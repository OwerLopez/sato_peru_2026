"""Modelo de SEGUIMIENTO mensual (durante la ejecucion) con la ejecucion financiera SIAF.

Cubre TODAS las modalidades y sectores de INFOBRAS (contrata, administracion directa, nucleo ejecutor...),
a diferencia del modelo de cuaderno de obra digital (solo contratos 2024+).

Unidad: obra-mes. Obras con CUI propia (una sola obra INFOBRAS por CUI, para atribuir el gasto sin ambiguedad)
y ejecucion SIAF. Cortes T = fin de mes desde el inicio de la obra hasta que termina o vence el limite
de retraso significativo (fin programado + 30 % del plazo), sin superar OBS_END.

Pregunta en T: ¿la obra terminara con RETRASO SIGNIFICATIVO (etiqueta y_30 del modelo ex-ante)?
Features en T = features ex-ante (fijadas al inicio) + dinamicas SIAF (meses < mes de T):
  fraccion del plazo transcurrida, dias al fin programado, devengado acumulado y desde el inicio / costo,
  devengado de 3 meses / costo, meses sin devengado, brecha de ritmo (devengado/costo - plazo transcurrido),
  PIA del anio / costo.

Validacion temporal: TEST = cortes en 2024-01..2025-12. TRAIN+VALID = cortes < 2024-01-01 de obras cuyo
resultado se conocia antes del 2024-01-01; VALID = cortes de 2023; TRAIN = cortes < 2023 con resultado
conocido antes de 2023. Se reporta el desempeno por etapa (fraccion del plazo transcurrida).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

from sato.config import FEATURES, STAGING
from sato.exante.train import OUT, fit_select, make
from sato.models.evaluate import cluster_bootstrap, point_metrics, precision_at_k, threshold_for_fbeta

log = logging.getLogger(__name__)
TEST_START, TEST_END, VALID_START = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31"), pd.Timestamp("2023-01-01")
OBS_END = pd.Timestamp("2026-03-31")


def panel_for(codigos=None, end: pd.Timestamp = OBS_END, labeled_only: bool = False) -> pd.DataFrame:
    """Panel obra-mes con features ex-ante + SIAF para las obras indicadas (CUI propia), cortes hasta `end`."""
    ds = pd.read_parquet(FEATURES / "exante_dataset.parquet")
    cnt = ds.groupby("codigo_unico_de_inversion").size()
    ds = ds[ds["codigo_unico_de_inversion"].map(cnt).eq(1)].copy()
    if labeled_only:
        ds = ds[ds["y_30"].notna()]
    if codigos is not None:
        ds = ds[ds["codigo_infobras"].isin(set(codigos))]
    ds = ds[ds["fecha_de_inicio_de_obra"] >= "2017-07-01"]
    ds["lim"] = ds["fecha_de_inicio_de_obra"] + pd.to_timedelta(np.ceil(ds["plazo_de_ejecucion_en_dias"] * 1.3), unit="D")
    ds["fin_obs"] = ds[["fecha_de_finalizacion_real", "lim"]].min(axis=1).clip(upper=end)
    if not labeled_only:  # obras activas: se evalua hasta `end` inclusive
        ds["fin_obs"] = ds["fin_obs"].where(ds["fecha_de_finalizacion_real"].notna() | ds["y_30"].notna(), end + pd.Timedelta(days=1))
    con = duckdb.connect()
    con.register("obras", ds[["codigo_infobras", "codigo_unico_de_inversion", "fecha_de_inicio_de_obra", "fin_obs", "fin_prog",
                              "plazo_de_ejecucion_en_dias", "costo_de_obra_en_soles_segun_et_en_soles"]])
    con.sql("""create table cortes as
        select o.codigo_infobras, o.codigo_unico_de_inversion cui, t::date "T", o.fecha_de_inicio_de_obra::date s, o.fin_prog::date fin_prog,
               o.plazo_de_ejecucion_en_dias plazo, nullif(o.costo_de_obra_en_soles_segun_et_en_soles, 0) costo
        from obras o, generate_series(last_day(o.fecha_de_inicio_de_obra::date), o.fin_obs::date - 1, interval 1 month) g(t)
        where last_day(t::date) = t::date""")
    siaf_glob = (STAGING / "siaf").as_posix() + "/*.parquet"
    con.sql(f"""create table siaf as select cui, make_date(anio, mes, 1) m, sum(monto_devengado) dev
                from read_parquet('{siaf_glob}') where mes between 1 and 12 group by all""")
    con.sql(f"""create table pia as select cui, anio, sum(monto_pia) pia from read_parquet('{siaf_glob}') where mes = 0 group by all""")
    df = con.sql("""
        select c.codigo_infobras, c."T",
          (c."T" - c.s) / c.plazo as sg_frac_plazo,
          c.fin_prog - c."T" as sg_dias_al_fin_prog,
          sum(f.dev) / c.costo as sg_dev_acum_costo,
          sum(f.dev) filter (where f.m >= date_trunc('month', c.s)) / c.costo as sg_dev_desde_inicio_costo,
          sum(f.dev) filter (where f.m >= date_trunc('month', c."T") - interval 3 month) / c.costo as sg_dev_3m_costo,
          date_diff('month', max(f.m) filter (where f.dev > 0), date_trunc('month', c."T")) as sg_meses_sin_dev,
          count(*) filter (where f.dev > 0 and f.m >= date_trunc('month', c.s)) as sg_meses_con_dev
        from cortes c left join siaf f on f.cui = c.cui and f.m < date_trunc('month', c."T")
        group by c.codigo_infobras, c."T", c.s, c.plazo, c.fin_prog, c.costo
    """).df()
    p = con.sql("""select c.codigo_infobras, c."T", p.pia / c.costo as sg_pia_anio_costo
                   from cortes c join pia p on p.cui = c.cui and p.anio = year(c."T")""").df()
    df = df.merge(p, on=["codigo_infobras", "T"], how="left")
    df["T"] = pd.to_datetime(df["T"])
    df["sg_brecha_ritmo"] = df["sg_dev_desde_inicio_costo"] - df["sg_frac_plazo"]
    df["sg_vencido"] = (df["sg_dias_al_fin_prog"] < 0).astype(int)
    return df.merge(ds.drop(columns=["lim", "fin_obs"]), on="codigo_infobras", how="left")


def build_panel(out: Path = FEATURES) -> Path:
    df = panel_for(labeled_only=True)
    dst = out / "seguimiento_panel.parquet"
    df.to_parquet(dst, index=False)
    log.info("panel seguimiento: %s filas, %s obras", len(df), df["codigo_infobras"].nunique())
    return dst


def run(out: Path = OUT) -> dict:
    t0 = time.time()
    d = pd.read_parquet(FEATURES / "seguimiento_panel.parquet")
    d["y"] = d["y_30"].astype(int)
    d["known"] = d["known_30"]
    feats = [c for c in d.columns if c.startswith(("ea_", "hist_", "sg_"))]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(d[c])]
    for c in cats:
        d[c] = d[c].astype("category")
    T = d["T"]
    test = (T >= TEST_START) & (T <= TEST_END)
    trainval = (T < TEST_START) & (d["known"] < TEST_START)
    valid = trainval & (T >= VALID_START)
    train = (T < VALID_START) & (d["known"] < VALID_START)
    X, y = d[feats], d["y"].to_numpy()
    res = {"n_features": len(feats), "features": feats, "periodos": {k: [str(T[m].min().date()), str(T[m].max().date()), int(m.sum()),
           int(d.loc[m, "codigo_infobras"].nunique()), float(d.loc[m, "y"].mean())] for k, m in (("train", train), ("valid", valid), ("test", test))},
           "modelos": {}}
    preds = d.loc[test, ["codigo_infobras", "T", "departamento", "y", "codigo_entidad", "sg_frac_plazo"]].copy()
    for name, featset in (("exante_lgbm", [f for f in feats if not f.startswith("sg_")]), ("seguimiento_lgbm", feats)):
        c2 = [c for c in cats if c in featset]
        _, p, s_va = fit_select("lgbm", featset, c2, X.loc[train, featset], y[train], X.loc[valid, featset], y[valid])
        m = make("lgbm", featset, c2, p)
        m.fit(X.loc[trainval, featset], y[trainval])
        preds[f"s_{name}"] = m.predict_proba(X.loc[test, featset])[:, 1]
        thr = threshold_for_fbeta(y[valid], s_va, beta=1.0)
        mres = {"params": p, "umbral_f1_valid": thr}
        for ts, tm in (("arequipa", preds["departamento"] == "AREQUIPA"), ("nacional", pd.Series(True, index=preds.index))):
            yt, st = preds.loc[tm, "y"].to_numpy(), preds.loc[tm, f"s_{name}"].to_numpy()
            pm = point_metrics(yt, st, thr)
            pm["precision_top20"], pm["recall_top20"] = precision_at_k(yt, st, 0.2)
            etapas = {}
            for lo, hi in ((0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 9)):
                sm = tm & preds["sg_frac_plazo"].between(lo, hi, inclusive="left")
                ye, se = preds.loc[sm, "y"].to_numpy(), preds.loc[sm, f"s_{name}"].to_numpy()
                if len(np.unique(ye)) == 2:
                    etapas[f"{int(lo*100)}-{int(hi*100) if hi < 9 else 'mas'}%"] = point_metrics(ye, se, thr) | {"filas": int(sm.sum())}
            pm["por_etapa"] = etapas
            mres[ts] = pm
        res["modelos"][name] = mres
        joblib.dump({"model": m, "features": featset, "cats": c2, "params": p, "umbral": thr}, out / f"modelo_{name}.joblib")
        log.info("%s | AQP AUC=%.3f AP=%.3f | NAC AUC=%.3f AP=%.3f", name, mres["arequipa"]["roc_auc"], mres["arequipa"]["pr_auc"],
                 mres["nacional"]["roc_auc"], mres["nacional"]["pr_auc"])
    for ts, tm in (("arequipa", preds["departamento"] == "AREQUIPA"), ("nacional", pd.Series(True, index=preds.index))):
        b = preds.loc[tm].rename(columns={"codigo_infobras": "cuaderno_id"})
        res[f"bootstrap_{ts}"] = cluster_bootstrap(b, ["s_exante_lgbm", "s_seguimiento_lgbm"], n_boot=300).to_dict("records")
    res["segundos"] = round(time.time() - t0, 1)
    preds.to_parquet(out / "predicciones_test_seguimiento.parquet", index=False)
    (out / "resultados_seguimiento.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if len(sys.argv) < 2 or sys.argv[1] == "panel":
        build_panel()
    if len(sys.argv) < 2 or sys.argv[1] == "run":
        run()
