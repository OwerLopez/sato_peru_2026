"""Staging del dataset de Obras Publicas de INFOBRAS (Contraloria General de la Republica).

Fuente: https://infobras.contraloria.gob.pe/InfobrasWeb/DataSets
El XLSX es una FOTO a la fecha de consulta (una fila por obra). Por ello sus
campos variables (avance, paralizacion, modificaciones, fin real) NO pueden
usarse como features a una fecha T anterior a la consulta: solo sirven para
atributos fijados al inicio de la obra, para etiquetas retrospectivas y para
validacion externa. Ver docs/methodology/LEAKAGE_POLICY.md.

Particularidades verificadas:
  * 3 filas de titulo antes de la cabecera (fila 4).
  * decimales exportados con espacio como separador ("1205287 56").
  * fechas dd/mm/aaaa; "0" o vacio significan dato no registrado.
  * columnas con el mismo nombre (contrato de ejecucion vs supervision).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from sato.config import RAW, STAGING

log = logging.getLogger(__name__)

NUMERIC = [
    "n_de_veedurias_ciudadanas", "n_informes_de_control", "n_comentarios_ciudadanos",
    "monto_viable_aprobado", "costo_actualizado_de_la_inversion", "n_obras_pertenecientes_a_la_inversion",
    "costo_de_obra_segun_expediente_tecnico", "tasa_de_cambio", "costo_de_obra_en_soles_segun_et_en_soles",
    "monto_del_contrato_en_soles", "monto_del_contrato_en_soles_1", "plazo_de_ejecucion_en_dias",
    "porcentaje_de_terreno_entregado", "ano_de_avance", "mes_de_avance",
    "avance_fisico_programado_acumulado", "avance_fisico_real_acumulado",
    "monto_de_valorizacion_programado_acumulado", "monto_de_valorizacion_ejecutado_acumulado",
    "porcentaje_de_ejecucion_financiera", "monto_de_ejecucion_financiera_de_la_obra",
    "numero_de_dias_paralizado", "n_de_modificaciones", "n_dias_de_modificaciones_de_plazo",
    "nuevo_plazo_de_ejecucion_en_dias", "n_de_controversias", "n_de_adicionales_de_obra",
    "monto_de_adicionales_de_obra_en_soles", "n_de_adicionales_de_supervision",
    "monto_de_adicionales_de_supervision_en_soles", "n_de_deductivos_de_obra", "monto_de_deductivos_de_obra_en_soles",
    "n_de_deductivos_de_supervision", "monto_de_deductivos_de_supervision_en_soles", "costo_de_la_obra_en_soles",
    "ano_de_primer_devengado", "monto_total_devengado_del_proyecto",
]
DATES = [
    "fecha_de_aprobacion_del_expediente", "fecha_inicio_supervision", "fecha_fin_supervision",
    "fecha_inicio_de_labores", "fecha_fin_de_labores", "fecha_de_inicio_de_obra",
    "fecha_finalizacion_programada_de_obra", "fecha_de_entrega_del_terreno", "fecha_de_registro_de_avance",
    "fecha_de_paralizacion", "fecha_finalizacion_reprogramada_de_obra", "fecha_de_finalizacion_real",
    "fecha_de_recepcion", "fecha_de_aprobacion_de_liquidacion_de_obra", "fecha_de_transferencia",
]
TEXT_NORMALIZE = ["departamento", "provincia", "distrito"]


def norm_col(c: str) -> str:
    c = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", c).strip("_")


def strip_accents_upper(s):
    if not isinstance(s, str):
        return s
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper().strip()


def parse_number(s: pd.Series) -> pd.Series:
    x = s.astype("string").str.strip()
    # "1205287 56" -> "1205287.56" ; el espacio es separador decimal en la exportacion
    x = x.str.replace(r"^(-?\d+) (\d{1,2})$", r"\1.\2", regex=True)
    return pd.to_numeric(x, errors="coerce")


def parse_date(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s.astype("string").str.strip(), format="%d/%m/%Y", errors="coerce")
    # fechas imposibles (< 1990 o > 2100) se consideran no registradas
    return d.where((d.dt.year >= 1990) & (d.dt.year <= 2100))


def stage(xlsx: Path | None = None, out: Path = STAGING) -> Path:
    if xlsx is None:
        xlsx = sorted((RAW / "infobras").glob("DataSet-Obras-Publicas_*.xlsx"))[-1]
    fecha_consulta = re.search(r"(\d{4}-\d{2}-\d{2})", xlsx.name).group(1)
    df = pd.read_excel(xlsx, engine="calamine", header=3, dtype=str)
    cols, seen = [], {}
    for c in df.columns:
        n = norm_col(c)
        if n in seen:
            seen[n] += 1
            n = f"{n}_{seen[n]}"
        else:
            seen[n] = 0
        cols.append(n)
    df.columns = cols
    for c in NUMERIC:
        df[c] = parse_number(df[c])
    for c in DATES:
        df[c] = parse_date(df[c])
    for c in TEXT_NORMALIZE:
        df[c] = df[c].map(strip_accents_upper)
    df["codigo_unico_de_inversion"] = df["codigo_unico_de_inversion"].astype("string").str.strip().replace({"0": pd.NA, "": pd.NA})
    df["codigo_infobras"] = df["codigo_infobras"].astype("string").str.strip()
    df["ruc_ejecucion"] = df["ruc_ejecucion"].astype("string").str.strip().replace({"": pd.NA})
    df["fecha_consulta"] = pd.Timestamp(fecha_consulta)
    df = df.replace({np.nan: None})
    dst = out / "infobras_obras.parquet"
    df.to_parquet(dst, index=False)
    log.info("INFOBRAS %s filas -> %s", len(df), dst)
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stage()
