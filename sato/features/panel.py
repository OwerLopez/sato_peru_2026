"""Panel obra-mes (unidad de observacion) con elegibilidad y etiquetas.

Unidad de observacion: (cuaderno de obra, fecha de corte T), con T = ultimo
dia de cada mes. En T el sistema solo conoce asientos con fecha <= T y demas
fuentes segun docs/methodology/LEAKAGE_POLICY.md.

Elegibilidad de (obra, T) para el objetivo k:
  * historia completa del cuaderno (asiento N°1 observado) y metadatos;
  * la obra ya inicio su cuaderno (primer asiento <= T);
  * no ha ocurrido aun el evento k (prediccion del PRIMER evento / onset);
  * no ha terminado (culminacion, recepcion, cierre o resolucion) en o antes de T;
  * tuvo actividad reciente: al menos un asiento en (T-90d, T].

Etiqueta y_k_H = 1 si el onset del evento k ocurre en (T, T+H].
Observabilidad: la etiqueta solo es valida si T+H <= fin de datos (corte del
ultimo archivo de asientos); en otro caso la fila es de "inferencia" (futuro
aun no observado) y no se usa para entrenar ni evaluar.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from sato.config import CURATED, FEATURES
from sato.labels.events import TARGETS, end_dates, onset_dates

log = logging.getLogger(__name__)

HORIZONS = (30, 60, 90)
ACTIVITY_WINDOW_DAYS = 90


def build(out: Path = FEATURES) -> Path:
    cua = pd.read_parquet(CURATED / "cuaderno.parquet")
    cua = cua[cua["tiene_metadatos"] & cua["historia_completa"]].copy()
    asi = pd.read_parquet(CURATED / "asiento.parquet", columns=["cuaderno_id", "fecha", "tipo_std"])
    asi = asi[asi["cuaderno_id"].isin(cua["cuaderno_id"])].copy()
    asi["fecha"] = pd.to_datetime(asi["fecha"])
    for c in [c for c in cua.columns if c.startswith("f_") or c in ("primer_asiento", "ultimo_asiento")]:
        cua[c] = pd.to_datetime(cua[c])
    data_end = asi["fecha"].max()
    fin = end_dates(asi)
    onsets = {k: onset_dates(asi, t) for k, t in TARGETS.items()}

    cutoffs = pd.date_range(asi["fecha"].min() + pd.offsets.MonthEnd(0), data_end, freq="ME")
    # actividad: fechas de asientos por cuaderno para ventana movil
    asi_days = asi[["cuaderno_id", "fecha"]].drop_duplicates()

    rows = []
    for T in cutoffs:
        lo = T - pd.Timedelta(days=ACTIVITY_WINDOW_DAYS)
        active = set(asi_days.loc[(asi_days["fecha"] > lo) & (asi_days["fecha"] <= T), "cuaderno_id"])
        started = cua["primer_asiento"] <= T
        c = cua.loc[started & cua["cuaderno_id"].isin(active), ["cuaderno_id", "primer_asiento"]].copy()
        f = c["cuaderno_id"].map(fin)
        c = c[f.isna() | (f > T)]
        c["T"] = T
        rows.append(c[["cuaderno_id", "T"]])
    p = pd.concat(rows, ignore_index=True)
    p["data_end"] = data_end
    for k, on in onsets.items():
        o = p["cuaderno_id"].map(on)
        p[f"onset_{k}"] = o
        p[f"eligible_{k}"] = o.isna() | (o > p["T"])
        for H in HORIZONS:
            p[f"observable_{H}"] = (p["T"] + pd.Timedelta(days=H)) <= data_end
            p[f"y_{k}_{H}"] = ((o > p["T"]) & (o <= p["T"] + pd.Timedelta(days=H))).astype("int8")
            p.loc[~p[f"observable_{H}"], f"y_{k}_{H}"] = -1  # no observable (futuro)
        p[f"dias_hasta_onset_{k}"] = (o - p["T"]).dt.days
    p = p.merge(cua[["cuaderno_id", "dep_code", "cui"]], on="cuaderno_id", how="left")
    dst = out / "panel.parquet"
    p.to_parquet(dst, index=False)
    log.info("panel: %s filas, %s cuadernos, cortes %s..%s", len(p), p["cuaderno_id"].nunique(), cutoffs.min().date(), cutoffs.max().date())
    return dst


def summarize(p: pd.DataFrame) -> pd.DataFrame:
    out = []
    for k in TARGETS:
        for H in HORIZONS:
            m = p[f"eligible_{k}"] & p[f"observable_{H}"]
            for scope, s in (("NACIONAL", m), ("AREQUIPA", m & (p["dep_code"] == "04"))):
                y = p.loc[s, f"y_{k}_{H}"]
                out.append(dict(target=k, H=H, scope=scope, filas=int(s.sum()), obras=int(p.loc[s, "cuaderno_id"].nunique()),
                                positivos=int((y == 1).sum()), obras_positivas=int(p.loc[s & (p[f"y_{k}_{H}"] == 1), "cuaderno_id"].nunique()),
                                prevalencia=float(np.round((y == 1).mean(), 4))))
    return pd.DataFrame(out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    d = build()
    print(summarize(pd.read_parquet(d)).to_string())
