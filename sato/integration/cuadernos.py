"""Tablas curadas de cuadernos de obra digital y sus asientos.

Salidas (data/curated):
  * asiento.parquet   : un asiento por fila, con fecha, rol, tipo original,
                        tipo armonizado entre regimenes (Ley 30225 / Ley 32069)
                        y texto.
  * cuaderno.parquet  : un cuaderno por fila (nacional), con metadatos del
                        contrato, ubicacion, CUI enlazado (metodo de enlace),
                        completitud de historia y fechas de primeros eventos.

Completitud de historia: los asientos abiertos solo existen desde 2024-06. Un
cuaderno tiene historia completa si su menor NRO_ASIENTO_REGISTRADO observado es
<= 1 (el asiento de apertura esta dentro de la ventana publicada). Solo esos
cuadernos permiten reconstruir su evolucion desde el inicio sin sesgo de
truncamiento por la izquierda.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from sato.config import CURATED, STAGING

log = logging.getLogger(__name__)

# Armonizacion del catalogo de tipos de asiento. El catalogo cambio el
# 2025-05-01 (entrada en vigencia de la Ley 32069, 22-04-2025) y el 2026-04-01
# (DS 001-2026-EF). Tipos equivalentes se unifican bajo un codigo estable.
TIPO_MAP = {
    "Apertura del cuaderno de obra digital": "APERTURA",
    "Apertura del cuaderno": "APERTURA",
    "Cierre del cuaderno de obra digital": "CIERRE",
    "Cierre del cuaderno": "CIERRE",
    "Adicionales de obra": "ADICIONALES",
    "Adicionales": "ADICIONALES",
    "Participación del plantel profesional clave": "PERSONAL_CLAVE",
    "Participación del personal clave": "PERSONAL_CLAVE",
    "Participación de profesionales adicionales al plantel técnico ofertado": "PROFESIONALES_ADICIONALES",
    "Participación de profesionales adicionales al personal clave": "PROFESIONALES_ADICIONALES",
    "Inicio del plazo de ejecución de obra": "INICIO_PLAZO",
    "Inicio del plazo de ejecución del contrato": "INICIO_PLAZO",
    "Reducciones de obra": "REDUCCIONES",
    "Reducción de prestaciones": "REDUCCIONES",
    "Otras ocurrencias": "OTRAS_OCURRENCIAS",
    "Consultas": "CONSULTAS",
    "Respuestas a consultas": "RESPUESTAS_CONSULTAS",
    "Ampliaciones de plazo": "AMPLIACION_PLAZO",
    "Ejecución de mayores metrados": "MAYORES_METRADOS",
    "Valorizaciones y metrados": "VALORIZACIONES",
    "Administración de riesgos": "RIESGOS",
    "Programa de ejecución de obra - CPM": "PROGRAMA_CPM",
    "Suspensión del plazo de ejecución": "SUSPENSION_PLAZO",
    "Constatación física de la obra": "CONSTATACION_FISICA",
    "Órdenes": "ORDENES",
    "Culminación de la obra": "CULMINACION",
    "Recepción de la obra": "RECEPCION",
    "Calendario de avance de obra valorizado": "CALENDARIO_VALORIZADO",
    "Calendario acelerado de obra": "CALENDARIO_ACELERADO",
    "Aplicación de penalidades": "PENALIDADES",
    "Otras modificaciones contractuales": "OTRAS_MODIFICACIONES",
    "Valorización acumulada ejecutada menor al 80% del monto acumulado programado": "VALORIZACION_MENOR_80",
    "Resolución de contrato": "RESOLUCION_CONTRATO",
    "Subcontratación": "SUBCONTRATACION",
    "Elaboración de expediente técnico de obra": "EXPEDIENTE_TECNICO",
    "Aprobación final del expediente técnico de obra": "EXPEDIENTE_TECNICO",
    "Cierre de elaboración del expediente técnico de obra": "EXPEDIENTE_TECNICO",
    "Entregables": "ENTREGABLES",
    "Adelantos": "ADELANTOS",
}

# Eventos de atraso normativo (RLCE art. 203 / RLGCP art. 207).
EVENTO_ATRASO = ("VALORIZACION_MENOR_80", "CALENDARIO_ACELERADO")


def build(out: Path = CURATED) -> tuple[Path, Path]:
    con = duckdb.connect()
    con.sql("set preserve_insertion_order=false")
    con.register("tipo_map", __import__("pandas").DataFrame({"tipo": list(TIPO_MAP), "tipo_std": list(TIPO_MAP.values())}))
    asi = out / "asiento.parquet"
    con.sql(
        f"""
        copy (
          select a.ID_CUADERNO cuaderno_id,
                 try_cast(a.NRO_ASIENTO_REGISTRADO as int) nro_asiento,
                 strptime(a.FECHA_REGISTRO_ASIENTO, '%Y%m%d')::date fecha,
                 try_strptime(a.FECHA_REGISTRO_ASIENTO || ' ' || a.HORA_REGISTRO_ASIENTO, '%Y%m%d %H:%M') fecha_hora,
                 a.TIPO_USUARIO_REGISTRANTE rol,
                 a.TIPO_ASIENTO_REGISTRADO tipo,
                 coalesce(m.tipo_std, 'OTRO') tipo_std,
                 a.TITULO_ASIENTO_REGISTRADO titulo,
                 a.DESCRIPCION_DEL_ASIENTO descripcion,
                 a.ASIENTO_ENLAZADO asiento_enlazado,
                 a.src_file, a.parse_status
          from '{(STAGING / "oece_asientos.parquet").as_posix()}' a
          left join tipo_map m on m.tipo = a.TIPO_ASIENTO_REGISTRADO
        ) to '{asi.as_posix()}' (format parquet, compression zstd)
        """
    )
    unmapped = con.sql(f"select tipo, count(*) from '{asi.as_posix()}' where tipo_std='OTRO' group by 1").fetchall()
    if unmapped:
        log.warning("tipos sin armonizar: %s", unmapped)

    cua = out / "cuaderno.parquet"
    ev = ", ".join(
        f"min(fecha) filter (where tipo_std='{t}') f_{t.lower()}"
        for t in ("VALORIZACION_MENOR_80", "CALENDARIO_ACELERADO", "SUSPENSION_PLAZO", "RESOLUCION_CONTRATO",
                  "AMPLIACION_PLAZO", "CULMINACION", "RECEPCION", "CIERRE", "APERTURA", "INICIO_PLAZO",
                  "PENALIDADES", "ADICIONALES")
    )
    con.sql(
        f"""
        copy (
          with meta as (
            select NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA cuaderno_id,
                   any_value(IDENTIFICADOR_DEL_CONTRATO) contrato_id,
                   any_value(IDENTIFICADOR_DEL_EXPEDIENTE) expediente_id,
                   any_value(RUC_CONTRATISTA) ruc_contratista,
                   any_value(RAZON_SOCIAL_CONTRATISTA) contratista,
                   any_value(RUC_ENTIDAD_CONTRATANTE) ruc_entidad,
                   any_value(RAZON_SOCIAL_ENTIDAD_CONTRATANTE) entidad,
                   any_value(DENOMINACION_DE_LA_OBRA) denominacion,
                   any_value(UBIGEO) ubigeo,
                   any_value(DESCRIPCION_DE_UBIGEO) ubigeo_desc,
                   try_cast(replace(any_value(LATITUD_REFERENCIA_DE_OBRA), ',', '.') as double) latitud,
                   try_cast(replace(any_value(LONGITUD_REFERNCIA_DE_OBRA), ',', '.') as double) longitud,
                   any_value(ES_CONSORCIO) = 'Si' es_consorcio,
                   count(*) n_miembros,
                   any_value(src_file) archivo_cuaderno
            from '{(STAGING / "oece_cuadernos.parquet").as_posix()}' group by 1
          ),
          agg as (
            select cuaderno_id, count(*) n_asientos, min(nro_asiento) min_nro_asiento, max(nro_asiento) max_nro_asiento,
                   min(fecha) primer_asiento, max(fecha) ultimo_asiento, {ev}
            from '{asi.as_posix()}' group by 1
          )
          select coalesce(meta.cuaderno_id, agg.cuaderno_id) cuaderno_id, meta.* exclude (cuaderno_id),
                 substr(meta.ubigeo, 1, 2) dep_code,
                 trim(split_part(meta.ubigeo_desc, ',', 1)) departamento,
                 trim(split_part(meta.ubigeo_desc, ',', 2)) provincia,
                 trim(split_part(meta.ubigeo_desc, ',', 3)) distrito,
                 agg.* exclude (cuaderno_id),
                 coalesce(agg.min_nro_asiento <= 1, false) historia_completa,
                 meta.cuaderno_id is not null tiene_metadatos,
                 l.cui, l.method link_method, l.fuzzy_score link_score
          from meta full outer join agg on meta.cuaderno_id = agg.cuaderno_id
          left join '{(out / "link_cuaderno_cui.parquet").as_posix()}' l on l.cuaderno_id = coalesce(meta.cuaderno_id, agg.cuaderno_id)
        ) to '{cua.as_posix()}' (format parquet, compression zstd)
        """
    )
    log.info("cuadernos: %s", con.sql(f"select count(*), count(*) filter (where historia_completa) from '{cua.as_posix()}'").fetchone())
    return asi, cua


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build()
