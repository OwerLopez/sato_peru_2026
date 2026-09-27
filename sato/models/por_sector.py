"""Desempeno de los modelos por sector / tipo de obra en sus conjuntos de prueba temporal (sin reentrenar).

Responde con datos a la pregunta de en que sectores la prediccion es mas confiable. Usa las predicciones de prueba ya
guardadas por los experimentos:
  * alerta a 60 dias (cuaderno digital): artifacts/experiments/atraso_H60_{A,B_full}_train-nacional/predicciones_test.parquet
  * cartera INFOBRAS al inicio y en seguimiento: artifacts/exante/predicciones_test_{y_30,seguimiento}.parquet
IC 95 % por bootstrap de obras (conglomerados). Solo se informan grupos con al menos 30 positivos y 30 negativos.

    python -m sato.models.por_sector      (requiere la BD cargada para el sector de los cuadernos)
Salida: artifacts/experiments/desempeno_por_sector.json y la clave `desempeno_sectores` en sato.configuracion.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import psycopg
from sklearn.metrics import average_precision_score, roc_auc_score

from sato.config import ARTIFACTS
from sato.serving.load_db import dsn

log = logging.getLogger(__name__)
OUT = ARTIFACTS / "experiments" / "desempeno_por_sector.json"
MIN_CLASE = 30


def _metricas(d: pd.DataFrame, score: str, grupo: str, n_boot: int = 300, seed: int = 7) -> dict | None:
    y = d["y"].to_numpy()
    if (y == 1).sum() < MIN_CLASE or (y == 0).sum() < MIN_CLASE:
        return None
    s = d[score].to_numpy()
    k = max(1, int(round(0.1 * len(d))))
    top = np.argsort(-s)[:k]
    out = {"filas": int(len(d)), "obras": int(d[grupo].nunique()), "positivos": int(y.sum()), "prevalencia": float(y.mean()),
           "roc_auc": float(roc_auc_score(y, s)), "pr_auc": float(average_precision_score(y, s)),
           "precision_top10": float(y[top].mean())}
    out["lift_top10"] = out["precision_top10"] / out["prevalencia"]
    rng = np.random.default_rng(seed)
    ids = d[grupo].to_numpy()
    uniq, inv = np.unique(ids, return_inverse=True)
    idx_by = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    rocs = []
    for _ in range(n_boot):
        pick = np.concatenate([idx_by[i] for i in rng.integers(0, len(uniq), len(uniq))])
        yb = y[pick]
        if 0 < yb.sum() < len(yb):
            rocs.append(roc_auc_score(yb, s[pick]))
    out["roc_ic95"] = [float(np.percentile(rocs, 2.5)), float(np.percentile(rocs, 97.5))]
    return out


def _por_grupo(d: pd.DataFrame, col: str, score: str, grupo: str) -> list[dict]:
    res = []
    for g, x in d.groupby(col):
        m = _metricas(x, score, grupo)
        if m:
            res.append({"sector": g, **m})
    return sorted(res, key=lambda r: -r["roc_auc"])


def build() -> dict:
    with psycopg.connect(dsn()) as c:
        sec = pd.DataFrame(c.execute("select cuaderno_id::text, sector from sato.obra").fetchall(), columns=["cuaderno_id", "sector"])
    tipo = pd.read_parquet(ARTIFACTS / "cartera" / "obras.parquet", columns=["codigo_infobras", "tipo_de_obra_clasificador_nivel_1"])
    tipo = tipo.rename(columns={"tipo_de_obra_clasificador_nivel_1": "tipo"})
    res = {"descripcion": "Desempeno en la prueba temporal por sector (sin reentrenar); IC 95 % del ROC-AUC por bootstrap de obras.",
           "minimo_por_clase": MIN_CLASE}

    b = pd.read_parquet(ARTIFACTS / "experiments" / "atraso_H60_B_full_train-nacional" / "predicciones_test.parquet")
    b["cuaderno_id"] = b["cuaderno_id"].astype(str)
    b = b.merge(sec, on="cuaderno_id", how="left").fillna({"sector": "SIN_CUI"})
    res["alerta_60d"] = {"modelo": "B_full LightGBM", "global": _metricas(b, "s_lgbm", "cuaderno_id"),
                         "sectores": _por_grupo(b, "sector", "s_lgbm", "cuaderno_id")}

    i = pd.read_parquet(ARTIFACTS / "exante" / "predicciones_test_y_30.parquet").merge(tipo, on="codigo_infobras", how="left")
    res["cartera_inicio"] = {"modelo": "LightGBM al inicio (y_30)", "global": _metricas(i, "s_lgbm", "codigo_infobras"),
                             "sectores": _por_grupo(i, "tipo", "s_lgbm", "codigo_infobras")}

    s = pd.read_parquet(ARTIFACTS / "exante" / "predicciones_test_seguimiento.parquet").merge(tipo, on="codigo_infobras", how="left")
    res["cartera_seguimiento"] = {"modelo": "LightGBM de seguimiento SIAF (y_30)", "global": _metricas(s, "s_seguimiento_lgbm", "codigo_infobras"),
                                  "sectores": _por_grupo(s, "tipo", "s_seguimiento_lgbm", "codigo_infobras")}
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    with psycopg.connect(dsn(), autocommit=True) as c:
        c.execute("insert into sato.configuracion (clave, valor) values ('desempeno_sectores', %s) "
                  "on conflict (clave) do update set valor = excluded.valor", (json.dumps(res),))
    return res


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    sys.stdout.reconfigure(encoding="utf-8")
    r = build()
    for k in ("alerta_60d", "cartera_inicio", "cartera_seguimiento"):
        g = r[k]["global"]
        print(f"== {k}: global ROC {g['roc_auc']:.3f} PR {g['pr_auc']:.3f} prev {g['prevalencia']:.3f}")
        for x in r[k]["sectores"]:
            print(f"  {x['sector'][:38]:38s} n={x['filas']:6d} pos={x['positivos']:5d} prev={x['prevalencia']:.3f} ROC={x['roc_auc']:.3f} "
                  f"[{x['roc_ic95'][0]:.3f};{x['roc_ic95'][1]:.3f}] PR={x['pr_auc']:.3f} lift10={x['lift_top10']:.2f}")
