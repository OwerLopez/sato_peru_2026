"""Ejecutor programado (worker) de SATO: sincronizacion mensual autocontrolada y resumen semanal.

    python -m sato.cron_runner            # bucle: sincronizacion mensual + digest semanal
    python -m sato.cron_runner --una-vez  # ejecuta una sincronizacion inmediata y termina

Politica (configurable por entorno):
  * SATO_SYNC_DIA (2): dia del mes en que se sincroniza (OECE publica los asientos del mes anterior el dia 1).
  * SATO_SYNC_PASOS ("ingest staging integration features release cartera monitor load"): pasos del pipeline.
    Los embeddings y la grilla experimental no se recalculan automaticamente (GPU / costo); se ejecutan a demanda.
  * SATO_SYNC_MAX_INTENTOS (3): intentos por mes; entre intentos fallidos se espera 2, 4, 8... horas.
  * SATO_PASO_REINTENTOS (2): reintentos inmediatos de un paso ante errores transitorios (red, base de datos), con espera
    exponencial. Un rechazo de la compuerta de integridad NO se reintenta: los datos de origen no cambiaran en minutos.
  * SATO_DIGEST_DIA_SEMANA (0 = lunes): dia del resumen semanal por correo.
  * SATO_ALERTAS_EMAIL: correos (separados por coma) que reciben los avisos de operacion (fallo, rechazo, deriva del modelo).

Autocontrol:
  * candado de la base (pg_try_advisory_lock): nunca corren dos sincronizaciones a la vez (varios workers o una manual);
  * al iniciar, las sincronizaciones que quedaron EN_CURSO por un corte abrupto se marcan como ERROR (interrumpidas);
  * latido en `servicio_latido` en cada ciclo: la API informa si el worker dejo de responder;
  * cada sincronizacion queda en `sincronizacion` (inicio, fin, estado, pasos con duracion e intentos, error).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import time
import traceback
from collections.abc import Callable

import psycopg

from sato.services.schedule import dia_sync, proxima_sync
from sato.serving.load_db import CargaRechazada, dsn

log = logging.getLogger("sato.cron")
CANDADO = 7_314_159  # clave del advisory lock de la sincronizacion
PASOS_DEFECTO = "ingest staging integration features release cartera monitor load"


def reintentar(fn: Callable[[], None], intentos: int, espera_s: float, dormir: Callable[[float], None] | None = None) -> int:
    """Ejecuta `fn` con reintentos y espera exponencial. Devuelve el numero de intentos usados; relanza el ultimo error.
    Los rechazos de la compuerta de integridad se relanzan de inmediato (no son transitorios)."""
    for i in range(1, intentos + 2):
        try:
            fn()
            return i
        except CargaRechazada:
            raise
        except Exception as e:  # noqa: BLE001
            if i > intentos:
                raise
            espera = espera_s * 2 ** (i - 1)
            log.warning("paso fallido (%s: %s); reintento %s de %s en %.0f s", type(e).__name__, e, i, intentos, espera)
            (dormir or time.sleep)(espera)
    raise AssertionError("inalcanzable")


def debe_sincronizar(hoy: dt.date, ahora: dt.datetime, ultimo_ok: dt.date | None, fallos_mes: int, ultimo_fallo: dt.datetime | None,
                     max_intentos: int) -> tuple[bool, str]:
    """Decide si corresponde sincronizar en este ciclo (funcion pura, probada en tests/test_operacion.py)."""
    if hoy.day < dia_sync():
        return False, "antes del dia de sincronizacion"
    if ultimo_ok and (ultimo_ok.year, ultimo_ok.month) >= (hoy.year, hoy.month):
        return False, "ya sincronizado este mes"
    if fallos_mes >= max_intentos:
        return False, f"se agotaron los {max_intentos} intentos del mes; requiere revision manual"
    if ultimo_fallo is not None and fallos_mes > 0:
        espera = dt.timedelta(hours=2 ** fallos_mes)
        if ahora - ultimo_fallo < espera:
            return False, f"esperando {espera} desde el ultimo fallo"
    return True, "corresponde sincronizar"


def notificar(asunto: str, texto: str) -> None:
    from sato.services.mailer import enviar

    for dest in [x.strip() for x in os.environ.get("SATO_ALERTAS_EMAIL", "").split(",") if x.strip()]:
        try:
            enviar(dest, f"SATO - {asunto}", texto)
        except Exception:  # noqa: BLE001  (un aviso fallido no debe detener el worker)
            log.exception("no se pudo enviar el aviso a %s", dest)


def latido(detalle: dict) -> None:
    with psycopg.connect(dsn(), autocommit=True) as conn:
        conn.execute("""insert into sato.servicio_latido (servicio, ts, detalle) values ('worker', now(), %s)
                        on conflict (servicio) do update set ts = now(), detalle = excluded.detalle""", (json.dumps(detalle, default=str),))


def recuperar_interrumpidas(conn: psycopg.Connection) -> int:
    """Marca como ERROR las sincronizaciones EN_CURSO sin proceso vivo (se llama con el candado tomado)."""
    r = conn.execute("""update sato.sincronizacion set estado = 'ERROR', fin = now(),
                          mensaje = 'Interrumpida: el proceso termino antes de registrar el resultado'
                        where estado = 'EN_CURSO' returning id""").fetchall()
    return len(r)


def sincronizar() -> str:
    from sato import pipeline

    pasos = os.environ.get("SATO_SYNC_PASOS", PASOS_DEFECTO).split()
    reintentos = int(os.environ.get("SATO_PASO_REINTENTOS", "2"))
    # conexion que mantiene el candado durante toda la sincronizacion (se libera sola si el proceso muere)
    with psycopg.connect(dsn(), autocommit=True) as lock_conn:
        if not lock_conn.execute("select pg_try_advisory_lock(%s)", (CANDADO,)).fetchone()[0]:
            log.warning("otra sincronizacion esta en curso: se omite este ciclo")
            return "OMITIDA"
        if n := recuperar_interrumpidas(lock_conn):
            log.warning("%s sincronizaciones interrumpidas marcadas como ERROR", n)
        sid = lock_conn.execute("insert into sato.sincronizacion (estado, pasos) values ('EN_CURSO', %s) returning id",
                                (json.dumps(pasos),)).fetchone()[0]
        hechos = []
        try:
            for p in pasos:
                t0 = time.time()
                intentos = reintentar(pipeline.STEPS[p], reintentos, 60)
                hechos.append({"paso": p, "segundos": round(time.time() - t0), "intentos": intentos})
            estado, msg = "OK", None
        except CargaRechazada as e:
            estado, msg = "RECHAZADA", str(e)[:3000]
            log.error("carga rechazada por la compuerta de integridad: %s", e)
        except Exception as e:  # se registra el error real; el worker sigue vivo
            estado, msg = "ERROR", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
            log.exception("sincronizacion fallida")
        corte = lock_conn.execute("select max(fecha_corte) from sato.corte_datos").fetchone()[0]
        lock_conn.execute("update sato.sincronizacion set fin = now(), estado = %s, pasos = %s, mensaje = %s, corte_datos = %s where id = %s",
                          (estado, json.dumps(hechos), msg, corte, sid))
        lock_conn.execute("select pg_advisory_unlock(%s)", (CANDADO,))
    if estado != "OK":
        notificar(f"sincronizacion {estado.lower()}", f"La sincronizacion {sid} termino en estado {estado}.\n"
                  f"Pasos completados: {[h['paso'] for h in hechos]}\n\n{msg}\n\n"
                  "La plataforma sigue sirviendo los datos del corte anterior.")
    else:
        avisos_monitoreo()
    return estado


def avisos_monitoreo() -> None:
    """Tras una sincronizacion exitosa, avisa si el monitoreo del modelo detecto deriva o anomalias."""
    from sato.config import ARTIFACTS

    f = ARTIFACTS / "monitoring" / "reporte.json"
    if f.exists():
        alertas = json.loads(f.read_text(encoding="utf-8")).get("alertas") or []
        if alertas:
            notificar("avisos del monitoreo del modelo", "El monitoreo mensual del modelo reporto:\n- " + "\n- ".join(alertas))


def estado_mes(conn: psycopg.Connection, hoy: dt.date) -> tuple[dt.date | None, int, dt.datetime | None]:
    ult_ok = conn.execute("select max(inicio)::date from sato.sincronizacion where estado = 'OK'").fetchone()[0]
    fallos, ult_fallo = conn.execute("""select count(*), max(inicio) from sato.sincronizacion
                                         where estado in ('ERROR', 'RECHAZADA') and inicio >= date_trunc('month', %s::date)""", (hoy,)).fetchone()
    return ult_ok, int(fallos), ult_fallo


def bucle():
    ultimo_digest = None
    max_intentos = int(os.environ.get("SATO_SYNC_MAX_INTENTOS", "3"))
    while True:
        hoy, ahora = dt.date.today(), dt.datetime.now(dt.UTC)
        try:
            with psycopg.connect(dsn(), autocommit=True) as conn:
                ult_ok, fallos, ult_fallo = estado_mes(conn, hoy)
            ok, motivo = debe_sincronizar(hoy, ahora, ult_ok, fallos, ult_fallo, max_intentos)
            latido({"decision": motivo, "proxima_sincronizacion": proxima_sync(hoy), "fallos_mes": fallos})
            if ok:
                resultado = sincronizar()
                log.info("sincronizacion mensual: %s", resultado)
                if resultado in ("ERROR", "RECHAZADA") and fallos + 1 >= max_intentos:
                    notificar("intentos agotados", f"Se agotaron los {max_intentos} intentos de sincronizacion de {hoy:%Y-%m}. "
                              "Revise el historial en /api/v1/admin/sincronizaciones.")
            if hoy.weekday() == int(os.environ.get("SATO_DIGEST_DIA_SEMANA", "0")) and ultimo_digest != hoy:
                from sato.services import digest

                digest.run(os.environ.get("SATO_BASE_URL", "http://localhost:8080"))
                ultimo_digest = hoy
        except psycopg.OperationalError:  # base caida: se reintenta en el proximo ciclo sin terminar el worker
            log.exception("base de datos no disponible; nuevo intento en el proximo ciclo")
        time.sleep(3600)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--una-vez", action="store_true")
    a = ap.parse_args()
    if a.una_vez:
        print(sincronizar())
    else:
        bucle()
