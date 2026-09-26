"""Orquestador reproducible del pipeline completo de SATO-AQP.

    python -m sato.pipeline all              # todo, en orden
    python -m sato.pipeline <paso> [<paso>]  # pasos individuales

Pasos (cada uno es idempotente: re-ejecutarlo sobreescribe su salida):
  ingest        descarga fuentes oficiales -> data/raw (+ manifest.jsonl con SHA-256)
  staging       normaliza cada fuente -> data/staging (Parquet)
  integration   resolucion de entidades y tablas curadas -> data/curated
  features      panel obra-mes, features estructuradas, texto, extraccion -> data/features
  embeddings    embeddings Sentence-BERT por asiento (GPU recomendada; ~40 min en RTX 4060 Ti)
  experiments   grilla experimental + rolling-origin + comparacion A/B -> artifacts/experiments
  release       modelo operativo, backtest as-of, SHAP y evidencia -> artifacts/release
  load          carga PostgreSQL (DATABASE_URL)

No hay orquestador externo (Airflow/Prefect/Dagster): el volumen (~3 GB brutos,
actualizacion mensual) no lo justifica; un job programado mensual que ejecute
`python -m sato.pipeline all` es suficiente (ver docs/architecture/ARCHITECTURE.md).
"""

from __future__ import annotations

import logging
import sys
import time

log = logging.getLogger("sato.pipeline")


def ingest():
    from sato.ingest import download

    for fn in download.STEPS.values():
        fn()


def staging():
    from sato.staging import contraloria, infobras, mef, oece, seace, siaf

    for k in ("cuadernos", "valorizaciones", "asientos"):
        oece.stage(k)
    mef.stage_inversiones()
    mef.stage_estado_situacional()
    siaf.stage_all()
    infobras.stage()
    contraloria.stage()
    seace.stage()


def integration():
    from sato.integration import cuadernos, linkage

    linkage.build()
    cuadernos.build()
    linkage.build_infobras_link()


def features():
    from sato.features import extraction, panel, structured, text

    panel.build()
    structured.build()
    text.build_lexicon()
    text.build_lsa()
    extraction.extract_all()
    extraction.build_features()
    from sato.config import FEATURES

    if (FEATURES / "asiento_embeddings.npy").exists():
        text.build_emb()
    else:
        log.warning("no hay embeddings: ejecutar el paso 'embeddings' y luego 'features'")


def embeddings():
    from sato.features import text

    text.embed_asientos()
    text.build_emb()


def experiments():
    from sato.models import compare, grid

    grid.main_grid()
    grid.rolling()
    compare.compare()


def release():
    from sato.serving import release as r

    r.build(feature_set="B_full", H=60)


def load():
    from sato.serving import load_db

    load_db.load()
    load_db.ensure_admin()


STEPS = dict(ingest=ingest, staging=staging, integration=integration, features=features, embeddings=embeddings,
             experiments=experiments, release=release, load=load)
ALL = ["ingest", "staging", "integration", "features", "embeddings", "experiments", "release", "load"]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    steps = sys.argv[1:] or ["all"]
    if steps == ["all"]:
        steps = ALL
    for s in steps:
        t0 = time.time()
        log.info("=== paso %s ===", s)
        STEPS[s]()
        log.info("=== paso %s listo en %.0f s ===", s, time.time() - t0)
