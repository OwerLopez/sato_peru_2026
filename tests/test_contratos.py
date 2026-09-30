"""Pruebas de contrato: forma y tipos de las respuestas publicas, documento OpenAPI y coherencia frontend <-> API.

Los valores se comparan con la base real (no con cifras fijas), de modo que las pruebas siguen siendo validas
despues de cada actualizacion mensual de los datos.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import requiere_bd

pytestmark = requiere_bd
WEB = Path(__file__).resolve().parents[1] / "web" / "src"


def _db():
    from sato.api import db

    return db


def _tipos(obj: dict, esquema: dict) -> None:
    for k, t in esquema.items():
        assert k in obj, f"falta {k}"
        assert obj[k] is None or isinstance(obj[k], t), f"{k}: {type(obj[k]).__name__}"


def test_openapi_documenta_todas_las_rutas(api_client):
    spec = api_client.get("/api/openapi.json").json()
    rutas = spec["paths"]
    assert len(rutas) >= 35
    for ruta, ops in rutas.items():
        assert ruta.startswith("/api/"), ruta
        for metodo, op in ops.items():
            assert op.get("tags"), f"{metodo} {ruta} sin etiqueta"
            assert "responses" in op


def _rutas_frontend() -> set[str]:
    """Rutas de la API que el frontend invoca (api<T>('/ruta...') y enlaces a /api/v1/...)."""
    rutas = set()
    for f in WEB.rglob("*.ts*"):
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"api<[^>]*>\(\s*([`'])(/[^`'?]*)", s):
            rutas.add(m.group(2))
        for m in re.finditer(r"[`'](?:\$\{API\}|/api/v1)(/[^`'?\"]*)", s):
            rutas.add(m.group(1))
    # la cadena de consulta (${qs(...)}) no forma parte de la ruta; los segmentos ${...} son parametros
    return {re.sub(r"\$\{[^}]+\}", "{p}", r.split("${qs")[0]).rstrip("/") for r in rutas}


def test_el_frontend_solo_llama_rutas_existentes(api_client):
    spec = api_client.get("/api/openapi.json").json()
    patrones = [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p[len("/api/v1"):]) + "$") for p in spec["paths"] if p.startswith("/api/v1")]
    usadas = _rutas_frontend()
    assert len(usadas) >= 20, usadas
    faltantes = [r for r in usadas if not any(p.match(r.replace("{p}", "x")) for p in patrones)]
    assert not faltantes, f"el frontend llama rutas que la API no expone: {faltantes}"


def test_contrato_resumen(api_client):
    j = api_client.get("/api/v1/resumen").json()
    for k in ("fecha_corte_cuaderno", "fecha_corte_cartera", "cuaderno", "cartera", "consolidado", "distribucion", "historico"):
        assert k in j
    _tipos(j["cuaderno"], {"activas": int, "alto": int, "medio": int})
    n = _db().one("""select count(*) n from prediccion p join modelo m on m.id = p.modelo_id and m.activo
                     where p.tipo = 'vigente' and p.fecha_corte = (select max(fecha_corte) from prediccion where tipo = 'vigente')""")["n"]
    assert j["cuaderno"]["activas"] == n
    for h in j["historico"]:
        assert h["observables"] <= h["evaluadas"] and h["alertas_confirmadas"] <= h["alertas"]


def test_contrato_listados_paginados(api_client):
    for ruta, clave in (("/api/v1/obras", "cuaderno_id"), ("/api/v1/cartera", "codigo_infobras")):
        p1 = api_client.get(ruta, params={"tamanio": 10, "pagina": 1}).json()
        p2 = api_client.get(ruta, params={"tamanio": 10, "pagina": 2}).json()
        assert p1["total"] == p2["total"] and len(p1["items"]) == 10
        assert not {x[clave] for x in p1["items"]} & {x[clave] for x in p2["items"]}  # paginas sin solapamiento
        scores = [x["score"] for x in p1["items"] + p2["items"] if x["score"] is not None]
        assert scores == sorted(scores, reverse=True)  # orden por riesgo por defecto
        ultima = api_client.get(ruta, params={"tamanio": 10, "pagina": 10**6}).json()
        assert ultima["items"] == []  # pagina fuera de rango: lista vacia, no error


def test_riesgo_vigente_coincide_con_la_ultima_prediccion(api_client):
    # la vista materializada debe devolver exactamente la ultima prediccion del modelo activo de cada obra
    difs = _db().one("""
        with ref as (select distinct on (p.cuaderno_id) p.cuaderno_id, p.id from prediccion p join modelo m on m.id = p.modelo_id and m.activo
                     order by p.cuaderno_id, p.fecha_corte desc)
        select count(*) n from ref full join obra_prediccion_vigente v using (cuaderno_id) where v.prediccion_id is distinct from ref.id""")["n"]
    assert difs == 0
    difs = _db().one("""
        with ref as (select distinct on (codigo_infobras) codigo_infobras, id from cartera_riesgo
                     order by codigo_infobras, (tipo = 'seguimiento') desc, fecha_corte desc)
        select count(*) n from ref full join cartera_riesgo_vigente v using (codigo_infobras) where v.riesgo_id is distinct from ref.id""")["n"]
    assert difs == 0


def test_contrato_ficha_de_obra_y_cartera(api_client):
    o = api_client.get("/api/v1/obras", params={"solo_vigentes": True, "tamanio": 1}).json()["items"][0]
    d = api_client.get(f"/api/v1/obras/{o['cuaderno_id']}").json()
    assert {"obra", "infobras", "contraloria_paralizada", "enlaces"} <= set(d)
    assert all(e["url"].startswith("https://") for e in d["enlaces"])
    c = api_client.get("/api/v1/cartera", params={"estado": "ACTIVA", "tamanio": 1}).json()["items"][0]
    dc = api_client.get(f"/api/v1/cartera/{c['codigo_infobras']}").json()
    assert {"obra", "riesgos", "explicaciones", "siaf_mensual", "umbrales", "enlaces"} <= set(dc)
    assert dc["explicaciones"], "obra activa sin factores explicativos"


def test_contrato_estado_del_sistema(api_client):
    j = api_client.get("/api/v1/sistema/estado").json()
    assert j["estado"] in ("OPERATIVO", "CON_AVISOS", "DEGRADADO")
    assert all(m["nivel"] in ("INFO", "AVISO", "CRITICO") and m["texto"] for m in j["motivos"])
    assert j["base_datos"]["ok"] and j["modelo"]["version"]
    if any(m["nivel"] == "CRITICO" for m in j["motivos"]):
        assert j["estado"] == "DEGRADADO"
    elif any(m["nivel"] == "AVISO" for m in j["motivos"]):
        assert j["estado"] == "CON_AVISOS"


def test_contrato_monitoreo_y_cargas(api_client):
    m = api_client.get("/api/v1/sistema/monitoreo").json()
    if m is None:
        pytest.skip("la carga vigente no incluye reporte de monitoreo")
    assert {"psi_ultimo_corte", "desempeno_realizado", "alertas"} <= set(m)
    assert all(0 <= r["recall_alerta"] <= 1 for r in m["desempeno_realizado"])
    c = api_client.get("/api/v1/sistema/cargas").json()["items"]
    for x in c:
        assert x["estado"] in ("EN_CURSO", "OK", "RECHAZADA", "ERROR")
        if x["estado"] == "OK":
            assert all(v["cargadas"] <= v["origen"] for v in x["conciliacion"].values())
        if x["estado"] == "ERROR":
            assert x["mensaje"] is None  # los errores internos no se publican


def test_contrato_calibracion_y_modelo(api_client):
    m = api_client.get("/api/v1/modelo").json()
    _tipos(m, {"version": str, "horizonte_dias": int, "umbral_alerta": float, "metricas": dict, "features": list})
    assert "password" not in str(m)
    c = api_client.get("/api/v1/modelo/calibracion").json()["alerta_60d"]
    assert [d["decil"] for d in c["deciles"]] == list(range(1, 11))
