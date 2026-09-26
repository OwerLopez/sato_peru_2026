"""Valida el extractor de avances (sato/features/extraction.py) contra el dataset
oficial de Valorizaciones de OECE (avance fisico acumulado ejecutado/programado).

Emparejamiento: contrato (IDENTIFICADOR_DEL_CONTRATO = contrato del cuaderno) y
periodo de valorizacion (mes). Se toman los asientos del cuaderno registrados entre
el ultimo dia del periodo y +20 dias (plazo tipico de anotacion de la valorizacion)
con valores extraidos; se compara el valor mas cercano al oficial y el primero.
Salida: docs/research/validacion_extraccion.json
"""

import json

import duckdb
import numpy as np
import pandas as pd

from sato.config import CURATED, FEATURES, ROOT, STAGING
from sato.features.extraction import extract_all

MESES = {m: i for i, m in enumerate(["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], 1)}
MESES["SEPTIEMBRE"] = 9

extract_all()
con = duckdb.connect()
val = con.sql(f"""select IDENTIFICADOR_DEL_CONTRATO contrato_id, PERIODO_DE_VALORIZACION per,
   try_cast(replace(AVANCE_FISICO_ACUMULADO_EJECUTADO, ',', '.') as double) of_ejec,
   try_cast(replace(AVANCE_FISICO_ACUMULADO_PROGRAMADO, ',', '.') as double) of_prog
 from '{(STAGING / 'oece_valorizaciones.parquet').as_posix()}'
 where DESCRIPCION_DEL_IDENTIFICADOR_DEL_TIPO_VALORIZACION ilike 'Obra principal'""").df()
p = val["per"].str.upper().str.split()
val["fin"] = [pd.Timestamp(int(x[1]), MESES[x[0]], 1) + pd.offsets.MonthEnd(0) if len(x) == 2 and x[0] in MESES else pd.NaT for x in p]
val = val.dropna(subset=["fin"]).drop_duplicates(["contrato_id", "fin"])
cua = pd.read_parquet(CURATED / "cuaderno.parquet", columns=["cuaderno_id", "contrato_id"]).dropna()
ie = pd.read_parquet(FEATURES / "asiento_extraccion.parquet")
ie["fecha"] = pd.to_datetime(ie["fecha"])
m = val.merge(cua, on="contrato_id").merge(ie, on="cuaderno_id")
m = m[(m["fecha"] >= m["fin"] - pd.Timedelta(days=3)) & (m["fecha"] <= m["fin"] + pd.Timedelta(days=20))]

res = {"valorizaciones_oficiales_con_cuaderno": int(val.merge(cua, on="contrato_id")[["contrato_id", "fin"]].drop_duplicates().shape[0])}
for k in ("ejec", "prog"):
    d = m.dropna(subset=[f"ie_{k}", f"of_{k}"]).copy()
    d["err"] = (d[f"ie_{k}"] - d[f"of_{k}"]).abs()
    first = d.sort_values("fecha").groupby(["contrato_id", "fin"]).head(1)
    res[k] = {
        "pares_valorizacion_con_valor_extraido": int(first.shape[0]),
        "exactitud_primer_valor_1pp": float((first["err"] <= 1.0).mean()),
        "exactitud_primer_valor_0_1pp": float((first["err"] <= 0.1).mean()),
        "error_absoluto_mediano_pp": float(first["err"].median()),
    }
res["cobertura_ejec"] = res["ejec"]["pares_valorizacion_con_valor_extraido"] / max(1, res["valorizaciones_oficiales_con_cuaderno"])
out = ROOT / "docs" / "research" / "validacion_extraccion.json"
out.write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
