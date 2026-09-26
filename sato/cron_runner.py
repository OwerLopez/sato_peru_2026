"""Ejecutor programado (worker) de SATO.

    python -m sato.cron_runner            # bucle: sincronizacion mensual + digest semanal
    python -m sato.cron_runner --una-vez  # ejecuta una sincronizacion inmediata y termina

Politica (configurable por entorno):
  * SATO_SYNC_DIA (2): dia del mes en que se sincroniza (OECE publica los asientos del mes anterior el dia 1).
  * SATO_SYNC_PASOS ("ingest staging integration features release cartera monitor load"): pasos del pipeline.
    Los embeddings y la grilla experimental no se recalculan automaticamente (GPU / costo); se ejecutan a demanda.
  * SATO_DIGEST_DIA_SEMANA (0 = lunes): dia del resumen semanal por correo.
Cada sincronizacion queda registrada en la tabla `sincronizacion` (inicio, fin, estado, pasos, error).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import time
import traceback

import psycopg

from sato.services.schedule import proxima_sync  # noqa: F401  (reexportado)
from sato.serving.load_db import dsn

log = logging.getLogger("sato.cron")


def sincronizar() -> str:
    from sato import pipeline

    pasos = os.environ.get("SATO_SYNC_PASOS", "ingest staging integration features release cartera monitor load").split()
    with psycopg.connect(dsn(), autocommit=True) as conn:
        sid = conn.execute("insert into sato.sincronizacion (estado, pasos) values ('EN_CURSO', %s) returning id", (json.dumps(pasos),)).fetchone()[0]
    hechos = []
    try:
        for p in pasos:
            t0 = time.time()
            pipeline.STEPS[p]()
            hechos.append({"paso": p, "segundos": round(time.time() - t0)})
        estado, msg = "OK", None
    except Exception as e:  # se registra el error real; el worker sigue vivo
        estado, msg = "ERROR", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        log.exception("sincronizacion fallida")
    with psycopg.connect(dsn(), autocommit=True) as conn:
        corte = conn.execute("select max(fecha_corte) from sato.corte_datos").fetchone()[0]
        conn.execute("update sato.sincronizacion set fin = now(), estado = %s, pasos = %s, mensaje = %s, corte_datos = %s where id = %s",
                     (estado, json.dumps(hechos), msg, corte, sid))
    return estado


def bucle():
    ultimo_digest = None
    while True:
        hoy = dt.date.today()
        with psycopg.connect(dsn(), autocommit=True) as conn:
            ult = conn.execute("select max(inicio)::date from sato.sincronizacion where estado = 'OK'").fetchone()[0]
        dia = int(os.environ.get("SATO_SYNC_DIA", "2"))
        if hoy.day >= dia and (ult is None or (ult.year, ult.month) < (hoy.year, hoy.month)):
            log.info("sincronizacion mensual: %s", sincronizar())
        if hoy.weekday() == int(os.environ.get("SATO_DIGEST_DIA_SEMANA", "0")) and ultimo_digest != hoy:
            from sato.services import digest

            digest.run(os.environ.get("SATO_BASE_URL", "http://localhost:8080"))
            ultimo_digest = hoy
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
