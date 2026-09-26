"""Entrenamiento y evaluacion del modelo EX-ANTE (riesgo de retraso significativo al inicio de obra).

Validacion temporal que simula el despliegue:
  * TEST        : obras que INICIAN entre 2022-01-01 y 2024-06-30 (con etiqueta determinada).
  * TRAIN+VALID : obras cuyo resultado se CONOCIO antes de 2022-01-01 (known_30 < TEST_START):
                  exactamente lo que un modelo entrenado el 01-01-2022 habria podido usar.
  * VALID       : obras de TRAIN+VALID iniciadas desde 2020-07-01; TRAIN interno: conocidas antes de esa fecha.
Hiperparametros y umbral se eligen en VALID; el test se evalua una sola vez.

Texto: el nombre de la obra (conocido al inicio) se representa con TF-IDF + regresion logistica;
el score de las filas de entrenamiento es out-of-fold (5 particiones por entidad) para no sobreajustar
el apilamiento; valid/test usan el modelo ajustado solo con entrenamiento.

    python -m sato.exante.train
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from sato.config import ARTIFACTS, FEATURES
from sato.models.evaluate import cluster_bootstrap, point_metrics, precision_at_k, threshold_for_fbeta

log = logging.getLogger(__name__)
TEST_START, TEST_END, VALID_START = pd.Timestamp("2022-01-01"), pd.Timestamp("2024-06-30"), pd.Timestamp("2020-07-01")
OUT = ARTIFACTS / "exante"


def norm(s):
    s = unicodedata.normalize("NFKD", s if isinstance(s, str) else "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s)


def load(target: str = "y_30") -> tuple[pd.DataFrame, list[str], list[str]]:
    d = pd.read_parquet(FEATURES / "exante_dataset.parquet")
    d = d[d[target].notna()].copy()
    d["y"] = d[target].astype(int)
    d["known"] = d["known_" + target.split("_")[1]]
    feats = [c for c in d.columns if c.startswith(("ea_", "hist_"))]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(d[c])]
    for c in cats:
        d[c] = d[c].astype("category")
    return d, feats, cats


def splits(d: pd.DataFrame):
    s = d["fecha_de_inicio_de_obra"]
    test = (s >= TEST_START) & (s <= TEST_END)
    trainval = d["known"] < TEST_START
    valid = trainval & (s >= VALID_START)
    train = trainval & (d["known"] < VALID_START)
    return train, valid, trainval, test


def text_scores(d: pd.DataFrame, fit_mask: pd.Series, groups: pd.Series, seed: int = 42) -> pd.Series:
    """Score del nombre de la obra: OOF en filas de ajuste; resto con modelo ajustado en todo fit_mask."""
    txt = d["nombre_de_obra"].map(norm)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=20, max_features=40000, sublinear_tf=True)
    X = vec.fit_transform(txt[fit_mask])
    y = d.loc[fit_mask, "y"].to_numpy()
    out = pd.Series(np.nan, index=d.index)
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups[fit_mask]):
        m = LogisticRegression(C=0.5, max_iter=2000, solver="liblinear").fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    out[fit_mask] = oof
    m = LogisticRegression(C=0.5, max_iter=2000, solver="liblinear").fit(X, y)
    rest = ~fit_mask
    out[rest] = m.predict_proba(vec.transform(txt[rest]))[:, 1]
    return out, (vec, m)


def make(name, feats, cats, p, seed=42):
    num = [c for c in feats if c not in cats]
    if name in ("logreg", "rf"):
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]) if name == "logreg"
             else SimpleImputer(strategy="median", add_indicator=True), num),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), cats)])
        clf = (LogisticRegression(C=p.get("C", 0.3), max_iter=3000) if name == "logreg"
               else RandomForestClassifier(n_estimators=400, min_samples_leaf=p.get("leaf", 20), max_features="sqrt", n_jobs=-1, random_state=seed))
        return Pipeline([("pre", pre), ("clf", clf)])
    if name == "lgbm":
        return lgb.LGBMClassifier(n_estimators=p.get("n_estimators", 3000), learning_rate=0.03, num_leaves=p.get("num_leaves", 63),
                                  min_child_samples=p.get("mcs", 50), subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
                                  reg_lambda=1.0, cat_smooth=20, random_state=seed, n_jobs=-1, verbose=-1)
    if name == "xgb":
        return XGBClassifier(n_estimators=p.get("n_estimators", 3000), learning_rate=0.03, max_depth=p.get("depth", 7), min_child_weight=5,
                             subsample=0.8, colsample_bytree=0.7, tree_method="hist", enable_categorical=True, max_cat_to_onehot=1,
                             random_state=seed, n_jobs=-1, eval_metric="auc")
    raise ValueError(name)


GRID = {"logreg": [{"C": c} for c in (0.1, 1.0)], "rf": [{"leaf": 10}, {"leaf": 40}],
        "lgbm": [{"num_leaves": n, "mcs": m} for n in (31, 127) for m in (30, 100)], "xgb": [{"depth": 6}, {"depth": 9}]}


def fit_select(name, feats, cats, Xtr, ytr, Xva, yva):
    best = (-1, None, None)
    for p in GRID[name]:
        m = make(name, feats, cats, p)
        if name == "lgbm":
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="auc", callbacks=[lgb.early_stopping(200, verbose=False)])
            p = {**p, "n_estimators": max(100, int(m.best_iteration_ * 1.1))}
        elif name == "xgb":
            m.set_params(early_stopping_rounds=200)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
            p = {**p, "n_estimators": max(100, int(m.best_iteration * 1.1))}
        else:
            m.fit(Xtr, ytr)
        s = m.predict_proba(Xva)[:, 1]
        from sklearn.metrics import roc_auc_score

        auc = roc_auc_score(yva, s)
        if auc > best[0]:
            best = (auc, p, s)
    return best


def run(target: str = "y_30", models=("regla", "logreg", "rf", "lgbm", "xgb"), with_text: bool = True, out: Path = OUT, tag: str = "") -> dict:
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    d, feats, cats = load(target)
    train, valid, trainval, test = splits(d)
    groups = d["codigo_entidad"].fillna("NA")
    final_text = None
    if with_text:
        feats = feats + ["ea_txt_nombre"]
        d["_txt_sel"], _ = text_scores(d, train, groups)           # seleccion: texto ajustado solo con TRAIN
        d["_txt_fin"], final_text = text_scores(d, trainval, groups)  # final: texto ajustado con TRAIN+VALID
    y = d["y"].to_numpy()

    def X_(which):
        X = d[[f for f in feats if f != "ea_txt_nombre"]].copy()
        if with_text:
            X["ea_txt_nombre"] = d[which]
        return X[feats]

    Xs, Xf = (X_("_txt_sel"), X_("_txt_fin")) if with_text else (d[feats], d[feats])
    res = {"target": target, "with_text": with_text, "n_features": len(feats), "features": feats,
           "periodos": {k: [str(d.loc[m, "fecha_de_inicio_de_obra"].min().date()), str(d.loc[m, "fecha_de_inicio_de_obra"].max().date()),
                            int(m.sum()), float(d.loc[m, "y"].mean())] for k, m in (("train", train), ("valid", valid), ("test", test))},
           "modelos": {}}
    preds = d.loc[test, ["codigo_infobras", "departamento", "y", "codigo_entidad"]].copy()
    for name in models:
        if name == "regla":
            s_va = d.loc[valid, "hist_entidad_tasa_retraso"].fillna(d["y"].mean()).to_numpy()
            s_te = d.loc[test, "hist_entidad_tasa_retraso"].fillna(d["y"].mean()).to_numpy()
            p, final = {}, None
        else:
            _, p, s_va = fit_select(name, feats, cats, Xs[train], y[train], Xs[valid], y[valid])
            final = make(name, feats, cats, p)
            final.fit(Xf[trainval], y[trainval])
            s_te = final.predict_proba(Xf[test])[:, 1]
        thr = threshold_for_fbeta(y[valid], s_va, beta=1.0)
        preds[f"s_{name}"] = s_te
        mres = {"params": p, "umbral_f1_valid": thr}
        for ts, tm in (("arequipa", preds["departamento"] == "AREQUIPA"), ("nacional", pd.Series(True, index=preds.index))):
            yt, st = preds.loc[tm, "y"].to_numpy(), preds.loc[tm, f"s_{name}"].to_numpy()
            pm = point_metrics(yt, st, thr)
            for frac in (0.1, 0.2, 0.3):
                pm[f"precision_top{int(frac * 100)}"], pm[f"recall_top{int(frac * 100)}"] = precision_at_k(yt, st, frac)
            mres[ts] = pm
        res["modelos"][name] = mres
        if name == "lgbm":
            joblib.dump({"model": final, "features": feats, "cats": cats, "params": p, "umbral": thr, "text": final_text, "target": target},
                        out / f"modelo_exante_{target}{tag}.joblib")
        log.info("%s %s | AQP AUC=%.3f AP=%.3f | NAC AUC=%.3f AP=%.3f", target, name, mres["arequipa"]["roc_auc"], mres["arequipa"]["pr_auc"],
                 mres["nacional"]["roc_auc"], mres["nacional"]["pr_auc"])
    for ts, tm in (("arequipa", preds["departamento"] == "AREQUIPA"), ("nacional", pd.Series(True, index=preds.index))):
        b = preds.loc[tm].rename(columns={"codigo_entidad": "cuaderno_id"}).fillna({"cuaderno_id": "NA"})  # bootstrap por ENTIDAD
        res[f"bootstrap_{ts}"] = cluster_bootstrap(b, [f"s_{m}" for m in models], n_boot=300).to_dict("records")
    res["segundos"] = round(time.time() - t0, 1)
    preds.to_parquet(out / f"predicciones_test_{target}{tag}.parquet", index=False)
    (out / f"resultados_{target}{tag}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(sys.argv[1] if len(sys.argv) > 1 else "y_30")
