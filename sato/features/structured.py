"""Features estructuradas (Modelo A) por (cuaderno, T).

Cada grupo documenta su regla de disponibilidad temporal. La auditoria
feature por feature esta en docs/methodology/LEAKAGE_POLICY.md; este modulo
implementa exactamente esas reglas:

  ASIENTOS_*   : asientos con fecha <= T (el COD publica en tiempo real).
  ESTATICO_*   : atributos fijados al inicio del contrato / de la inversion.
  ACTOR_*      : historial de contratista y entidad con eventos fechados < T.
  SIAF_*       : devengado mensual hasta el mes anterior a T (rezago de 1 mes);
                 PIA del anio de T (se conoce desde el 1 de enero). El PIM del
                 anio en curso NO se usa (no esta fechado).
  MEFSEG_*     : registros de estado situacional F12B con fecha_registro <= T.
  IB_*         : SOLO atributos de INFOBRAS fijados al inicio de la obra (plazo de
                 ejecucion original, monto del contrato, fecha de inicio de obra) de la
                 obra enlazada deterministicamente (CUI + RUC). Riesgo residual: la
                 foto de INFOBRAS es posterior a T; se asume que estos campos no se
                 reescriben (se evalua con ablacion sin IB_*).

Prohibidos (foto actual, posterior a T): estado/costo actualizado/avance de MEF,
todos los campos variables de INFOBRAS, monto adicional / fin de vigencia
actualizada de SEACE, asientos con fecha > T.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from sato.config import CURATED, FEATURES, STAGING

log = logging.getLogger(__name__)

TIPOS = [
    "AMPLIACION_PLAZO", "SUSPENSION_PLAZO", "ADICIONALES", "MAYORES_METRADOS", "CONSULTAS",
    "RESPUESTAS_CONSULTAS", "PENALIDADES", "ORDENES", "RIESGOS", "CONSTATACION_FISICA", "PROGRAMA_CPM",
    "CALENDARIO_VALORIZADO", "VALORIZACIONES", "OTRAS_MODIFICACIONES", "REDUCCIONES", "PERSONAL_CLAVE",
    "EXPEDIENTE_TECNICO", "ADELANTOS", "OTRAS_OCURRENCIAS", "INICIO_PLAZO",
]
REGIMEN_32069_DESDE = "2025-04-22"


def _p(path: Path) -> str:
    return f"'{path.as_posix()}'"


def build(out: Path = FEATURES) -> Path:
    con = duckdb.connect()
    con.sql("set preserve_insertion_order=false")
    con.sql(f"create table panel as select cuaderno_id, \"T\"::date t from {_p(out / 'panel.parquet')}")
    con.sql(f"create table cua as select * from {_p(CURATED / 'cuaderno.parquet')} where tiene_metadatos and historia_completa")
    con.sql(
        f"""create table asi as select a.cuaderno_id, a.fecha::date fecha, a.tipo_std, a.rol, a.tipo
            from {_p(CURATED / 'asiento.parquet')} a semi join cua on cua.cuaderno_id = a.cuaderno_id"""
    )

    cum = ",\n".join(f"count(*) filter (where a.tipo_std='{t}') as asi_cum_{t.lower()}" for t in TIPOS)
    w90 = ",\n".join(f"count(*) filter (where a.tipo_std='{t}' and a.fecha > p.t - 90) as asi_90d_{t.lower()}" for t in TIPOS)
    con.sql(
        f"""
        create table f_asi as
        select p.cuaderno_id, p.t,
          count(*) as asi_n_total,
          count(*) filter (where a.fecha > p.t - 30) as asi_n_30d,
          count(*) filter (where a.fecha > p.t - 90) as asi_n_90d,
          count(distinct a.fecha) filter (where a.fecha > p.t - 30) as asi_dias_activos_30d,
          p.t - max(a.fecha) as asi_dias_desde_ultimo,
          p.t - min(a.fecha) as asi_dias_desde_primero,
          avg(case when a.rol in ('SOEC_SPV','SOEC_INSP') then 1 else 0 end) filter (where a.fecha > p.t - 90) as asi_frac_supervision_90d,
          {cum},
          {w90},
          min(a.fecha) filter (where a.tipo_std = 'INICIO_PLAZO') as _f_inicio_plazo,
          bool_or(a.tipo = 'Apertura del cuaderno') as est_regimen_ley32069
        from panel p join asi a on a.cuaderno_id = p.cuaderno_id and a.fecha <= p.t
        group by p.cuaderno_id, p.t
        """
    )

    # Historial de actores (contratista y entidad) con eventos fechados antes de T (nacional).
    con.sql(
        f"""
        create table actor_ev as
        select c.cuaderno_id, c.ruc_contratista, c.ruc_entidad, c.primer_asiento::date inicio,
               least(c.f_valorizacion_menor_80, c.f_calendario_acelerado)::date onset
        from {_p(CURATED / 'cuaderno.parquet')} c where c.tiene_metadatos
        """
    )
    con.sql(
        """
        create table f_actor as
        select p.cuaderno_id, p.t,
          (select count(*) from actor_ev e where e.ruc_contratista = c.ruc_contratista and e.cuaderno_id <> p.cuaderno_id and e.inicio < p.t) as actor_contratista_obras_previas,
          (select count(*) from actor_ev e where e.ruc_contratista = c.ruc_contratista and e.cuaderno_id <> p.cuaderno_id and e.onset < p.t) as actor_contratista_atrasos_previos,
          (select count(*) from actor_ev e where e.ruc_entidad = c.ruc_entidad and e.cuaderno_id <> p.cuaderno_id and e.inicio < p.t) as actor_entidad_obras_previas,
          (select count(*) from actor_ev e where e.ruc_entidad = c.ruc_entidad and e.cuaderno_id <> p.cuaderno_id and e.onset < p.t) as actor_entidad_atrasos_previos
        from panel p join cua c using (cuaderno_id)
        """
    )

    # Atributos estaticos (fijados al inicio): cuaderno, MEF (solo campos no actualizables) y SEACE original.
    con.sql(
        f"""
        create table f_est as
        select c.cuaderno_id,
          c.es_consorcio::int as est_es_consorcio, c.n_miembros as est_n_miembros_consorcio,
          c.dep_code as est_dep_code, (c.dep_code = '04')::int as est_arequipa,
          c.cui is not null as est_tiene_cui, c.link_method as est_link_method,
          m.nivel as est_nivel_gobierno,
          case when m.funcion='SANEAMIENTO' or (m.funcion='SALUD Y SANEAMIENTO' and m.programa ilike '%SANEAMIENTO%') then 'SANEAMIENTO'
               when m.funcion='TRANSPORTE' then 'TRANSPORTE' when m.funcion ilike 'EDUCACI%' then 'EDUCACION'
               when m.funcion in ('SALUD','SALUD Y SANEAMIENTO') then 'SALUD'
               when m.funcion in ('AGROPECUARIA','AGRARIA') then 'AGROPECUARIA'
               when m.funcion is null then 'SIN_CUI' else 'OTROS' end as est_sector,
          m.tipo_inversion as est_tipo_inversion, m.marco as est_marco,
          ln(1 + m.monto_viable) as est_log_monto_viable,
          case when upper(c.entidad) like 'MUNICIPALIDAD DISTRITAL%' then 'MUNI_DISTRITAL'
               when upper(c.entidad) like 'MUNICIPALIDAD PROVINCIAL%' then 'MUNI_PROVINCIAL'
               when upper(c.entidad) like 'GOBIERNO REGIONAL%' or upper(c.entidad) like 'REGION %' then 'GOB_REGIONAL'
               when upper(c.entidad) like 'PROGRAMA%' or upper(c.entidad) like 'PROYECTO ESPECIAL%' or upper(c.entidad) like 'FONDO%' then 'PROGRAMA_NACIONAL'
               when upper(c.entidad) like 'MINISTERIO%' then 'MINISTERIO'
               else 'OTRA' end as est_tipo_entidad,
          ln(1 + s.monto_contratado) as est_log_monto_contratado,
          s.plazo_vigencia_dias as est_plazo_vigencia_dias,
          s.monto_contratado is not null as est_tiene_seace,
          case when ib.plazo_de_ejecucion_en_dias > 0 then ib.plazo_de_ejecucion_en_dias end as ib_plazo_original_dias,
          ln(1 + nullif(ib.monto_del_contrato_en_soles, 0)) as ib_log_monto_contrato,
          ib.fecha_de_inicio_de_obra::date as _ib_inicio
        from cua c
        left join {_p(STAGING / 'mef_inversiones.parquet')} m on m.cui = c.cui
        left join (
          select n_cod_contrato, max(try_cast(monto_contratado_total as double)) monto_contratado,
                 max(date_diff('day', try_cast(fecha_vigencia_inicial as date), try_cast(fecha_vigencia_final as date))) plazo_vigencia_dias
          from {_p(STAGING / 'seace_contratos.parquet')} group by 1
        ) s on s.n_cod_contrato = c.contrato_id
        left join {_p(CURATED / 'link_cuaderno_infobras.parquet')} li on li.cuaderno_id = c.cuaderno_id
        left join {_p(STAGING / 'infobras_obras.parquet')} ib on ib.codigo_infobras = li.codigo_infobras
        """
    )

    # SIAF: devengado mensual por CUI; en T se usa hasta el mes anterior (rezago 1 mes).
    con.sql(
        f"""create table siaf as select cui, make_date(anio, mes, 1) mes_ini, monto_devengado dev
            from read_parquet('{(STAGING / 'siaf').as_posix()}/*.parquet') where mes between 1 and 12"""
    )
    con.sql(
        f"""create table pia as select cui, anio, sum(monto_pia) pia
            from read_parquet('{(STAGING / 'siaf').as_posix()}/*.parquet') where mes = 0 group by all"""
    )
    con.sql(
        f"""
        create table f_siaf as
        select p.cuaderno_id, p.t,
          sum(s.dev) as siaf_dev_acum,
          sum(s.dev) filter (where s.mes_ini >= date_trunc('month', p.t) - interval 3 month) as siaf_dev_3m,
          sum(s.dev) filter (where year(s.mes_ini) = year(p.t)) as siaf_dev_ytd,
          date_diff('month', max(s.mes_ini) filter (where s.dev > 0), date_trunc('month', p.t)) as siaf_meses_desde_ultimo_dev
        from panel p join cua c using (cuaderno_id)
        join siaf s on s.cui = c.cui and s.mes_ini < date_trunc('month', p.t)
        group by p.cuaderno_id, p.t
        """
    )
    con.sql(
        """create table f_pia as select p.cuaderno_id, p.t, pia.pia as siaf_pia_anio
           from panel p join cua c using (cuaderno_id) join pia on pia.cui = c.cui and pia.anio = year(p.t)"""
    )

    # Seguimiento MEF (F12B, estado situacional) registrado hasta T.
    con.sql(
        f"""
        create table f_mef as
        select p.cuaderno_id, p.t,
          count(*) filter (where e.fecha_registro::date > p.t - 180) as mefseg_registros_180d,
          count(*) filter (where e.fecha_registro::date > p.t - 180 and e.tipo_registro ilike 'PROBLEMA%') as mefseg_problemas_180d,
          count(*) filter (where e.fecha_registro::date > p.t - 180 and e.tipo_registro ilike '%Atrasos%paraliza%') as mefseg_problema_atraso_180d
        from panel p join cua c using (cuaderno_id)
        join {_p(STAGING / 'mef_estado_situacional.parquet')} e on e.cui = c.cui and e.fecha_registro::date <= p.t
        group by p.cuaderno_id, p.t
        """
    )

    df = con.sql(
        """
        select p.cuaderno_id, p.t as "T", a.* exclude (cuaderno_id, t, _f_inicio_plazo),
          case when a._f_inicio_plazo is not null then p.t - a._f_inicio_plazo end as asi_dias_desde_inicio_plazo,
          month(p.t) as tmp_mes,
          (p.t >= date '2025-04-22')::int as tmp_vigencia_ley32069,
          e.* exclude (cuaderno_id, _ib_inicio),
          case when e._ib_inicio <= p.t and e.ib_plazo_original_dias > 0 then (p.t - e._ib_inicio) / e.ib_plazo_original_dias end as ib_frac_plazo_transcurrido,
          case when e._ib_inicio <= p.t and e.ib_plazo_original_dias > 0 then e._ib_inicio + e.ib_plazo_original_dias::int - p.t end as ib_dias_para_fin_programado,
          ac.* exclude (cuaderno_id, t),
          s.* exclude (cuaderno_id, t), pi.siaf_pia_anio,
          m.* exclude (cuaderno_id, t)
        from panel p
        left join f_asi a using (cuaderno_id, t)
        left join f_est e using (cuaderno_id)
        left join f_actor ac using (cuaderno_id, t)
        left join f_siaf s using (cuaderno_id, t)
        left join f_pia pi using (cuaderno_id, t)
        left join f_mef m using (cuaderno_id, t)
        """
    ).df()
    df["T"] = pd.to_datetime(df["T"])
    # ratios derivados (solo de columnas ya disponibles en T)
    df["asi_consultas_pendientes"] = df["asi_cum_consultas"] - df["asi_cum_respuestas_consultas"]
    df["asi_ritmo_30d_vs_90d"] = df["asi_n_30d"] / (df["asi_n_90d"] / 3).where(df["asi_n_90d"] > 0)
    viable = df["est_log_monto_viable"].pipe(lambda s: (2.718281828 ** s) - 1)
    df["siaf_dev_acum_sobre_viable"] = df["siaf_dev_acum"] / viable.where(viable > 0)
    df["siaf_dev_ytd_sobre_pia"] = df["siaf_dev_ytd"] / df["siaf_pia_anio"].where(df["siaf_pia_anio"] > 0)
    for c in ("asi_dias_desde_ultimo", "asi_dias_desde_primero", "asi_dias_desde_inicio_plazo"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    dst = out / "features_structured.parquet"
    df.to_parquet(dst, index=False)
    log.info("features estructuradas: %s filas x %s columnas", *df.shape)
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build()
