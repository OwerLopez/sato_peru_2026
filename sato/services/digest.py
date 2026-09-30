"""Resumen (digest) semanal de alertas para suscriptores confirmados.

    DATABASE_URL=... python -m sato.services.digest [--base-url https://dominio]

Para cada suscripcion confirmada y activa: obras con cuaderno digital en nivel ALTO en el corte vigente del
ambito suscrito (departamento/provincia) y obras de la cartera INFOBRAS activas en nivel ALTO. Registra cada
envio en `envio_correo` con el modo real (smtp | archivo).
"""

from __future__ import annotations

import argparse
import logging

import psycopg

from sato.services.mailer import enviar
from sato.serving.load_db import dsn

log = logging.getLogger(__name__)


def construir(conn, dep, prov):
    corte = conn.execute("select max(fecha_corte) from sato.prediccion where tipo = 'vigente'").fetchone()[0]
    cua = conn.execute(
        """select o.denominacion, o.provincia, p.score, o.cuaderno_id::text from sato.prediccion p join sato.modelo m on m.id = p.modelo_id and m.activo
           join sato.obra o on o.cuaderno_id = p.cuaderno_id
           where p.fecha_corte = %s and p.tipo = 'vigente' and p.nivel = 'ALTO' and (%s::text is null or o.departamento = %s)
             and (%s::text is null or o.provincia = %s) order by p.score desc limit 25""", (corte, dep, dep, prov, prov)).fetchall()
    car = conn.execute(
        """select c.nombre, c.provincia, r.score, c.codigo_infobras from sato.cartera_obra c
           join sato.cartera_riesgo_vigente r on r.codigo_infobras = c.codigo_infobras
           where c.estado_operativo = 'ACTIVA' and r.nivel = 'ALTO' and (%s::text is null or c.departamento = %s)
             and (%s::text is null or c.provincia = %s) order by r.score desc limit 25""", (dep, dep, prov, prov)).fetchall()
    return corte, cua, car


def run(base_url: str = "http://localhost:8080") -> int:
    enviados = 0
    with psycopg.connect(dsn()) as conn:
        subs = conn.execute("select id, email, departamento, provincia, token from sato.suscripcion where confirmada and activa").fetchall()
        for sid, email, dep, prov, token in subs:
            corte, cua, car = construir(conn, dep, prov)
            ambito = " / ".join(x for x in (dep, prov) if x) or "Todo el Peru"
            lineas = [f"SATO - Resumen semanal de alertas ({ambito}). Corte del modelo de cuaderno digital: {corte}.", "",
                      f"Obras con cuaderno de obra digital en nivel ALTO (probabilidad de causal de atraso en 60 dias): {len(cua)}"]
            lineas += [f"  - {d[:110]} ({p}) {100 * s:.0f}%  {base_url}/obras/{i}" for d, p, s, i in cua]
            lineas += ["", f"Obras activas de la cartera INFOBRAS en nivel ALTO (riesgo de retraso significativo al termino): {len(car)}"]
            lineas += [f"  - {d[:110]} ({p}) {100 * s:.0f}%  {base_url}/cartera/{i}" for d, p, s, i in car]
            lineas += ["", "Estimaciones probabilisticas para priorizar la supervision; no determinan responsabilidades.",
                       f"Darse de baja: {base_url}/api/v1/suscripciones/baja?token={token}"]
            modo = enviar(email, f"SATO - Alertas de obras ({ambito})", "\n".join(lineas))
            conn.execute("insert into sato.envio_correo (suscripcion_id, modo, obras, destino) values (%s, %s, %s, %s)",
                         (sid, modo, len(cua) + len(car), email))
            conn.execute("update sato.suscripcion set ultimo_envio = now() where id = %s", (sid,))
            enviados += 1
        conn.commit()
    log.info("digest: %s suscripciones procesadas", enviados)
    return enviados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    run(ap.parse_args().base_url)
