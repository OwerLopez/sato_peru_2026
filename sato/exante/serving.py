"""Publicacion de los modelos de CARTERA (INFOBRAS, todas las modalidades y sectores).

Salidas en artifacts/cartera/:
  * obras.parquet          : cartera nacional de obras INFOBRAS con estado operativo derivado.
  * riesgo.parquet         : predicciones as-of
        - tipo `inicio`      : riesgo al inicio de la obra (modelo ex-ante). Cada obra iniciada en el anio Y se
                               puntua con un modelo entrenado SOLO con obras cuyo resultado se conocia antes del
                               01-01-Y (reentrenamiento anual). Nunca se usa informacion posterior al inicio.
        - tipo `seguimiento` : riesgo mensual durante la ejecucion (ex-ante + SIAF), cada corte T del anio Y con un
                               modelo entrenado con cortes anteriores a Y cuyo resultado se conocia antes de Y.
  * explicaciones.parquet  : top-6 TreeSHAP de las predicciones de obras activas y recientes.
  * cartera_card.json      : umbrales de nivel (elegidos con predicciones fuera de tiempo previas al test) y metricas.

Estado operativo (dataset INFOBRAS con registros hasta OBS_END = 2026-03-31):
  * ACTIVA      : en ejecucion/paralizada, sin fin real y con registro de avance en los 12 meses previos a OBS_END.
  * CONSUMADO   : activa cuyo limite de retraso significativo (fin programado + 30 % del plazo) ya vencio.
  * FINALIZADA  : con fecha real de fin.
  * DESACTUALIZADA : en ejecucion sin registros recientes (no se evalua: estado real desconocido).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from sato.config import ARTIFACTS, FEATURES, STAGING
from sato.exante.seguimiento import OBS_END as SEG_OBS_END
from sato.exante.train import make, text_scores
from sato.serving.descriptions_cartera import describe_c, group_c

log = logging.getLogger(__name__)
OUT = ARTIFACTS / "cartera"
OBS_END = pd.Timestamp("2026-03-31")
ACTIVIDAD_DESDE = OBS_END - pd.DateOffset(months=12)
TOP_K = 6


def estado_operativo(d: pd.DataFrame) -> pd.Series:
    fin = d["fecha_de_finalizacion_real"].notna()
    ejec = d["estado_de_ejecucion"].str.startswith(("En Ejec", "Paraliz"), na=False)
    reciente = d["fecha_de_registro_de_avance"] >= ACTIVIDAD_DESDE
    lim = d["fecha_de_inicio_de_obra"] + pd.to_timedelta(np.ceil(d["plazo_de_ejecucion_en_dias"] * 1.3), unit="D")
    e = np.select([fin, ejec & reciente & (lim < OBS_END), ejec & reciente, ejec], ["FINALIZADA", "CONSUMADO", "ACTIVA", "DESACTUALIZADA"], "OTRO")
    return pd.Series(e, index=d.index)


def _explain(model, X: pd.DataFrame, ids: pd.DataFrame, tipo: str) -> list[dict]:
    S = model.booster_.predict(X, pred_contrib=True)[:, :-1]
    cols = list(X.columns)
    out = []
    for j in range(len(X)):
        order = np.argsort(-np.abs(S[j]))[:TOP_K]
        for r, k in enumerate(order):
            v = X.iat[j, k]
            vnum = float(v) if isinstance(v, (int, float, np.floating, np.integer)) and not pd.isna(v) else None
            out.append(dict(codigo_infobras=ids.iat[j, 0], T=ids.iat[j, 1], tipo=tipo, rango=r + 1, feature=cols[k], grupo=group_c(cols[k]),
                            valor=vnum, shap=float(S[j, k]), descripcion=describe_c(cols[k], vnum if vnum is not None else (None if pd.isna(v) else str(v)))))
    return out


def inicio(res_params: dict) -> tuple[pd.DataFrame, list[dict]]:
    d = pd.read_parquet(FEATURES / "exante_dataset.parquet")
    d["y"] = d["y_30"]
    d["known"] = d["known_30"]
    feats = [c for c in d.columns if c.startswith(("ea_", "hist_"))]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(d[c])]
    for c in cats:
        d[c] = d[c].astype("category")
    ib = pd.read_parquet(STAGING / "infobras_obras.parquet", columns=["codigo_infobras", "fecha_de_registro_de_avance"])
    d = d.merge(ib.drop_duplicates("codigo_infobras"), on="codigo_infobras", how="left")
    d["estado_operativo"] = estado_operativo(d)
    groups = d["codigo_entidad"].fillna("NA")
    year = d["fecha_de_inicio_de_obra"].dt.year
    preds, expl = [], []
    for Y in range(2016, 2027):
        cut = pd.Timestamp(Y, 1, 1)
        fit = d["y"].notna() & (d["known"] < cut)
        sel = year == Y
        if sel.sum() == 0:
            continue
        dd = d.copy()
        dd["y"] = dd["y"].fillna(0).astype(int)
        txt, _ = text_scores(dd, fit, groups)
        X = d[feats].copy()
        X["ea_txt_nombre"] = txt
        f2 = feats + ["ea_txt_nombre"]
        m = make("lgbm", f2, cats, res_params)
        m.fit(X.loc[fit, f2], d.loc[fit, "y"].astype(int))
        p = d.loc[sel, ["codigo_infobras", "fecha_de_inicio_de_obra", "y"]].rename(columns={"fecha_de_inicio_de_obra": "T"})
        p["score"] = m.predict_proba(X.loc[sel, f2])[:, 1]
        p["modelo_origen"] = str(cut.date())
        preds.append(p)
        rec = sel & ((d["fecha_de_inicio_de_obra"] >= "2022-01-01") | d["estado_operativo"].isin(["ACTIVA", "CONSUMADO"]))
        if rec.sum():
            ids = d.loc[rec, ["codigo_infobras", "fecha_de_inicio_de_obra"]]
            expl += _explain(m, X.loc[rec, f2], ids, "inicio")
        log.info("inicio: anio %s, entrenado con %s obras, %s puntuadas", Y, int(fit.sum()), int(sel.sum()))
    P = pd.concat(preds)
    P["tipo"] = "inicio"
    return P, expl, d


def seguimiento(params: dict, d_obras: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    from sato.exante.seguimiento import panel_for

    lab = pd.read_parquet(FEATURES / "seguimiento_panel.parquet")
    act = d_obras[d_obras["estado_operativo"] == "ACTIVA"]
    cur = panel_for(act["codigo_infobras"], end=OBS_END)
    cur = cur[~cur["codigo_infobras"].isin(lab["codigo_infobras"])]  # activas sin etiqueta aun
    d = pd.concat([lab, cur], ignore_index=True)
    d["y"] = d["y_30"]
    d["known"] = d["known_30"]
    feats = [c for c in lab.columns if c.startswith(("ea_", "hist_", "sg_"))]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(d[c])]
    for c in cats:
        d[c] = d[c].astype("category")
    preds, expl = [], []
    for Y in range(2019, 2027):
        cut = pd.Timestamp(Y, 1, 1)
        fit = d["y"].notna() & (d["T"] < cut) & (d["known"] < cut)
        sel = d["T"].dt.year == Y
        if sel.sum() == 0 or fit.sum() < 1000:
            continue
        m = make("lgbm", feats, cats, params)
        m.fit(d.loc[fit, feats], d.loc[fit, "y"].astype(int))
        p = d.loc[sel, ["codigo_infobras", "T", "y"]].copy()
        p["score"] = m.predict_proba(d.loc[sel, feats])[:, 1]
        p["modelo_origen"] = str(cut.date())
        preds.append(p)
        # ultimo corte disponible de cada obra activa (el SIAF llega con un mes de rezago, por lo que puede ser anterior a OBS_END)
        es_act = sel & d["codigo_infobras"].isin(act["codigo_infobras"])
        last = es_act & (d["T"] == d["T"].where(es_act).groupby(d["codigo_infobras"]).transform("max"))
        if last.sum():
            expl += _explain(m, d.loc[last, feats], d.loc[last, ["codigo_infobras", "T"]], "seguimiento")
        log.info("seguimiento: anio %s, entrenado con %s filas, %s puntuadas", Y, int(fit.sum()), int(sel.sum()))
    P = pd.concat(preds)
    P["tipo"] = "seguimiento"
    return P, expl


def build(out: Path = OUT) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    r_ini = json.loads((ARTIFACTS / "exante" / "resultados_y_30.json").read_text(encoding="utf-8"))
    r_seg = json.loads((ARTIFACTS / "exante" / "resultados_seguimiento.json").read_text(encoding="utf-8"))
    P1, e1, d = inicio(r_ini["modelos"]["lgbm"]["params"])
    P2, e2 = seguimiento(r_seg["modelos"]["seguimiento_lgbm"]["params"], d)
    card = {"obs_end": str(OBS_END.date()), "actividad_desde": str(ACTIVIDAD_DESDE.date()), "umbrales": {},
            "metricas_test": {"inicio": r_ini["modelos"], "seguimiento": r_seg["modelos"]},
            "periodos": {"inicio": r_ini["periodos"], "seguimiento": r_seg["periodos"]}}
    P = []
    for tipo, p, test_start in (("inicio", P1, "2022-01-01"), ("seguimiento", P2, "2024-01-01")):
        # Niveles por cuantiles de predicciones FUERA DE TIEMPO anteriores al periodo de test:
        # ALTO = 20 % de mayor riesgo, MEDIO = siguiente 30 %, BAJO = 50 % restante.
        ref = p[p["y"].notna() & (p["T"] < test_start)]
        alto, medio = float(ref["score"].quantile(0.80)), float(ref["score"].quantile(0.50))
        p = p.copy()
        p["nivel"] = np.where(p["score"] >= alto, "ALTO", np.where(p["score"] >= medio, "MEDIO", "BAJO"))
        tst = p[p["y"].notna() & (p["T"] >= test_start)]
        calib = {n: {"filas": int((tst["nivel"] == n).sum()), "tasa_retraso_observada": float(tst.loc[tst["nivel"] == n, "y"].mean())}
                 for n in ("ALTO", "MEDIO", "BAJO")}
        card["umbrales"][tipo] = {"alto": alto, "medio": medio, "filas_referencia": int(len(ref)), "periodo_test_desde": test_start,
                                  "tasa_base_test": float(tst["y"].mean()), "tasa_por_nivel_test": calib}
        P.append(p)
    P = pd.concat(P, ignore_index=True)
    P["y_observado"] = P["y"]
    P = P.drop(columns="y")
    keep = ["codigo_infobras", "codigo_unico_de_inversion", "nombre_de_obra", "entidad_publica", "codigo_entidad", "ruc_ejecucion",
            "nombre_o_razon_social_de_la_empresa_o_consorcio", "departamento", "provincia", "distrito", "estado_de_ejecucion",
            "estado_operativo", "fecha_de_inicio_de_obra", "plazo_de_ejecucion_en_dias", "fin_prog", "fecha_de_finalizacion_real",
            "sobreplazo", "costo_de_obra_en_soles_segun_et_en_soles", "modalidad_de_ejecucion_de_la_obra", "tipo_de_obra_clasificador_nivel_1",
            "y_30"]
    obras = d[keep].copy()
    for c in obras.columns:
        if isinstance(obras[c].dtype, pd.CategoricalDtype):
            obras[c] = obras[c].astype(str)
    obras.to_parquet(out / "obras.parquet", index=False)
    P.to_parquet(out / "riesgo.parquet", index=False)
    pd.DataFrame(e1 + e2).to_parquet(out / "explicaciones.parquet", index=False)
    (out / "cartera_card.json").write_text(json.dumps(card, indent=1, default=str), encoding="utf-8")
    log.info("cartera: %s obras, %s predicciones, %s explicaciones; activas %s", len(obras), len(P), len(e1) + len(e2),
             int((obras["estado_operativo"] == "ACTIVA").sum()))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build()
    assert SEG_OBS_END == OBS_END
