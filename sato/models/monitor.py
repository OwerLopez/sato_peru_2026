"""Monitoreo de datos y del modelo (drift) para la actualizacion mensual.

    python -m sato.models.monitor

Genera artifacts/monitoring/reporte.json con:
  * cobertura mensual de fuentes (asientos, cuadernos activos, % con CUI) y variacion vs. promedio de 6 meses;
  * tipos de asiento sin armonizar (catalogo nuevo de OECE);
  * PSI (Population Stability Index) de las features mas importantes: periodo de entrenamiento del modelo
    operativo vs. ultimo corte; PSI > 0.25 => reentrenar (regla usual en riesgo de credito);
  * desempeno realizado de las predicciones cuyo horizonte ya vencio (PR-AUC y recall por corte).
Las alertas de drift se listan en `alertas`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from sato.config import ARTIFACTS, CURATED, FEATURES
from sato.models.evaluate import safe_ap

log = logging.getLogger(__name__)
OUT = ARTIFACTS / "monitoring"


def psi(ref: pd.Series, cur: pd.Series, bins: int = 10) -> float:
    ref, cur = ref.dropna().astype(float), cur.dropna().astype(float)
    if len(ref) < 50 or len(cur) < 20:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return float("nan")
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / len(cur)
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def report(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    alertas = []
    asi = pd.read_parquet(CURATED / "asiento.parquet", columns=["cuaderno_id", "fecha", "tipo_std"])
    asi["mes"] = pd.to_datetime(asi["fecha"]).dt.to_period("M").astype(str)
    cob = asi.groupby("mes").agg(asientos=("cuaderno_id", "size"), cuadernos_activos=("cuaderno_id", "nunique")).reset_index()
    cob["var_vs_6m"] = cob["asientos"] / cob["asientos"].rolling(6, min_periods=3).mean().shift(1) - 1
    last = cob.iloc[-1]
    if pd.notna(last["var_vs_6m"]) and last["var_vs_6m"] < -0.2:
        alertas.append(f"Caida de {last['var_vs_6m']:.0%} en asientos publicados en {last['mes']}")
    sin_map = asi.loc[asi["tipo_std"] == "OTRO", "mes"].value_counts().to_dict()
    if sin_map:
        alertas.append(f"Tipos de asiento sin armonizar: {sin_map}")

    res = {"cobertura_mensual": cob.tail(12).to_dict("records"), "tipos_sin_armonizar": sin_map}
    card_p = ARTIFACTS / "release" / "modelo_card.json"
    if card_p.exists():
        card = json.loads(card_p.read_text(encoding="utf-8"))
        feats = pd.read_parquet(FEATURES / "features_structured.parquet")
        for f in ("features_text_lexicon.parquet",):
            if (FEATURES / f).exists():
                feats = feats.merge(pd.read_parquet(FEATURES / f), on=["cuaderno_id", "T"], how="left")
        cols = [c for c in card["features"] if c in feats.columns and pd.api.types.is_numeric_dtype(feats[c]) and not c.startswith("tmp_")]  # calendario: PSI trivial
        ref = feats[feats["T"] <= pd.Timestamp(card["entrenado_hasta"])]
        cur = feats[feats["T"] == feats["T"].max()]
        ps = {c: psi(ref[c], cur[c]) for c in cols}
        ps = dict(sorted(((k, v) for k, v in ps.items() if not np.isnan(v)), key=lambda kv: -kv[1]))
        res["psi_ultimo_corte"] = {k: round(v, 4) for k, v in list(ps.items())[:25]}
        altos = {k: v for k, v in ps.items() if v > 0.25}
        if altos:
            alertas.append(f"PSI > 0.25 en {len(altos)} features: {list(altos)[:8]} -> evaluar reentrenamiento")
        preds = ARTIFACTS / "release" / "predicciones.parquet"
        if preds.exists():
            p = pd.read_parquet(preds)
            p = p[p["y_observado"].notna()]
            perf = []
            for T, g in p.groupby("T"):
                y = g["y_observado"].to_numpy()
                perf.append(dict(T=str(pd.Timestamp(T).date()), n=len(g), eventos=int(y.sum()), pr_auc=float(safe_ap(y, g["score"].to_numpy())),
                                 recall_alerta=float(((g["alerta"]) & (y == 1)).sum() / max(1, y.sum()))))
            res["desempeno_realizado"] = perf
    res["alertas"] = alertas
    (out / "reporte.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log.info("monitoreo: %s alertas", len(alertas))
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    r = report()
    print(json.dumps({k: r[k] for k in ("alertas", "tipos_sin_armonizar")}, indent=1, ensure_ascii=False))
    print("PSI top:", list(r.get("psi_ultimo_corte", {}).items())[:8])
