"""Metricas de evaluacion, bootstrap por obra y anticipacion (lead time)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def safe_auc(y, s):
    return roc_auc_score(y, s) if len(np.unique(y)) == 2 else np.nan


def safe_ap(y, s):
    return average_precision_score(y, s) if y.sum() > 0 else np.nan


def threshold_for_fbeta(y, s, beta: float = 2.0) -> float:
    """Umbral que maximiza F-beta (beta=2 prioriza recall: alerta temprana)."""
    qs = np.unique(np.quantile(s, np.linspace(0.5, 0.995, 200)))
    best, thr = -1.0, float(qs[-1])
    for q in qs:
        f = fbeta_score(y, (s >= q).astype(int), beta=beta, zero_division=0)
        if f > best:
            best, thr = f, float(q)
    return thr


def point_metrics(y, s, thr: float) -> dict:
    yhat = (s >= thr).astype(int)
    return dict(
        n=int(len(y)), positivos=int(y.sum()), prevalencia=float(y.mean()),
        pr_auc=float(safe_ap(y, s)), roc_auc=float(safe_auc(y, s)), brier=float(brier_score_loss(y, s)) if (s.min() >= 0 and s.max() <= 1) else float("nan"),
        umbral=float(thr), alertas=int(yhat.sum()),
        precision=float(precision_score(y, yhat, zero_division=0)), recall=float(recall_score(y, yhat, zero_division=0)),
        f1=float(f1_score(y, yhat, zero_division=0)), f2=float(fbeta_score(y, yhat, beta=2, zero_division=0)),
        tp=int(((yhat == 1) & (y == 1)).sum()), fp=int(((yhat == 1) & (y == 0)).sum()),
        fn=int(((yhat == 0) & (y == 1)).sum()), tn=int(((yhat == 0) & (y == 0)).sum()),
    )


def precision_at_k(y, s, frac: float) -> tuple[float, float]:
    k = max(1, int(round(frac * len(s))))
    idx = np.argsort(-s)[:k]
    return float(y[idx].mean()), float(y[idx].sum() / max(1, y.sum()))


def cluster_bootstrap(df: pd.DataFrame, score_cols: list[str], y_col: str = "y", group_col: str = "cuaderno_id",
                      n_boot: int = 1000, seed: int = 7) -> pd.DataFrame:
    """IC 95% por bootstrap de obras (clusters) para PR-AUC y ROC-AUC de cada score,
    y para la diferencia pareada respecto del primer score."""
    rng = np.random.default_rng(seed)
    groups = df[group_col].unique()
    idx_by_g = df.groupby(group_col).indices
    res = {c: {"pr": [], "roc": []} for c in score_cols}
    diffs = {c: {"pr": [], "roc": []} for c in score_cols[1:]}
    y_all = df[y_col].to_numpy()
    S = {c: df[c].to_numpy() for c in score_cols}
    for _ in range(n_boot):
        g = rng.choice(groups, size=len(groups), replace=True)
        ii = np.concatenate([idx_by_g[x] for x in g])
        y = y_all[ii]
        if y.sum() == 0 or y.sum() == len(y):
            continue
        base_pr = base_roc = None
        for j, c in enumerate(score_cols):
            pr, roc = average_precision_score(y, S[c][ii]), roc_auc_score(y, S[c][ii])
            res[c]["pr"].append(pr)
            res[c]["roc"].append(roc)
            if j == 0:
                base_pr, base_roc = pr, roc
            else:
                diffs[c]["pr"].append(pr - base_pr)
                diffs[c]["roc"].append(roc - base_roc)
    rows = []
    for c in score_cols:
        for m in ("pr", "roc"):
            a = np.array(res[c][m])
            rows.append(dict(score=c, metrica=m, media=a.mean(), ic_inf=np.quantile(a, 0.025), ic_sup=np.quantile(a, 0.975)))
    for c in score_cols[1:]:
        for m in ("pr", "roc"):
            a = np.array(diffs[c][m])
            rows.append(dict(score=f"{c} - {score_cols[0]}", metrica=m, media=a.mean(), ic_inf=np.quantile(a, 0.025),
                             ic_sup=np.quantile(a, 0.975), p_valor_una_cola=float((a <= 0).mean())))
    return pd.DataFrame(rows)


def lead_times(df: pd.DataFrame, score_col: str, thr: float, onset_col: str) -> pd.DataFrame:
    """Para cada obra con onset observado dentro del periodo evaluado, primera alerta (score>=thr)
    emitida antes del onset y dias de anticipacion."""
    d = df[df[onset_col].notna()].copy()
    d = d[d["T"] < d[onset_col]]
    out = []
    for cid, g in d.groupby("cuaderno_id"):
        onset = g[onset_col].iloc[0]
        alerts = g.loc[g[score_col] >= thr, "T"]
        first = alerts.min() if len(alerts) else pd.NaT
        out.append(dict(cuaderno_id=cid, onset=onset, primera_alerta=first,
                        anticipacion_dias=(onset - first).days if pd.notna(first) else np.nan,
                        cortes_previos=len(g)))
    return pd.DataFrame(out)
