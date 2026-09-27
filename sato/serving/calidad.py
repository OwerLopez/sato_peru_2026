"""Auditoria de calidad de los datos cargados en la base (se ejecuta al final de `python -m sato.pipeline load`).

Mide sobre la base real, sin muestreo ni valores fijos: cobertura de identificadores, valores nulos, duplicados,
consistencia de fechas, relaciones entre fuentes y frescura de cada fuente. El resultado se guarda en
`configuracion('calidad_datos')` y se publica en /api/v1/sistema/calidad y en la pantalla "Datos y fuentes".

Estados: OK (sin hallazgos), AVISO (hallazgo documentado que no invalida el uso) e INFO (dato descriptivo).
Ninguna regla modifica los datos: los hallazgos se informan tal como estan en las fuentes oficiales.

    python -m sato.serving.calidad
"""

from __future__ import annotations

import datetime as dt
import json
import logging

import psycopg

from sato.serving.load_db import dsn

log = logging.getLogger(__name__)

# (seccion, clave, descripcion, consulta que devuelve (valor, total) o (valor,), estado si valor > 0 cuando es un problema)
CHEQUEOS: list[tuple[str, str, str, str, str]] = [
    # ---- cuaderno de obra digital (OECE)
    ("Cuaderno de obra digital (OECE)", "obras", "Obras (contratos) con cuaderno de obra digital", "select count(*) from obra", "INFO"),
    ("Cuaderno de obra digital (OECE)", "asientos", "Asientos cargados", "select count(*) from asiento", "INFO"),
    ("Cuaderno de obra digital (OECE)", "asientos_duplicados", "Asientos repetidos (misma obra, número, fecha-hora y texto)",
     "select count(*) from (select 1 from asiento group by cuaderno_id, nro_asiento, fecha_hora, md5(coalesce(descripcion, '')) having count(*) > 1) x", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "obras_sin_entidad", "Obras sin entidad contratante identificada",
     "select count(*) filter (where entidad_ruc is null), count(*) from obra", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "obras_sin_contratista", "Obras sin contratista identificado",
     "select count(*) filter (where contratista_ruc is null), count(*) from obra", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "obras_sin_ubicacion", "Obras sin coordenadas geográficas",
     "select count(*) filter (where latitud is null or longitud is null), count(*) from obra", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "obras_sin_departamento", "Obras sin departamento",
     "select count(*) filter (where departamento is null), count(*) from obra", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "fechas_invertidas", "Obras cuyo último asiento es anterior al primero",
     "select count(*) filter (where ultimo_asiento < primer_asiento), count(*) from obra", "AVISO"),
    ("Cuaderno de obra digital (OECE)", "asientos_futuros", "Asientos fechados después del corte de datos",
     "select count(*) filter (where fecha > (select max(fecha_corte) from corte_datos)), count(*) from asiento", "AVISO"),
    # ---- enlaces entre fuentes
    ("Relación entre fuentes", "obras_con_cui", "Obras enlazadas a una inversión pública (CUI, Invierte.pe)",
     "select count(*) filter (where cui is not null), count(*) from obra", "INFO"),
    ("Relación entre fuentes", "obras_con_infobras", "Obras enlazadas a su ficha INFOBRAS",
     "select count(*) filter (where codigo_infobras is not null), count(*) from obra", "INFO"),
    ("Relación entre fuentes", "obras_con_seace", "Obras con contrato publicado en SEACE",
     "select count(*) filter (where url_contrato_seace is not null), count(*) from obra", "INFO"),
    ("Relación entre fuentes", "cartera_con_cuaderno", "Obras de la cartera INFOBRAS con cuaderno de obra digital",
     "select count(*) filter (where cuaderno_id is not null), count(*) from cartera_obra", "INFO"),
    ("Relación entre fuentes", "cartera_cuaderno_huerfano", "Enlaces de la cartera a cuadernos inexistentes",
     "select count(*) from cartera_obra c where c.cuaderno_id is not null and not exists (select 1 from obra o where o.cuaderno_id = c.cuaderno_id)", "AVISO"),
    ("Relación entre fuentes", "inversiones_con_siaf", "Inversiones enlazadas con ejecución mensual SIAF",
     "select count(distinct o.cui) filter (where exists (select 1 from siaf_mensual s where s.cui = o.cui)), count(distinct o.cui) from obra o where o.cui is not null", "INFO"),
    # ---- cartera INFOBRAS (Contraloria)
    ("Cartera INFOBRAS (Contraloría)", "cartera_obras", "Obras de la cartera nacional", "select count(*) from cartera_obra", "INFO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_sin_inicio", "Obras sin fecha de inicio",
     "select count(*) filter (where fecha_inicio is null), count(*) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_plazo_invalido", "Obras con plazo nulo o no positivo",
     "select count(*) filter (where plazo_dias is null or plazo_dias <= 0), count(*) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_fin_antes_inicio", "Obras con fin real anterior al inicio",
     "select count(*) filter (where fin_real < fecha_inicio), count(*) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_sin_costo", "Obras sin costo registrado",
     "select count(*) filter (where costo is null or costo <= 0), count(*) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_cui_irregular", "Obras con CUI que no tiene 7 dígitos (error de digitación en la fuente)",
     "select count(*) filter (where cui is not null and cui !~ '^[0-9]{7}$'), count(*) filter (where cui is not null) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_sin_ubicacion", "Obras sin coordenadas geográficas",
     "select count(*) filter (where latitud is null), count(*) from cartera_obra", "AVISO"),
    ("Cartera INFOBRAS (Contraloría)", "cartera_desactualizada", "Obras en ejecución sin registros en los últimos 12 meses (no se evalúan)",
     "select count(*) filter (where estado_operativo = 'DESACTUALIZADA'), count(*) from cartera_obra", "AVISO"),
    # ---- ejecucion financiera (MEF)
    ("Ejecución financiera (MEF)", "siaf_registros", "Registros mensuales de devengado SIAF", "select count(*) from siaf_mensual", "INFO"),
    ("Ejecución financiera (MEF)", "siaf_negativos", "Meses con devengado negativo (reversiones registradas en SIAF)",
     "select count(*) filter (where devengado < 0), count(*) from siaf_mensual", "INFO"),
    # ---- predicciones
    ("Predicciones", "vigentes_duplicadas", "Obras con más de una predicción vigente en el mismo corte",
     "select count(*) from (select cuaderno_id from prediccion where tipo = 'vigente' group by cuaderno_id, fecha_corte having count(*) > 1) x", "AVISO"),
    ("Predicciones", "vigentes_no_activas", "Predicciones vigentes sobre obras que no están en ejecución",
     "select count(*) filter (where o.estado_observado <> 'EN_EJECUCION'), count(*) from prediccion p join obra o using (cuaderno_id) where p.tipo = 'vigente'", "AVISO"),
    ("Predicciones", "vigentes_sin_explicacion", "Predicciones vigentes sin factores explicativos",
     "select count(*) filter (where not exists (select 1 from explicacion e where e.prediccion_id = p.id)), count(*) from prediccion p where p.tipo = 'vigente'", "AVISO"),
    ("Predicciones", "cartera_activa_sin_explicacion", "Obras activas de la cartera cuyo riesgo actual no tiene factores explicativos",
     """with lr as (select distinct on (c.codigo_infobras) r.id from cartera_obra c join cartera_riesgo r using (codigo_infobras)
                   where c.estado_operativo = 'ACTIVA' order by c.codigo_infobras, (r.tipo = 'seguimiento') desc, r.fecha_corte desc)
        select count(*) filter (where not exists (select 1 from cartera_explicacion e where e.riesgo_id = lr.id)), count(*) from lr""", "AVISO"),
]

FRESCURA = [
    ("Cuaderno de obra digital (OECE)", "select max(fecha) from asiento"),
    ("Ejecución financiera SIAF (MEF)", "select max(make_date(anio, mes, 1)) from siaf_mensual"),
    ("Seguimiento Invierte.pe F12B (MEF)", "select max(fecha_registro)::date from mef_seguimiento"),
    ("Obras paralizadas (Contraloría)", "select max(fecha_corte) from contraloria_paralizada"),
    ("Cartera INFOBRAS (Contraloría)", "select (valor->>'obs_end')::date from configuracion where clave = 'modelo_cartera'"),
]


def build() -> dict:
    res: list[dict] = []
    with psycopg.connect(dsn(), options="-c search_path=sato,public") as c:
        for seccion, clave, desc, sql, tipo in CHEQUEOS:
            r = c.execute(sql).fetchone()
            valor = int(r[0] or 0)
            total = int(r[1]) if len(r) > 1 and r[1] is not None else None
            estado = "INFO" if tipo == "INFO" else ("AVISO" if valor > 0 else "OK")
            res.append({"seccion": seccion, "clave": clave, "descripcion": desc, "valor": valor, "total": total,
                        "proporcion": (valor / total) if total else None, "estado": estado})
        frescura = [{"fuente": f, "ultimo_dato": str(c.execute(sql).fetchone()[0])} for f, sql in FRESCURA]
        archivos = c.execute("select count(*), coalesce(sum(bytes), 0), count(*) filter (where sha256 is null) from fuente_archivo").fetchone()
        out = {"generado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "chequeos": res, "frescura": frescura,
               "archivos": {"total": int(archivos[0]), "bytes": int(archivos[1]), "sin_huella": int(archivos[2])},
               "resumen": {e: sum(1 for x in res if x["estado"] == e) for e in ("OK", "AVISO", "INFO")}}
        c.execute("insert into configuracion (clave, valor) values ('calidad_datos', %s) on conflict (clave) do update set valor = excluded.valor",
                  (json.dumps(out),))
        c.commit()
    log.info("calidad de datos: %s", out["resumen"])
    return out


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    sys.stdout.reconfigure(encoding="utf-8")
    r = build()
    for x in r["chequeos"]:
        tot = f"/{x['total']:,}" if x["total"] else ""
        print(f"[{x['estado']:5s}] {x['descripcion']}: {x['valor']:,}{tot}")
    for f in r["frescura"]:
        print(f"  ultimo dato {f['fuente']}: {f['ultimo_dato']}")
