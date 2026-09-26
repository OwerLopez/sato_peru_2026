"""Rutas y constantes compartidas por todo el pipeline."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("SATO_ROOT", Path(__file__).resolve().parents[1]))
DATA = Path(os.environ.get("SATO_DATA", ROOT / "data"))
RAW = DATA / "raw"
STAGING = DATA / "staging"
CURATED = DATA / "curated"
FEATURES = DATA / "features"
ARTIFACTS = Path(os.environ.get("SATO_ARTIFACTS", ROOT / "artifacts"))

# Departamento de estudio (codigo INEI de ubigeo = primeros 2 digitos).
DEPARTAMENTO = "AREQUIPA"
UBIGEO_DEP = "04"
PROVINCIAS = [
    "AREQUIPA",
    "CAMANA",
    "CARAVELI",
    "CASTILLA",
    "CAYLLOMA",
    "CONDESUYOS",
    "ISLAY",
    "LA UNION",
]

for _p in (RAW, STAGING, CURATED, FEATURES, ARTIFACTS):
    _p.mkdir(parents=True, exist_ok=True)
