"""Comparacion pareada Modelo A vs variantes del Modelo B (experimento central).

Para cada objetivo, horizonte y alcance de test se unen las predicciones de test
(mismas filas obra-mes) de LightGBM entrenado con A y con cada variante B, y se
estima con bootstrap por obra (1000 remuestreos de obras completas) la
diferencia de PR-AUC y ROC-AUC, su IC 95% y un p-valor de una cola
(proporcion de remuestreos con diferencia <= 0).

    python -m sato.models.compare
"""

from __future__ import annotations

import logging

import pandas as pd

from sato.config import ARTIFACTS
from sato.models.evaluate import cluster_bootstrap

log = logging.getLogger(__name__)
EXP = ARTIFACTS / "experiments"


def load_preds(target, H, fs, scope="nacional", model="lgbm"):
    d = EXP / f"{target}_H{H}_{fs}_train-{scope}" / "predicciones_test.parquet"
    if not d.exists():
        return None
    p = pd.read_parquet(d)
    return p[["cuaderno_id", "T", "dep_code", "y", f"s_{model}"]].rename(columns={f"s_{model}": fs})


def compare(n_boot: int = 1000) -> pd.DataFrame:
    rows = []
    for target in ("atraso", "disrupcion"):
        for H in (30, 60, 90):
            base = load_preds(target, H, "A")
            if base is None:
                continue
            variants = [v for v in ("A_sin_ib", "A_asientos", "B_lex", "B_lex_sinproxy", "B_ie", "B_lsa", "B_emb", "B_stack_tfidf",
                                    "B_stack_emb", "B_full", "B_full_sinproxy") if load_preds(target, H, v) is not None]
            for v in variants:
                d = base.merge(load_preds(target, H, v)[["cuaderno_id", "T", v]], on=["cuaderno_id", "T"])
                for ts, m in (("arequipa", d["dep_code"] == "04"), ("nacional", pd.Series(True, index=d.index))):
                    b = cluster_bootstrap(d[m], ["A", v], n_boot=n_boot)
                    diff = b[b["score"] == f"{v} - A"].set_index("metrica")
                    base_m = b[b["score"] == "A"].set_index("metrica")
                    var_m = b[b["score"] == v].set_index("metrica")
                    for met in ("pr", "roc"):
                        rows.append(dict(target=target, H=H, variante=v, test_scope=ts, metrica=met,
                                         A=base_m.loc[met, "media"], B=var_m.loc[met, "media"],
                                         diferencia=diff.loc[met, "media"], ic_inf=diff.loc[met, "ic_inf"], ic_sup=diff.loc[met, "ic_sup"],
                                         p_valor=diff.loc[met, "p_valor_una_cola"], filas=int(m.sum()), obras=int(d.loc[m, "cuaderno_id"].nunique())))
                log.info("%s H=%s %s listo", target, H, v)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / "comparacion_A_vs_B.csv", index=False)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(compare().to_string())
