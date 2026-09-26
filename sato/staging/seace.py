"""Staging de contratos SEACE publicados en CONOSCE (OECE).

Fuente: https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/contratos/AAAA/CONOSCE_CONTRATOSAAAA_0.xlsx
Hallazgos verificados:
  * N_COD_CONTRATO coincide exactamente con IDENTIFICADOR_DEL_CONTRATO de los
    cuadernos de obra digital (llave deterministica).
  * Cobertura incompleta desde 2021 (~10 mil contratos/anio).
  * El archivo de un mismo anio puede regenerarse con distinto numero de filas
    (2024: 10 988 -> 9 666 filas el 2026-09-25). Por eso cada descarga se
    registra con SHA-256 en data/raw/manifest.jsonl.
Uso permitido como feature: solo monto contratado y vigencia ORIGINALES
(fijados a la firma). Monto adicional y fin de vigencia actualizado son fotos
posteriores y estan prohibidos (leakage).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from sato.config import RAW, STAGING

log = logging.getLogger(__name__)


def stage(raw: Path = RAW / "seace", out: Path = STAGING) -> Path:
    frames = []
    for f in sorted(raw.glob("CONOSCE_CONTRATOS*.xlsx")):
        d = pd.read_excel(f, engine="calamine", dtype=str)
        d.columns = [c.lower().strip() for c in d.columns]  # OECE alterna mayusculas/minusculas entre versiones
        frames.append(d.assign(archivo=f.name))
    df = pd.concat(frames, ignore_index=True)
    dst = out / "seace_contratos.parquet"
    df.to_parquet(dst, index=False)
    log.info("SEACE contratos: %s filas, %s contratos", len(df), df["n_cod_contrato"].nunique())
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stage()
