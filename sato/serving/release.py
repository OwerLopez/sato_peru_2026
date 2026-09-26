"""Publicacion del modelo operativo: predicciones, explicaciones (TreeSHAP) y evidencia.

Configuracion operativa PRE-REGISTRADA (no elegida mirando el test):
  * objetivo  : atraso normativo (RLCE art. 203 / RLGCP art. 207)
  * horizonte : H = 60 dias (dos ciclos de valorizacion mensual: margen para que la
                entidad exija medidas antes del disparador formal)
  * algoritmo : LightGBM, hiperparametros elegidos en VALID
  * features  : conjunto configurable (por defecto el de mejor PR-AUC en VALID entre A y B_full)

Salidas en artifacts/release/:
  * modelo_produccion.joblib : entrenado con TODAS las filas observables (T <= D - H)
  * predicciones.parquet     : Arequipa. `backtest` = score "as-of" de un modelo
                               reentrenado trimestralmente solo con datos anteriores
                               (T' <= origen - H); `vigente` = ultimo corte D con el
                               modelo de produccion.
  * explicaciones.parquet    : top-8 contribuciones TreeSHAP por prediccion
  * evidencia.parquet        : registros reales que respaldan cada contribucion positiva
  * modelo_card.json         : metadatos, umbrales, metricas de test temporal ciego
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sato.config import ARTIFACTS, CURATED, FEATURES, STAGING
from sato.features.text import LEXICON, WINDOW_DAYS, norm_text
from sato.models.evaluate import threshold_for_fbeta
from sato.models.experiment import CATEGORICAL, Config, asof_text_scores, load_dataset, make_model, splits
from sato.models.grid import FEATURE_SETS
from sato.serving.descriptions import describe, group_of

log = logging.getLogger(__name__)
OUT = ARTIFACTS / "release"
TOP_K = 8


def _load_all(cfg: Config) -> tuple[pd.DataFrame, list[str]]:
    """Como load_dataset pero conservando filas aun no observables (para prediccion vigente)."""
    import sato.models.experiment as E

    panel = pd.read_parquet(FEATURES / "panel.parquet")
    panel["_row"] = np.arange(len(panel))
    feats = pd.read_parquet(FEATURES / "features_structured.parquet")
    df = panel.merge(feats, on=["cuaderno_id", "T"], how="left")
    for f in cfg.extra_feature_files:
        df = df.merge(pd.read_parquet(FEATURES / f), on=["cuaderno_id", "T"], how="left")
    ycol = f"y_{cfg.target}_{cfg.H}"
    df = df[df[f"eligible_{cfg.target}"]].copy()
    df["y"] = df[ycol].astype(int)  # -1 = no observable aun
    df["onset"] = df[f"onset_{cfg.target}"]
    _, cols = load_dataset(cfg)  # misma lista y reglas de columnas
    cols = [c for c in cols if not c.startswith("txt_stack_")]
    for c in cols:
        if c.startswith(E.ZERO_FILL_PREFIX):
            df[c] = df[c].fillna(0)
        if df[c].dtype == bool:
            df[c] = df[c].astype(float)
    for c in CATEGORICAL:
        if c in cols:
            df[c] = df[c].fillna("NA").astype("category")
    return df, cols


def _params(cfg: Config) -> dict:
    from sato.models.experiment import run_id

    r = json.loads((ARTIFACTS / "experiments" / run_id(cfg) / "resultados.json").read_text(encoding="utf-8"))
    return r["modelos"]["lgbm"]["params"], r


def _fit(cols, X, y, params, seed=42):
    m = make_model("lgbm", cols, seed, params)
    m.fit(X, y)
    return m


def _shap(model, X: pd.DataFrame) -> np.ndarray:
    return model.booster_.predict(X, pred_contrib=True)  # TreeSHAP exacto; ultima columna = valor base (log-odds)


def build(feature_set: str = "B_full", H: int = 60, target: str = "atraso", out: Path = OUT) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    kw = FEATURE_SETS[feature_set]
    cfg = Config(target=target, H=H, feature_set=feature_set, models=("lgbm",), **kw)
    params, grid_res = _params(cfg)
    df, cols = _load_all(cfg)
    D = df["data_end"].iloc[0]
    obs = df["y"] >= 0
    # Scores de texto apilados totalmente "as-of" (cada mes con un modelo entrenado solo con etiquetas ya conocidas)
    for wf in cfg.text_stack:
        name = "txt_stack_" + ("tfidf" if wf.endswith(".npz") else "emb")
        tmp = df.copy()
        tmp.loc[~obs, "y"] = 0  # nunca se usan para entrenar: asof usa T' <= m - H, siempre observables
        df[name] = asof_text_scores(tmp, H, test_start=D + pd.Timedelta(days=3650), window_file=wf)
        cols = cols + [name]

    # Umbrales en VALID (misma particion que la grilla)
    train, valid, trainval, test = splits(df[obs], H)
    dfo = df[obs]
    m_val = _fit(cols, dfo.loc[train, cols], dfo.loc[train, "y"], params)
    s_val = m_val.predict_proba(dfo.loc[valid, cols])[:, 1]
    y_val = dfo.loc[valid, "y"].to_numpy()
    thr_alerta = threshold_for_fbeta(y_val, s_val, beta=2.0)
    thr_alto = threshold_for_fbeta(y_val, s_val, beta=1.0)
    thr_alto = max(thr_alto, thr_alerta)

    # Modelo de produccion: todas las filas observables
    prod = _fit(cols, dfo[cols], dfo["y"], params)
    art = out / "modelo_produccion.joblib"
    joblib.dump({"model": prod, "features": cols, "params": params, "H": H, "target": target, "feature_set": feature_set,
                 "thr_alerta": thr_alerta, "thr_alto": thr_alto, "entrenado_hasta": str(dfo["T"].max().date())}, art)
    sha = hashlib.sha256(art.read_bytes()).hexdigest()

    aqp = pd.Series(True, index=df.index)  # alcance nacional (todas las obras con cuaderno digital)
    preds, shaps = [], []
    # Backtest as-of con reentrenamiento trimestral
    origins = pd.date_range("2024-12-31", D, freq="QE")
    for i, o in enumerate(origins):
        nxt = origins[i + 1] if i + 1 < len(origins) else D + pd.Timedelta(days=1)
        tr = obs & (df["T"] <= o - pd.Timedelta(days=H))
        if df.loc[tr, "y"].sum() < 50:
            continue
        m = _fit(cols, df.loc[tr, cols], df.loc[tr, "y"], params)
        sel = aqp & (df["T"] > o) & (df["T"] <= nxt) & (df["T"] < D)
        if sel.sum() == 0:
            continue
        p = df.loc[sel, ["cuaderno_id", "T", "y"]].copy()
        p["score"] = m.predict_proba(df.loc[sel, cols])[:, 1]
        p["tipo"] = "backtest"
        p["modelo_origen"] = str(o.date())
        preds.append(p)
        shaps.append((p.index, _shap(m, df.loc[sel, cols])))
        log.info("backtest origen %s: entrenado con %s filas, %s predicciones", o.date(), int(tr.sum()), int(sel.sum()))
    sel = aqp & (df["T"] == D)
    p = df.loc[sel, ["cuaderno_id", "T", "y"]].copy()
    p["score"] = prod.predict_proba(df.loc[sel, cols])[:, 1]
    p["tipo"] = "vigente"
    p["modelo_origen"] = "produccion"
    preds.append(p)
    shaps.append((p.index, _shap(prod, df.loc[sel, cols])))
    P = pd.concat(preds)
    # Politica operativa (elegida en VALID): ALERTA = nivel ALTO (umbral que maximiza F1);
    # MEDIO = "en vigilancia" (umbral que maximiza F2, orientado a recall); BAJO = resto.
    P["alerta"] = P["score"] >= thr_alto
    P["nivel"] = np.where(P["alerta"], "ALTO", np.where(P["score"] >= thr_alerta, "MEDIO", "BAJO"))
    P["percentil"] = P.groupby("T")["score"].rank(pct=True)
    P["y_observado"] = P["y"].where(P["y"] >= 0)
    P = P.drop(columns="y")

    # Explicaciones top-K
    E = []
    for idx, S in shaps:
        vals = df.loc[idx, cols]
        for j, ix in enumerate(idx):
            contrib = S[j, :-1]
            order = np.argsort(-np.abs(contrib))[:TOP_K]
            for r, k in enumerate(order):
                f = cols[k]
                v = vals.iloc[j, k]
                vnum = float(v) if isinstance(v, (int, float, np.floating, np.integer)) and not pd.isna(v) else None
                E.append(dict(cuaderno_id=df.at[ix, "cuaderno_id"], T=df.at[ix, "T"], rango=r + 1, feature=f, grupo=group_of(f),
                              valor=vnum, shap=float(contrib[k]), descripcion=describe(f, vnum if vnum is not None else (str(v) if not pd.isna(v) else None))))
    E = pd.DataFrame(E)
    P.to_parquet(out / "predicciones.parquet", index=False)
    E.to_parquet(out / "explicaciones.parquet", index=False)
    keep = P.loc[(P["tipo"] == "vigente") | (P["nivel"] != "BAJO"), ["cuaderno_id", "T"]]
    evidence(E.merge(keep, on=["cuaderno_id", "T"]), out)
    simulate(prod, df.loc[df["T"] == D], cols, thr_alto, out)

    dep = df.drop_duplicates("cuaderno_id").set_index("cuaderno_id")["dep_code"]

    def operacion(o):
        r = {"filas_observables": int(len(o)), "prevalencia": float((o["y_observado"] == 1).mean())}
        for name, m in (("alerta_alto", o["nivel"] == "ALTO"), ("vigilancia_o_alto", o["nivel"] != "BAJO")):
            tp = int(((m) & (o["y_observado"] == 1)).sum())
            r[name] = {"tasa_marcadas": float(m.mean()), "precision": tp / max(1, int(m.sum())), "recall": tp / max(1, int((o["y_observado"] == 1).sum()))}
        for k in (0.05, 0.10, 0.20, 0.30):
            m = o["score"] >= o["score"].quantile(1 - k)
            tp = int(((m) & (o["y_observado"] == 1)).sum())
            r[f"top_{int(k * 100)}"] = {"precision": tp / max(1, int(m.sum())), "recall": tp / max(1, int((o["y_observado"] == 1).sum()))}
        return r

    o_all = P[P["y_observado"].notna()]
    op = operacion(o_all[o_all["cuaderno_id"].map(dep) == "04"])
    op_nac = operacion(o_all)
    card = dict(
        nombre="SATO-AQP alerta de atraso", version=f"{target}-H{H}-{feature_set}-{str(D.date())}", objetivo=target, horizonte_dias=H,
        conjunto_features=feature_set, algoritmo="LightGBM (TreeSHAP)", entrenado_hasta=str(df.loc[obs, "T"].max().date()),
        fecha_corte_datos=str(D.date()), umbral_alerta=thr_alto, umbral_vigilancia=thr_alerta, umbral_alto=thr_alto,
        operacion_backtest_arequipa=op, operacion_backtest_nacional=op_nac, params=params, features=cols,
        metricas_test=grid_res["modelos"]["lgbm"], periodos_evaluacion=grid_res["periodos"], artefacto=str(art.name), sha256=sha,
        filas_entrenamiento=int(obs.sum()), obras_entrenamiento=int(df.loc[obs, "cuaderno_id"].nunique()),
    )
    (out / "modelo_card.json").write_text(json.dumps(card, indent=1, default=str), encoding="utf-8")
    log.info("release: %s predicciones (%s vigentes, %s alertas vigentes)", len(P), int((P.tipo == "vigente").sum()),
             int(((P.tipo == "vigente") & P.alerta).sum()))
    return out


# ---------------------------------------------------------------- simulador (sensibilidad del modelo)
ESCENARIOS = {
    "consultas": ("Absolver todas las consultas pendientes", {"asi_consultas_pendientes": 0}),
    "suspensiones": ("Sin suspensiones del plazo en los ultimos 90 dias", {"asi_90d_suspension_plazo": 0}),
    "penalidades": ("Sin aplicacion de penalidades en los ultimos 90 dias", {"asi_90d_penalidades": 0}),
    "ampliaciones": ("Sin nuevas ampliaciones de plazo en los ultimos 90 dias", {"asi_90d_ampliacion_plazo": 0}),
    "registro": ("Registro activo del cuaderno (asiento reciente)", {"asi_dias_desde_ultimo": 0}),
    "devengado": ("Ejecucion financiera al dia (devengado en el ultimo mes)", {"siaf_meses_desde_ultimo_dev": 1}),
}


def simulate(model, cur: pd.DataFrame, cols: list[str], thr: float, out: Path) -> Path:
    """Recalcula el riesgo vigente modificando UNA variable accionable a la vez.

    Es un analisis de SENSIBILIDAD del modelo (cuanto cambia la prediccion si esa senal
    cambiara), NO una estimacion causal del efecto de una intervencion real.
    Solo se reportan escenarios aplicables (la variable existe y su valor cambia).
    """
    base = model.predict_proba(cur[cols])[:, 1]
    rows = []
    for key, (desc, changes) in ESCENARIOS.items():
        X = cur[cols].copy()
        aplica = pd.Series(False, index=cur.index)
        for f, v in changes.items():
            if f not in X.columns:
                continue
            aplica |= X[f].notna() & (X[f] != v)
            X[f] = X[f].where(~(X[f].notna() & (X[f] != v)), v)
        s = model.predict_proba(X)[:, 1]
        for i, ix in enumerate(cur.index):
            if aplica.loc[ix]:
                rows.append(dict(cuaderno_id=cur.at[ix, "cuaderno_id"], T=cur.at[ix, "T"], escenario=key, descripcion=desc,
                                 score_base=float(base[i]), score_escenario=float(s[i]), alerta_escenario=bool(s[i] >= thr)))
    sim = pd.DataFrame(rows)
    dst = out / "simulaciones.parquet"
    sim.to_parquet(dst, index=False)
    log.info("simulaciones: %s escenarios aplicables", len(sim))
    return dst


# ---------------------------------------------------------------- evidencia
def _tfidf_ranker():
    """Modelo de texto de produccion para ORDENAR asientos como evidencia (no para predecir)."""
    import scipy.sparse as sp
    from sklearn.linear_model import LogisticRegression

    vec = joblib.load(FEATURES / "text_lsa_model.joblib")["vectorizer"]
    panel = pd.read_parquet(FEATURES / "panel.parquet")
    Xw = sp.load_npz(FEATURES / "text_window_tfidf.npz").tocsr()
    y = panel["y_atraso_60"].to_numpy()
    ok = (y >= 0) & panel["eligible_atraso"].to_numpy()
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="liblinear").fit(Xw[ok], y[ok])
    return vec, clf


def evidence(E: pd.DataFrame, out: Path) -> Path:
    pos = E[E["shap"] > 0].sort_values(["cuaderno_id", "T", "rango"]).groupby(["cuaderno_id", "T"]).head(5)
    asi = pd.read_parquet(CURATED / "asiento.parquet", columns=["cuaderno_id", "nro_asiento", "fecha", "tipo", "tipo_std", "titulo", "descripcion"])
    asi = asi[asi["cuaderno_id"].isin(pos["cuaderno_id"].unique())].copy()
    asi["fecha"] = pd.to_datetime(asi["fecha"])
    asi["txt"] = (asi["titulo"].fillna("") + " . " + asi["descripcion"].fillna("")).map(norm_text)
    by_c = {c: g for c, g in asi.groupby("cuaderno_id")}
    siaf = pd.concat([pd.read_parquet(f, columns=["cui", "anio", "mes", "monto_devengado"]) for f in sorted((STAGING / "siaf").glob("*.parquet"))])
    cua = pd.read_parquet(CURATED / "cuaderno.parquet").set_index("cuaderno_id")
    cuis = set(cua.loc[cua.index.isin(pos["cuaderno_id"].unique()), "cui"].dropna())
    siaf = siaf[(siaf["mes"] >= 1) & (siaf["anio"] >= 2020) & siaf["cui"].isin(cuis)].copy()
    siaf["mes_ini"] = pd.to_datetime(dict(year=siaf["anio"], month=siaf["mes"], day=1))
    siaf_by = {c: g.sort_values("mes_ini", ascending=False) for c, g in siaf.groupby("cui")}
    mefseg = pd.read_parquet(STAGING / "mef_estado_situacional.parquet")
    mefseg = mefseg[mefseg["cui"].isin(cuis)]
    mefseg_by = {c: g for c, g in mefseg.groupby("cui")}
    cua["onset"] = pd.concat([pd.to_datetime(cua[c]) for c in ("f_valorizacion_menor_80", "f_calendario_acelerado")], axis=1).min(axis=1)
    actor_by = {k: {v: g for v, g in cua[cua["onset"].notna()].groupby(k)} for k in ("ruc_contratista", "ruc_entidad")}
    vec, clf = _tfidf_ranker()
    coef = clf.coef_.ravel()
    lex = {k: re.compile(v) for k, v in LEXICON.items()}
    rows = []

    def add(r, fuente, **kw):
        rows.append(dict(cuaderno_id=r.cuaderno_id, T=r.T, feature=r.feature, fuente=fuente, **kw))

    for r in pos.itertuples():
        g = by_c.get(r.cuaderno_id)
        T = pd.Timestamp(r.T)
        f = r.feature
        if g is not None:
            m = re.match(r"asi_(cum|90d)_(.+)", f)
            if m:
                w = g[(g["fecha"] <= T) & (g["tipo_std"] == m.group(2).upper())]
                if m.group(1) == "90d":
                    w = w[w["fecha"] > T - pd.Timedelta(days=90)]
                for a in w.sort_values("fecha", ascending=False).head(5).itertuples():
                    add(r, "ASIENTO", nro_asiento=a.nro_asiento, fecha=a.fecha, referencia=a.tipo, extracto=_snip(a.titulo, a.descripcion))
                continue
            m = re.match(r"txt_lx_(.+)", f)
            if m and m.group(1) in lex:
                w = g[(g["fecha"] <= T) & (g["fecha"] > T - pd.Timedelta(days=WINDOW_DAYS))]
                w = w[w["txt"].str.contains(lex[m.group(1)])]
                for a in w.sort_values("fecha", ascending=False).head(4).itertuples():
                    add(r, "ASIENTO", nro_asiento=a.nro_asiento, fecha=a.fecha, referencia=a.tipo,
                        extracto=_snip_match(a.txt, lex[m.group(1)]))
                continue
            if f.startswith(("txt_stack", "txt_lsa", "txt_emb", "txt_n_", "txt_len", "ie_", "asi_")):
                w = g[(g["fecha"] <= T) & (g["fecha"] > T - pd.Timedelta(days=WINDOW_DAYS))]
                if len(w):
                    sc = vec.transform(w["txt"]) @ coef
                    w = w.assign(_s=np.asarray(sc).ravel()).sort_values("_s", ascending=False).head(3)
                    for a in w.itertuples():
                        add(r, "ASIENTO", nro_asiento=a.nro_asiento, fecha=a.fecha, referencia=a.tipo, extracto=_snip(a.titulo, a.descripcion))
                continue
        cui = cua.at[r.cuaderno_id, "cui"] if r.cuaderno_id in cua.index else None
        if f.startswith("siaf_") and cui:
            s = siaf_by.get(cui)
            s = s[s["mes_ini"] < T.replace(day=1)].head(6) if s is not None else siaf.iloc[:0]
            for x in s.itertuples():
                add(r, "SIAF", fecha=x.mes_ini, referencia=f"https://ofi5.mef.gob.pe/ssi/Ssi/Index?codigo={cui}&tipo=2",
                    extracto=f"Devengado {x.anio}-{x.mes:02d}: S/ {x.monto_devengado:,.2f}")
        elif f.startswith("mefseg_") and cui:
            s = mefseg_by.get(cui, mefseg.iloc[:0])
            s = s[(s["fecha_registro"] <= T) & (s["fecha_registro"] > T - pd.Timedelta(days=180))]
            for x in s.sort_values("fecha_registro", ascending=False).head(4).itertuples():
                add(r, "MEF_SEGUIMIENTO", fecha=x.fecha_registro, referencia=x.tipo_registro, extracto=_s(x.descripcion)[:400])
        elif f.startswith("actor_contratista") or f.startswith("actor_entidad"):
            key = "ruc_contratista" if "contratista" in f else "ruc_entidad"
            val = cua.at[r.cuaderno_id, key] if r.cuaderno_id in cua.index else None
            if val:
                prev = actor_by[key].get(val, cua.iloc[:0])
                prev = prev[(prev.index != r.cuaderno_id) & (prev["onset"] < T)].sort_values("onset", ascending=False).head(4)
                for cid, x in prev.iterrows():
                    add(r, "HISTORIAL", fecha=x.onset, referencia=str(cid), extracto=f"{_s(x.denominacion)[:220]} ({_s(x.departamento)}) - atraso normativo el {x.onset.date()}")
        elif f.startswith("ib_"):
            add(r, "INFOBRAS", referencia="https://infobras.contraloria.gob.pe/InfobrasWeb/Mapa/Sumario?ObraId=", extracto=describe(f, r.valor))
    ev = pd.DataFrame(rows)
    dst = out / "evidencia.parquet"
    ev.to_parquet(dst, index=False)
    log.info("evidencia: %s registros", len(ev))
    return dst


def _s(v) -> str:
    return v if isinstance(v, str) else ""


def _snip(titulo, desc, n=420):
    t = f"{_s(titulo)}: {_s(desc)}".strip(": ")
    return t[:n] + ("..." if len(t) > n else "")


def _snip_match(txt, rx, n=200):
    m = rx.search(txt)
    if not m:
        return txt[: 2 * n]
    a, b = max(0, m.start() - n), min(len(txt), m.end() + n)
    return ("..." if a else "") + txt[a:b] + ("..." if b < len(txt) else "")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build(feature_set=sys.argv[1] if len(sys.argv) > 1 else "B_full", H=int(sys.argv[2]) if len(sys.argv) > 2 else 60)
