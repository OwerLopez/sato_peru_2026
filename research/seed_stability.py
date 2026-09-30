"""Variabilidad por semilla de entrenamiento (LightGBM) de A y B_full, H=60, entrenamiento nacional."""

import logging

import pandas as pd

from sato.config import ARTIFACTS
from sato.models.experiment import Config, run
from sato.models.grid import FEATURE_SETS

logging.basicConfig(level=logging.WARNING)
rows = []
for seed in (1, 2, 3, 4, 5):
    for fs in ("A", "B_full"):
        r = run(Config(H=60, feature_set=fs, models=("lgbm",), seed=seed, n_boot=50, tag=f"seed{seed}", **FEATURE_SETS[fs]))
        m = r["modelos"]["lgbm"]
        for ts in ("arequipa", "nacional"):
            rows.append(dict(seed=seed, feature_set=fs, test_scope=ts, pr_auc=m[ts]["pr_auc"], roc_auc=m[ts]["roc_auc"]))
df = pd.DataFrame(rows)
df.to_csv(ARTIFACTS / "experiments" / "estabilidad_semillas.csv", index=False)
print(df.groupby(["test_scope", "feature_set"])[["pr_auc", "roc_auc"]].agg(["mean", "std", "min", "max"]).round(4).to_string())
