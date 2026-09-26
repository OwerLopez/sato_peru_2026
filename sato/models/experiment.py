"""Experimentos de deteccion temprana con validacion temporal estricta.

Diseno de validacion (por horizonte H, fin de datos D):
  * TEST        : cortes T en [TEST_START, D - H]  (etiquetas totalmente observadas)
  * TRAIN+VALID : cortes T <= TEST_START - H  (purga de H dias: ninguna etiqueta de
                  entrenamiento mira dentro del periodo de test)
  * VALID       : ultimos 3 meses de TRAIN+VALID; TRAIN interno: T <= VALID_START - H
  Hiperparametros, early stopping y umbral de alerta se eligen SOLO en VALID.
  El modelo final se reentrena con TRAIN+VALID y se evalua una unica vez en TEST.

Ademas se reporta una evaluacion rolling-origin (varios origenes) para medir
estabilidad temporal.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from sato.config import ARTIFACTS, FEATURES
from sato.models.evaluate import (
    cluster_bootstrap,
    lead_times,
    point_metrics,
    precision_at_k,
    safe_ap,
    threshold_for_fbeta,
)

log = logging.getLogger(__name__)

TEST_START = pd.Timestamp("2025-12-31")
VALID_MONTHS = 3
PREFIXES_A = ("asi_", "est_", "actor_", "siaf_", "mefseg_", "tmp_", "ib_")
CATEGORICAL = ["est_dep_code", "est_link_method", "est_nivel_gobierno", "est_sector", "est_tipo_inversion", "est_marco", "est_tipo_entidad"]
# Conteos cuya ausencia significa 0 (no hubo registros), no "desconocido"
ZERO_FILL_PREFIX = ("mefseg_", "actor_")


@dataclass
class Config:
    target: str = "atraso"
    H: int = 60
    feature_set: str = "A"
    train_scope: str = "nacional"  # nacional | arequipa
    models: tuple = ("regla", "logreg", "rf", "lgbm", "xgb")
    seed: int = 42
    n_boot: int = 500
    extra_feature_files: tuple = ()
    exclude_prefixes: tuple = ()
    text_stack: tuple = ()  # archivos de ventana (tfidf .npz / emb .npy) para scores as-of apilados
    tag: str = ""
    test_start: str = "2025-12-31"
    test_months: int = 0  # 0 = hasta el final observable; >0 = ventana de test acotada (rolling-origin)
    save_model: bool = False
    results: dict = field(default_factory=dict)


def asof_text_scores(df: pd.DataFrame, H: int, test_start: pd.Timestamp = TEST_START, min_pos: int = 30,
                     window_file: str = "text_window_tfidf.npz") -> pd.Series:
    """Score de texto supervisado calculado "as-of" (forward chaining).

    Para una fila con corte T=m se usa una regresion logistica sobre la
    representacion de texto de la ventana, entrenada SOLO con filas cuyo
    corte T' cumple T' + H <= m (su etiqueta ya era conocida en m). Para las
    filas de test se usa el modelo congelado en TEST_START (entrenado con
    T' <= TEST_START - H), igual que los demas modelos. Asi el score nunca
    incorpora informacion posterior al corte.
    """
    import scipy.sparse as sp

    if window_file.endswith(".npz"):
        Xw = sp.load_npz(FEATURES / window_file).tocsr()
    else:
        Xw = np.load(FEATURES / window_file)
    rows = df["_row"].to_numpy()
    X = Xw[rows]
    y = df["y"].to_numpy()
    T = df["T"].to_numpy()
    out = np.full(len(df), np.nan)
    months = np.sort(df["T"].unique())
    cache = {}
    for m in months:
        cutoff = min(pd.Timestamp(m), test_start) - pd.Timedelta(days=H)
        key = cutoff
        if key not in cache:
            tr = T <= np.datetime64(cutoff)
            if y[tr].sum() < min_pos:
                cache[key] = None
            else:
                clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="liblinear")
                clf.fit(X[tr], y[tr])
                cache[key] = clf
        clf = cache[key]
        sel = T == m
        if clf is not None:
            out[sel] = clf.predict_proba(X[sel])[:, 1]
    return pd.Series(out, index=df.index)


def load_dataset(cfg: Config) -> tuple[pd.DataFrame, list[str]]:
    panel = pd.read_parquet(FEATURES / "panel.parquet")
    panel["_row"] = np.arange(len(panel))
    feats = pd.read_parquet(FEATURES / "features_structured.parquet")
    df = panel.merge(feats, on=["cuaderno_id", "T"], how="left")
    for f in cfg.extra_feature_files:
        df = df.merge(pd.read_parquet(FEATURES / f), on=["cuaderno_id", "T"], how="left")
    ycol = f"y_{cfg.target}_{cfg.H}"
    df = df[df[f"eligible_{cfg.target}"] & (df[ycol] >= 0)].copy()
    df["y"] = df[ycol].astype(int)
    df["onset"] = df[f"onset_{cfg.target}"]
    cols = [c for c in feats.columns if c.startswith(PREFIXES_A)]
    for f in cfg.extra_feature_files:
        cols += [c for c in pd.read_parquet(FEATURES / f).columns if c not in ("cuaderno_id", "T")]
    cols = [c for c in cols if not c.startswith(cfg.exclude_prefixes)] if cfg.exclude_prefixes else cols
    for c in cols:
        if c.startswith(ZERO_FILL_PREFIX):
            df[c] = df[c].fillna(0)
        if df[c].dtype == bool:
            df[c] = df[c].astype(float)
    for c in CATEGORICAL:
        if c in cols:
            df[c] = df[c].fillna("NA").astype("category")
    return df, cols


def splits(df: pd.DataFrame, H: int, test_start: pd.Timestamp = TEST_START, test_months: int = 0):
    D = df["data_end"].iloc[0]
    test_end = D - pd.Timedelta(days=H)
    if test_months:
        test_end = min(test_end, test_start + pd.DateOffset(months=test_months - 1) + pd.offsets.MonthEnd(0))
    test = (df["T"] >= test_start) & (df["T"] <= test_end)
    trainval = df["T"] <= test_start - pd.Timedelta(days=H)
    tv_end = df.loc[trainval, "T"].max()
    valid_start = tv_end - pd.DateOffset(months=VALID_MONTHS) + pd.offsets.MonthEnd(0)
    valid = trainval & (df["T"] > valid_start)
    train = df["T"] <= valid_start - pd.Timedelta(days=H)
    return train, valid, trainval, test


def rule_score(X: pd.DataFrame) -> np.ndarray:
    """Heuristica experta sin aprendizaje: senales formales recientes de problemas."""
    s = (
        X.get("asi_90d_ampliacion_plazo", 0) + 2 * X.get("asi_90d_suspension_plazo", 0) + 2 * X.get("asi_90d_penalidades", 0)
        + X.get("asi_90d_adicionales", 0) + X.get("asi_90d_mayores_metrados", 0) + X.get("asi_consultas_pendientes", 0).clip(lower=0)
    )
    return np.asarray(s, dtype=float) + 1e-6 * np.asarray(X.get("asi_n_90d", 0), dtype=float)


def _num_cat(cols):
    cats = [c for c in cols if c in CATEGORICAL]
    return [c for c in cols if c not in cats], cats


def make_model(name: str, cols: list[str], seed: int, params: dict | None = None):
    params = params or {}
    num, cats = _num_cat(cols)
    if name == "logreg":
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]), num),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cats),
        ])
        return Pipeline([("pre", pre), ("clf", LogisticRegression(C=params.get("C", 0.1), class_weight="balanced", max_iter=3000))])
    if name == "rf":
        pre = ColumnTransformer([
            ("num", SimpleImputer(strategy="median", add_indicator=True), num),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cats),
        ])
        return Pipeline([("pre", pre), ("clf", RandomForestClassifier(n_estimators=500, min_samples_leaf=params.get("min_samples_leaf", 20),
                                                                     max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=seed))])
    if name == "lgbm":
        return lgb.LGBMClassifier(n_estimators=params.get("n_estimators", 2000), learning_rate=0.03, num_leaves=params.get("num_leaves", 31),
                                  min_child_samples=params.get("min_child_samples", 40), subsample=0.8, subsample_freq=1,
                                  colsample_bytree=0.8, reg_lambda=1.0, random_state=seed, n_jobs=-1, verbose=-1)
    if name == "xgb":
        return XGBClassifier(n_estimators=params.get("n_estimators", 2000), learning_rate=0.03, max_depth=params.get("max_depth", 5),
                             min_child_weight=params.get("min_child_weight", 5), subsample=0.8, colsample_bytree=0.8,
                             reg_lambda=1.0, tree_method="hist", enable_categorical=True, random_state=seed, n_jobs=-1,
                             eval_metric="aucpr")
    raise ValueError(name)


GRIDS = {
    "logreg": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "rf": [{"min_samples_leaf": m} for m in (5, 20, 50)],
    "lgbm": [{"num_leaves": n, "min_child_samples": m} for n in (15, 31) for m in (20, 60)],
    "xgb": [{"max_depth": d, "min_child_weight": w} for d in (3, 5) for w in (1, 10)],
}


def fit_select(name, cols, Xtr, ytr, Xva, yva, seed):
    """Seleccion de hiperparametros y n_estimators SOLO con VALID."""
    best = (-1, None)
    for p in GRIDS[name]:
        m = make_model(name, cols, seed, p)
        if name == "lgbm":
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="average_precision",
                  callbacks=[lgb.early_stopping(150, verbose=False)])
            p = {**p, "n_estimators": max(50, int(m.best_iteration_ * 1.1))}
        elif name == "xgb":
            m.set_params(early_stopping_rounds=150)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
            p = {**p, "n_estimators": max(50, int(m.best_iteration * 1.1))}
        else:
            m.fit(Xtr, ytr)
        s = m.predict_proba(Xva)[:, 1]
        ap = safe_ap(yva, s)
        if ap > best[0]:
            best = (ap, p, s)
    return best


def run(cfg: Config, out_root: Path = ARTIFACTS / "experiments") -> dict:
    t0 = time.time()
    df, cols = load_dataset(cfg)
    for wf in cfg.text_stack:
        name = "txt_stack_" + ("tfidf" if wf.endswith(".npz") else "emb")
        df[name] = asof_text_scores(df, cfg.H, test_start=pd.Timestamp(cfg.test_start), window_file=wf)
        cols = cols + [name]
    train, valid, trainval, test = splits(df, cfg.H, pd.Timestamp(cfg.test_start), cfg.test_months)
    scope = (df["dep_code"] == "04") if cfg.train_scope == "arequipa" else pd.Series(True, index=df.index)
    X, y = df[cols], df["y"].to_numpy()
    res = {"config": {k: v for k, v in asdict(cfg).items() if k != "results"}, "n_features": len(cols), "features": cols,
           "periodos": {k: [str(df.loc[m, "T"].min().date()), str(df.loc[m, "T"].max().date()), int(m.sum()), int(df.loc[m, "y"].sum())]
                        for k, m in (("train", train & scope), ("valid", valid & scope), ("test", test))},
           "modelos": {}}
    preds = df.loc[test, ["cuaderno_id", "T", "dep_code", "y", "onset"]].copy()
    for name in cfg.models:
        if name == "regla":
            s_va, s_te, p = rule_score(X[valid & scope]), rule_score(X[test]), {}
            val_ap = safe_ap(y[valid & scope], s_va)
        else:
            val_ap, p, s_va = fit_select(name, cols, X[train & scope], y[train & scope], X[valid & scope], y[valid & scope], cfg.seed)
            final = make_model(name, cols, cfg.seed, p)
            final.fit(X[trainval & scope], y[trainval & scope])
            s_te = final.predict_proba(X[test])[:, 1]
            if name == "lgbm" and cfg.save_model:
                import joblib
                d = out_root / run_id(cfg)
                d.mkdir(parents=True, exist_ok=True)
                joblib.dump({"model": final, "features": cols, "config": res["config"], "params": p}, d / "model_lgbm.joblib")
        thr = threshold_for_fbeta(y[valid & scope], s_va, beta=2.0)
        preds[f"s_{name}"] = s_te
        mres = {"params": p, "valid_pr_auc": float(val_ap), "umbral_f2_valid": thr}
        for tscope, tm in (("arequipa", preds["dep_code"] == "04"), ("nacional", pd.Series(True, index=preds.index))):
            yt, st = preds.loc[tm, "y"].to_numpy(), preds.loc[tm, f"s_{name}"].to_numpy()
            pm = point_metrics(yt, st, thr)
            for frac in (0.05, 0.10, 0.20):
                pm[f"precision_top{int(frac*100)}"], pm[f"recall_top{int(frac*100)}"] = precision_at_k(yt, st, frac)
            lt = lead_times(preds.loc[tm].assign(T=preds.loc[tm, "T"]), f"s_{name}", thr, "onset")
            pm["obras_con_onset_en_test"] = int(len(lt))
            pm["obras_alertadas_antes_del_onset"] = int(lt["primera_alerta"].notna().sum()) if len(lt) else 0
            pm["anticipacion_mediana_dias"] = float(lt["anticipacion_dias"].median()) if len(lt) else np.nan
            mres[tscope] = pm
        res["modelos"][name] = mres
        log.info("%s %s H=%s %s | valid AP=%.3f | AQP test AP=%.3f ROC=%.3f | NAC AP=%.3f",
                 cfg.tag or cfg.feature_set, name, cfg.H, cfg.train_scope, val_ap,
                 mres["arequipa"]["pr_auc"], mres["arequipa"]["roc_auc"], mres["nacional"]["pr_auc"])
    # bootstrap por obra: todos los modelos vs la regla heuristica, en Arequipa y nacional
    score_cols = [f"s_{m}" for m in cfg.models]
    for tscope, tm in (("arequipa", preds["dep_code"] == "04"), ("nacional", pd.Series(True, index=preds.index))):
        res[f"bootstrap_{tscope}"] = cluster_bootstrap(preds.loc[tm], score_cols, n_boot=cfg.n_boot).to_dict("records")
    res["segundos"] = round(time.time() - t0, 1)
    d = out_root / run_id(cfg)
    d.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(d / "predicciones_test.parquet", index=False)
    (d / "resultados.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


def run_id(cfg: Config) -> str:
    ts = "" if cfg.test_start == "2025-12-31" and not cfg.test_months else f"_origin-{cfg.test_start}"
    return f"{cfg.target}_H{cfg.H}_{cfg.feature_set}{('_' + cfg.tag) if cfg.tag else ''}_train-{cfg.train_scope}{ts}"


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="atraso")
    ap.add_argument("--H", type=int, default=60)
    ap.add_argument("--scope", default="nacional")
    ap.add_argument("--models", default="regla,logreg,rf,lgbm,xgb")
    a = ap.parse_args()
    run(Config(target=a.target, H=a.H, train_scope=a.scope, models=tuple(a.models.split(","))))
