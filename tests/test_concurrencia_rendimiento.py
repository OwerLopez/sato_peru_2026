"""Pruebas de concurrencia (solicitudes simultaneas, escrituras concurrentes, exclusion mutua del worker) y de
rendimiento de los endpoints principales contra la base real. La carga sostenida con usuarios virtuales se mide
aparte con k6 (docs/articulo/evaluacion/k6_carga.js)."""

from __future__ import annotations

import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from tests.conftest import requiere_bd, token_de

pytestmark = requiere_bd

RUTAS = ["/api/v1/resumen", "/api/v1/obras?tamanio=25", "/api/v1/cartera?tamanio=25", "/api/v1/comparador", "/api/v1/filtros",
         "/api/v1/modelo/calibracion", "/api/v1/radar/cuaderno?limite=50", "/api/v1/cartera?tamanio=25&nivel=ALTO&orden=monto",
         "/api/v1/sistema/estado"]


def test_solicitudes_simultaneas_consistentes(api_client):
    referencia = {r: api_client.get(r).json() for r in RUTAS}
    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda r: (r, api_client.get(r)), RUTAS * 8))
    assert all(x.status_code == 200 for _, x in res)
    for r, x in res:
        if r != "/api/v1/sistema/estado":  # el estado incluye la hora de verificacion
            assert x.json() == referencia[r], r


def test_revisiones_concurrentes_no_se_pierden(api_client, crear_usuario):
    a = api_client.get("/api/v1/alertas", params={"limite": 1}).json()["items"]
    if not a:
        pytest.skip("sin alertas vigentes")
    h = token_de(api_client, crear_usuario())
    url = f"/api/v1/alertas/{a[0]['cuaderno_id']}/{a[0]['fecha_corte']}/revisiones"
    marca = uuid.uuid4().hex
    with ThreadPoolExecutor(10) as ex:
        codigos = list(ex.map(lambda i: api_client.post(url, headers=h, json={"decision": "EN_SEGUIMIENTO", "comentario": f"{marca}-{i}"}).status_code,
                              range(10)))
    assert codigos == [201] * 10
    assert sum(x["comentario"].startswith(marca) for x in api_client.get(url, headers=h).json()) == 10


def test_suscripciones_concurrentes_del_mismo_correo(api_client, bandeja, limpiar_suscripciones):
    from sato.api import db

    email = f"con-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(email)
    with ThreadPoolExecutor(8) as ex:
        codigos = list(ex.map(lambda _: api_client.post("/api/v1/suscripciones", json={"email": email}).status_code, range(8)))
    assert set(codigos) == {202}
    assert db.one("select count(*) n from suscripcion where email = :e", e=email)["n"] == 1


def test_una_sola_sincronizacion_a_la_vez(monkeypatch):
    """Con el candado tomado por otro proceso, el worker omite el ciclo sin ejecutar pasos ni registrar una sincronizacion."""
    import os

    from sato import cron_runner

    monkeypatch.setenv("DATABASE_URL", os.environ["SATO_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
    from sato.serving.load_db import dsn

    ejecutados = []
    monkeypatch.setattr("sato.pipeline.STEPS", {p: (lambda p=p: ejecutados.append(p)) for p in cron_runner.PASOS_DEFECTO.split()})
    with psycopg.connect(dsn(), autocommit=True) as otro:
        otro.execute("select pg_advisory_lock(%s)", (cron_runner.CANDADO,))
        antes = otro.execute("select count(*) from sato.sincronizacion").fetchone()[0]
        assert cron_runner.sincronizar() == "OMITIDA"
        assert otro.execute("select count(*) from sato.sincronizacion").fetchone()[0] == antes and ejecutados == []
        otro.execute("select pg_advisory_unlock(%s)", (cron_runner.CANDADO,))


def test_worker_registra_reintentos_y_recupera_interrumpidas(monkeypatch):
    import os

    from sato import cron_runner

    monkeypatch.setenv("DATABASE_URL", os.environ["SATO_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
    monkeypatch.setenv("SATO_SYNC_PASOS", "monitor")
    monkeypatch.setenv("SATO_PASO_REINTENTOS", "1")
    monkeypatch.delenv("SATO_ALERTAS_EMAIL", raising=False)
    fallos = iter([ConnectionError("fuente no responde")])

    def paso():
        if e := next(fallos, None):
            raise e

    monkeypatch.setattr("sato.pipeline.STEPS", {"monitor": paso})
    monkeypatch.setattr(cron_runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(cron_runner, "avisos_monitoreo", lambda: None)
    from sato.serving.load_db import dsn

    with psycopg.connect(dsn(), autocommit=True) as c:
        huerfana = c.execute("insert into sato.sincronizacion (estado, inicio) values ('EN_CURSO', now() - interval '2 days') returning id").fetchone()[0]
        try:
            assert cron_runner.sincronizar() == "OK"
            estado, msj = c.execute("select estado, mensaje from sato.sincronizacion where id = %s", (huerfana,)).fetchone()
            assert estado == "ERROR" and msj.startswith("Interrumpida")
            pasos = c.execute("select pasos from sato.sincronizacion order by id desc limit 1").fetchone()[0]
            assert pasos == [{"paso": "monitor", "segundos": 0, "intentos": 2}]
        finally:
            c.execute("delete from sato.sincronizacion where id >= %s", (huerfana,))


def _p95(client, ruta: str, n: int = 20) -> float:
    t = []
    for _ in range(n):
        t0 = time.perf_counter()
        assert client.get(ruta).status_code == 200
        t.append(1000 * (time.perf_counter() - t0))
    return statistics.quantiles(t, n=20)[18]


@pytest.mark.parametrize("ruta,limite_ms", [
    ("/api/v1/resumen", 150), ("/api/v1/comparador", 150), ("/api/v1/obras?tamanio=25", 400), ("/api/v1/cartera?tamanio=25", 500),
    ("/api/v1/cartera?tamanio=25&nivel=ALTO&orden=monto", 500), ("/api/v1/obras?q=colegio&tamanio=25", 600),
    ("/api/v1/modelo/calibracion", 150), ("/api/v1/sistema/estado", 400),
])
def test_latencia_p95(api_client, ruta, limite_ms):
    api_client.get(ruta)  # calentamiento (primera consulta y cache)
    p95 = _p95(api_client, ruta)
    assert p95 < limite_ms, f"{ruta}: p95 {p95:.0f} ms"
