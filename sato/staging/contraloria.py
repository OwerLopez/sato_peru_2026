"""Staging de los cortes trimestrales de obras paralizadas (Contraloria).

Fuente: coleccion oficial "Obras paralizadas - documentos"
https://www.gob.pe/institucion/contraloria/colecciones/18230-obras-paralizadas-documentos
Cada informe trae un anexo XLSX con la base de datos de obras paralizadas a la
fecha de corte. Unirlos produce un panel oficial y FECHADO: una obra aparece en
el corte q si la Contraloria la registraba como paralizada a esa fecha.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from sato.config import RAW, STAGING
from sato.staging.infobras import norm_col

log = logging.getLogger(__name__)

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
PATTERN = re.compile(r"anexo-n-0?2-(base|reporte)|anexo-n-01-base-de-datos-con-la-lista", re.I)
KEEP = {
    "codigo_infobras": "codigo_infobras", "cui": "cui", "descripcion_obra": "descripcion_obra",
    "entidad": "entidad", "evento": "evento", "modalidad_de_ejecucion": "modalidad",
    "departamento": "departamento", "provincia": "provincia", "distrito": "distrito",
    "ano_inicio_obra": "anio_inicio_obra", "avance_fisico": "avance_fisico",
    "nivel_de_gobierno": "nivel_gobierno", "sector": "sector", "causal_paralizacion": "causal_paralizacion",
    "tipo_de_obra": "tipo_obra",
}


def corte_from_name(name: str) -> pd.Timestamp:
    n = name.lower()
    y = int(re.findall(r"(20\d{2})", n)[-1])
    m = next(v for k, v in MESES.items() if k in n)
    return pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)


def stage(raw: Path = RAW / "contraloria", out: Path = STAGING) -> Path:
    frames = []
    for f in sorted(raw.iterdir()):
        if not PATTERN.search(f.name) or "servicio" in f.name.lower() or f.suffix.lower() not in (".xlsx", ".xls"):
            continue
        if f.name.startswith("8489152"):  # informe junio 2026: el nombre del anexo no trae el mes
            corte = pd.Timestamp(2026, 6, 30)
        else:
            corte = corte_from_name(f.name)
        x = pd.ExcelFile(f, engine="calamine")
        head = x.parse(x.sheet_names[0], header=None, nrows=15)
        hr = next(i for i in range(15) if head.iloc[i].notna().sum() > 8)
        d = x.parse(x.sheet_names[0], header=hr, dtype=str)
        d.columns = [norm_col(c) for c in d.columns]
        d = d[[c for c in KEEP if c in d.columns]].rename(columns=KEEP)
        d = d[d["codigo_infobras"].notna() | d["cui"].notna()]
        d["fecha_corte"] = corte
        d["archivo"] = f.name
        frames.append(d)
        log.info("%s corte=%s filas=%s", f.name[:60], corte.date(), len(d))
    df = pd.concat(frames, ignore_index=True)
    df["cui"] = df["cui"].str.replace(r"\.0$", "", regex=True).str.strip()
    df["codigo_infobras"] = df["codigo_infobras"].str.replace(r"\.0$", "", regex=True).str.strip()
    df["avance_fisico"] = pd.to_numeric(df["avance_fisico"], errors="coerce")
    df["departamento"] = df["departamento"].str.upper().str.strip()
    dst = out / "contraloria_paralizadas.parquet"
    df.to_parquet(dst, index=False)
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stage()
