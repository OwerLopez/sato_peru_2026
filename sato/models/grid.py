"""Grilla experimental completa de la tesis (reproducible con un solo comando).

    python -m sato.models.grid            # grilla principal
    python -m sato.models.grid rolling    # evaluacion rolling-origin

Conjuntos de features:
  A              : estructurado (asientos tipificados, estatico, actores, SIAF, MEF, INFOBRAS inicio)
  A_sin_ib       : A sin atributos INFOBRAS (ablacion de riesgo de leakage)
  A_asientos     : solo metadatos de asientos (tipos/actividad) + tiempo
  B_lex          : A + lexico de dominio
  B_lex_sinproxy : A + lexico sin la categoria proxy_80
  B_ie           : A + extraccion de avances reportados (IE)
  B_lsa          : A + LSA (TF-IDF + SVD)
  B_emb          : A + embeddings Sentence-BERT (PCA)
  B_stack_tfidf  : A + score supervisado as-of sobre TF-IDF
  B_stack_emb    : A + score supervisado as-of sobre embeddings
  B_full         : A + lexico + IE + scores as-of (TF-IDF y embeddings)
  B_full_sinproxy: B_full sin lexico proxy_80 ni IE (mide aporte "no proxy")
"""

from __future__ import annotations

import json
import logging
import sys

import pandas as pd

from sato.config import ARTIFACTS
from sato.models.experiment import Config, run

log = logging.getLogger(__name__)

LEX, LSA, EMB, IE = "features_text_lexicon.parquet", "features_text_lsa.parquet", "features_text_emb.parquet", "features_text_ie.parquet"
TFW, EMW = "text_window_tfidf.npz", "text_window_emb.npy"

FEATURE_SETS = {
    "A": dict(),
    "A_sin_ib": dict(exclude_prefixes=("ib_",)),
    "A_asientos": dict(exclude_prefixes=("est_", "actor_", "siaf_", "mefseg_", "ib_")),
    "B_lex": dict(extra_feature_files=(LEX,)),
    "B_lex_sinproxy": dict(extra_feature_files=(LEX,), exclude_prefixes=("txt_lx_proxy_80",)),
    "B_ie": dict(extra_feature_files=(IE,)),
    "B_lsa": dict(extra_feature_files=(LSA,)),
    "B_emb": dict(extra_feature_files=(EMB,)),
    "B_stack_tfidf": dict(text_stack=(TFW,)),
    "B_stack_emb": dict(text_stack=(EMW,)),
    "B_full": dict(extra_feature_files=(LEX, IE), text_stack=(TFW, EMW)),
    "B_full_sinproxy": dict(extra_feature_files=(LEX,), text_stack=(TFW, EMW), exclude_prefixes=("txt_lx_proxy_80",)),
}
ALL_MODELS = ("regla", "logreg", "rf", "lgbm", "xgb")


def main_grid():
    rows = []
    for target in ("atraso", "disrupcion"):
        for H in (30, 60, 90):
            for fs, kw in FEATURE_SETS.items():
                core = fs in ("A", "B_full")
                if target == "disrupcion" and fs not in ("A", "B_full", "B_full_sinproxy"):
                    continue
                scopes = ("nacional", "arequipa") if core else ("nacional",)
                for scope in scopes:
                    models = ALL_MODELS if core else ("lgbm",)
                    cfg = Config(target=target, H=H, feature_set=fs, train_scope=scope, models=models, n_boot=500,
                                 save_model=(core and scope == "nacional"), **kw)
                    try:
                        r = run(cfg)
                    except Exception as e:  # se registra y continua; nunca se inventa un resultado
                        log.exception("fallo %s", cfg)
                        rows.append(dict(target=target, H=H, feature_set=fs, train_scope=scope, error=str(e)))
                        continue
                    for m, v in r["modelos"].items():
                        for ts in ("arequipa", "nacional"):
                            rows.append(dict(target=target, H=H, feature_set=fs, train_scope=scope, modelo=m, test_scope=ts,
                                             valid_pr_auc=v["valid_pr_auc"], **{k: v[ts][k] for k in v[ts]}))
                    pd.DataFrame(rows).to_csv(ARTIFACTS / "experiments" / "grid_resultados.csv", index=False)
    return pd.DataFrame(rows)


def rolling():
    rows = []
    for H in (30, 60, 90):
        for origin in ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"):
            for fs in ("A", "B_full"):
                cfg = Config(target="atraso", H=H, feature_set=fs, models=("lgbm",), n_boot=200, test_start=origin,
                             test_months=3, **FEATURE_SETS[fs])
                try:
                    r = run(cfg)
                except Exception as e:
                    log.exception("fallo %s", cfg)
                    continue
                v = r["modelos"]["lgbm"]
                for ts in ("arequipa", "nacional"):
                    rows.append(dict(H=H, origen=origin, feature_set=fs, test_scope=ts, **{k: v[ts][k] for k in ("n", "positivos", "pr_auc", "roc_auc", "recall", "precision")}))
                pd.DataFrame(rows).to_csv(ARTIFACTS / "experiments" / "rolling_resultados.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    (ARTIFACTS / "experiments").mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "rolling":
        rolling()
    else:
        main_grid()
