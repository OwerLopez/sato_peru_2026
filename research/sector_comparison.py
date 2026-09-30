"""Comparacion real de sectores para Arequipa con todas las fuentes integradas.

Salida: docs/research/sector_comparison.csv y .md
Sector: FUNCION del Banco de Inversiones (MEF) del CUI; para la funcion
historica "SALUD Y SANEAMIENTO" (SNIP) se usa el PROGRAMA. Las obras sin CUI
enlazable se reportan como "SIN CUI".
"""

import duckdb
import pandas as pd

from sato.config import CURATED, ROOT, STAGING

con = duckdb.connect()
def P(p):
    return f"'{p.as_posix()}'"

con.sql(
    f"""
create table mef as select cui, funcion, programa, departamento, fuente,
  case
    when funcion = 'SANEAMIENTO' then 'SANEAMIENTO'
    when funcion = 'SALUD Y SANEAMIENTO' and programa ilike '%SANEAMIENTO%' then 'SANEAMIENTO'
    when funcion = 'SALUD Y SANEAMIENTO' then 'SALUD'
    when funcion = 'TRANSPORTE' then 'TRANSPORTE'
    when funcion ilike 'EDUCACI%' then 'EDUCACION'
    when funcion = 'SALUD' then 'SALUD'
    when funcion in ('AGROPECUARIA','AGRARIA') then 'AGROPECUARIA'
    else 'OTROS' end sector
from {P(STAGING / "mef_inversiones.parquet")}
"""
)
con.sql(
    f"""
create table ib as select i.*, coalesce(m.sector, case when i.codigo_unico_de_inversion is null then 'SIN CUI' else 'OTROS' end) sector,
  m.cui is not null en_mef
from {P(STAGING / "infobras_obras.parquet")} i left join mef m on m.cui = i.codigo_unico_de_inversion
where i.departamento = 'AREQUIPA'
"""
)
con.sql(
    f"create table par as select distinct cui, codigo_infobras from {P(STAGING / 'contraloria_paralizadas.parquet')} where departamento='AREQUIPA'"
)
con.sql(
    f"""
create table cua as select c.*, coalesce(m.sector, case when c.cui is null then 'SIN CUI' else 'OTROS' end) sector,
  (select count(distinct date_trunc('month', a.fecha)) from {P(CURATED / "asiento.parquet")} a where a.cuaderno_id = c.cuaderno_id) meses_con_asientos
from {P(CURATED / "cuaderno.parquet")} c left join mef m on m.cui = c.cui
where c.dep_code = '04'
"""
)
con.sql(f"""create table val as select distinct IDENTIFICADOR_DEL_CONTRATO contrato_id from {P(STAGING / "oece_valorizaciones.parquet")}""")
con.sql(
    f"create table siaf as select cui, count(distinct anio*100+mes) meses_dev from read_parquet('{(STAGING / 'siaf').as_posix()}/*.parquet') where mes between 1 and 12 and monto_devengado > 0 group by 1"
)

rows = {}
sectors = ["SANEAMIENTO", "TRANSPORTE", "EDUCACION", "SALUD", "AGROPECUARIA", "OTROS", "SIN CUI"]


def put(name, sql):
    d = dict(con.sql(sql).fetchall())
    rows[name] = [int(d.get(s, 0)) for s in sectors]


put(
    "Inversiones MEF en Arequipa (activas+cerradas)",
    "select sector, count(*) from mef where departamento='AREQUIPA' and fuente in ('ACTIVO','CERRADO') group by 1",
)
put("Obras INFOBRAS en Arequipa", "select sector, count(*) from ib group by 1")
put("Obras INFOBRAS con CUI", "select sector, count(*) from ib where codigo_unico_de_inversion is not null group by 1")
put("Obras INFOBRAS con CUI en Banco de Inversiones", "select sector, count(*) from ib where en_mef group by 1")
put(
    "Obras INFOBRAS por contrata (con RUC ejecutor)",
    "select sector, count(*) from ib where modalidad_de_ejecucion_de_la_obra ilike 'Contrata%' and ruc_ejecucion is not null group by 1",
)
put("Obras INFOBRAS con avance registrado", "select sector, count(*) from ib where avance_fisico_real_acumulado > 0 group by 1")
put("Obras INFOBRAS con informes de control", "select sector, count(*) from ib where n_informes_de_control > 0 group by 1")
put("Obras INFOBRAS con paralizacion registrada", "select sector, count(*) from ib where existe_paralizacion = 'Si' group by 1")
put(
    "Obras en panel Contraloria de paralizadas (2023-09..2026-06)",
    "select sector, count(*) from ib where codigo_infobras in (select codigo_infobras from par) group by 1",
)
put(
    "Obras INFOBRAS con CUI con devengado SIAF 2020-2026",
    "select sector, count(*) from ib where codigo_unico_de_inversion in (select cui from siaf) group by 1",
)
put("Cuadernos de obra digital (OECE, 2024-2026)", "select sector, count(*) from cua where tiene_metadatos group by 1")
put("Cuadernos con asientos", "select sector, count(*) from cua where n_asientos > 0 group by 1")
put("Cuadernos con valorizaciones OECE", "select sector, count(*) from cua where contrato_id in (select contrato_id from val) group by 1")
put("Cuadernos con historia completa", "select sector, count(*) from cua where historia_completa group by 1")
put(
    "Cuadernos con historia completa y >= 3 meses con asientos",
    "select sector, count(*) from cua where historia_completa and meses_con_asientos >= 3 group by 1",
)
put(
    "Cuadernos con evento de atraso normativo (art. 203/207)",
    "select sector, count(*) from cua where f_valorizacion_menor_80 is not null or f_calendario_acelerado is not null group by 1",
)
put("Cuadernos con suspension del plazo", "select sector, count(*) from cua where f_suspension_plazo is not null group by 1")
put("Cuadernos con resolucion de contrato", "select sector, count(*) from cua where f_resolucion_contrato is not null group by 1")
put(
    "Cuadernos integrables (CUI + MEF + INFOBRAS)",
    f"select sector, count(*) from cua where cui in (select codigo_unico_de_inversion from {P(STAGING / 'infobras_obras.parquet')}) group by 1",
)
put(
    "Cuadernos utilizables para ML (historia completa, >=3 meses)",
    "select sector, count(*) from cua where historia_completa and meses_con_asientos >= 3 group by 1",
)
put(
    "  ...de ellos con evento de atraso normativo",
    "select sector, count(*) from cua where historia_completa and meses_con_asientos >= 3 and (f_valorizacion_menor_80 is not null or f_calendario_acelerado is not null) group by 1",
)

df = pd.DataFrame(rows, index=sectors).T
df["TOTAL"] = df.sum(axis=1)
out = ROOT / "docs" / "research"
df.to_csv(out / "sector_comparison.csv")
(out / "sector_comparison.md").write_text(df.to_markdown(), encoding="utf-8")
print(df.to_string())
