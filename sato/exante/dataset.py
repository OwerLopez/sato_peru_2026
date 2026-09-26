"""Dataset del modelo EX-ANTE (riesgo al inicio de la obra) sobre INFOBRAS nacional.

Unidad: obra registrada en INFOBRAS (todas las modalidades y sectores).
Momento de prediccion: fecha de inicio de obra `s` (solo informacion conocida en `s`).

Evento objetivo -- RETRASO SIGNIFICATIVO AL TERMINO:
    la obra culmina despues de  fin_programada_original + UMBRAL x plazo_original
    (UMBRAL principal = 30 %; sensibilidad 10 %, 50 %, 100 %).
Determinacion de la etiqueta (sin inventar estados):
  * fin real registrado:  y = 1 si fin_real > limite, y = 0 si fin_real <= limite.
  * sin fin real (en ejecucion / paralizada): y = 1 SOLO si hay evidencia de que seguia
    sin terminar despues del limite (ultimo registro de avance > limite, o paralizacion
    registrada antes del limite); si no hay evidencia, la obra se EXCLUYE (registro abandonado).
  * Solo cohortes cuyo limite vence antes de OBS_END (fin efectivo de registros del dataset,
    2026-03-31 segun la fecha maxima de registro de avance).
Fecha en que el resultado se conoce (para historiales sin fuga): fin_real si y=0; limite si y=1.

Features (todas conocidas en `s`):
  * INFOBRAS fijados al inicio: modalidad, naturaleza, tipo de obra (3 niveles), nivel de gobierno,
    sector de la entidad, departamento, plazo, costo segun expediente, monto de contrato, relacion
    contrato/expediente, supervision contratada, terreno entregado, dias desde aprobacion del expediente,
    saldo de obra, marcas de reconstruccion/reactivacion, mes y anio de inicio.
  * MEF (Banco de Inversiones, atributos de formulacion): monto viable, tipo de inversion, marco,
    funcion, dias entre viabilidad e inicio.
  * Historial as-of (nacional, INFOBRAS): de la ENTIDAD, del CONTRATISTA (RUC) y de la PROVINCIA:
    obras previas, obras con resultado conocido antes de `s`, tasa de retraso significativo (suavizada),
    sobre-plazo mediano, obras en curso en `s` (carga de trabajo).
PROHIBIDOS: avance, paralizacion, modificaciones, adicionales, fechas reprogramadas/reales, costos actualizados.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from sato.config import FEATURES, STAGING

log = logging.getLogger(__name__)

OBS_END = pd.Timestamp("2026-03-31")
UMBRALES = (0.10, 0.30, 0.50, 1.00)
UMBRAL = 0.30
PRIOR_N = 5  # suavizado bayesiano de tasas historicas


def _base() -> pd.DataFrame:
    d = pd.read_parquet(STAGING / "infobras_obras.parquet")
    d = d[d["fecha_de_inicio_de_obra"].notna() & d["plazo_de_ejecucion_en_dias"].between(7, 2500)].copy()
    d = d[~d["estado_de_ejecucion"].str.startswith("Sin Ejec", na=False)]
    d = d[(d["fecha_de_inicio_de_obra"] >= "2012-01-01") & (d["fecha_de_inicio_de_obra"] <= OBS_END)]
    fr = d["fecha_de_finalizacion_real"]
    d.loc[fr.notna() & (fr < d["fecha_de_inicio_de_obra"]), "fecha_de_finalizacion_real"] = pd.NaT  # fecha imposible
    d["fin_prog"] = d["fecha_de_inicio_de_obra"] + pd.to_timedelta(d["plazo_de_ejecucion_en_dias"], unit="D")
    d["sobreplazo"] = (d["fecha_de_finalizacion_real"] - d["fin_prog"]).dt.days / d["plazo_de_ejecucion_en_dias"]
    return d


def label(d: pd.DataFrame, umbral: float) -> tuple[pd.Series, pd.Series]:
    lim = d["fecha_de_inicio_de_obra"] + pd.to_timedelta(np.ceil(d["plazo_de_ejecucion_en_dias"] * (1 + umbral)), unit="D")
    fr = d["fecha_de_finalizacion_real"]
    y = pd.Series(np.nan, index=d.index)
    known = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns]")
    fin = fr.notna()
    y[fin & (fr <= lim)] = 0
    known[fin & (fr <= lim)] = fr
    y[fin & (fr > lim)] = 1
    known[fin & (fr > lim)] = lim
    evid = (~fin) & ((d["fecha_de_registro_de_avance"] > lim) | ((d["existe_paralizacion"] == "Si") & (d["fecha_de_paralizacion"] <= lim)))
    y[evid] = 1
    known[evid] = lim
    ok = lim <= OBS_END
    y[~ok & (y == 1)] = np.nan  # solo cohortes con limite vencido dentro de la ventana observable
    known[y.isna()] = pd.NaT
    return y, known


def _history(d: pd.DataFrame, key: str, prefix: str) -> pd.DataFrame:
    """Historial as-of de un actor: solo resultados conocidos ANTES del inicio de cada obra."""
    out = pd.DataFrame(index=d.index)
    sub = d[d[key].notna()][[key, "fecha_de_inicio_de_obra", "_y", "_known", "sobreplazo", "fecha_de_finalizacion_real", "fin_prog"]]
    base_rate = d["_y"].mean()
    res = {f"{prefix}_obras_previas": [], f"{prefix}_resultados_previos": [], f"{prefix}_tasa_retraso": [],
           f"{prefix}_sobreplazo_mediano": [], f"{prefix}_en_curso": []}
    idx = []
    for _, g in sub.groupby(key, sort=False):
        g = g.sort_values("fecha_de_inicio_de_obra")
        starts = g["fecha_de_inicio_de_obra"].to_numpy()
        kn = g["_known"].to_numpy()
        yy = g["_y"].to_numpy()
        sp = g["sobreplazo"].to_numpy()
        end = g["fecha_de_finalizacion_real"].fillna(g["fin_prog"]).to_numpy()
        for s in starts:
            prev = starts < s
            kmask = (~pd.isna(kn)) & (kn < s)
            n_known = int(kmask.sum())
            pos = float(np.nansum(yy[kmask])) if n_known else 0.0
            res[f"{prefix}_obras_previas"].append(int(prev.sum()))
            res[f"{prefix}_resultados_previos"].append(n_known)
            res[f"{prefix}_tasa_retraso"].append((pos + PRIOR_N * base_rate) / (n_known + PRIOR_N))
            spk = sp[kmask & ~np.isnan(sp) & (g["fecha_de_finalizacion_real"].to_numpy() < s)] if n_known else np.array([])
            res[f"{prefix}_sobreplazo_mediano"].append(float(np.median(spk)) if len(spk) else np.nan)
            res[f"{prefix}_en_curso"].append(int((prev & (end >= s)).sum()))
        idx.extend(g.index)
    h = pd.DataFrame(res, index=idx)
    return out.join(h)


def build(out: Path = FEATURES) -> Path:
    d = _base()
    for u in UMBRALES:
        y, k = label(d, u)
        d[f"y_{int(u * 100)}"] = y
        d[f"known_{int(u * 100)}"] = k
    d["_y"], d["_known"] = d[f"y_{int(UMBRAL * 100)}"], d[f"known_{int(UMBRAL * 100)}"]
    mef = pd.read_parquet(STAGING / "mef_inversiones.parquet", columns=["cui", "monto_viable", "tipo_inversion", "marco", "funcion", "fecha_viabilidad", "nivel"])
    d = d.merge(mef.rename(columns={"cui": "codigo_unico_de_inversion"}), on="codigo_unico_de_inversion", how="left")
    s = d["fecha_de_inicio_de_obra"]
    f = pd.DataFrame(index=d.index)
    cat = {
        "modalidad": "modalidad_de_ejecucion_de_la_obra", "naturaleza": "naturaleza_de_la_obra", "tipo1": "tipo_de_obra_clasificador_nivel_1",
        "tipo2": "tipo_de_obra_clasificador_nivel_2", "tipo3": "tipo_de_obra_clasificador_nivel_3", "nivel_gobierno": "nivel_de_gobierno",
        "sector_entidad": "sector_de_la_entidad", "departamento": "departamento", "tipo_inversion": "tipo_inversion", "marco": "marco", "funcion": "funcion",
    }
    for k, c in cat.items():
        f[f"ea_{k}"] = d[c].fillna("NA").astype(str)
    f["ea_log_plazo"] = np.log(d["plazo_de_ejecucion_en_dias"])
    f["ea_log_costo_et"] = np.log1p(d["costo_de_obra_en_soles_segun_et_en_soles"].where(lambda x: x > 0))
    f["ea_log_monto_contrato"] = np.log1p(d["monto_del_contrato_en_soles"].where(lambda x: x > 0))
    f["ea_ratio_contrato_et"] = (d["monto_del_contrato_en_soles"] / d["costo_de_obra_en_soles_segun_et_en_soles"]).where(lambda x: (x > 0.2) & (x < 5))
    f["ea_log_monto_viable"] = np.log1p(d["monto_viable"].where(lambda x: x > 0))
    f["ea_costo_por_dia"] = np.log1p(d["costo_de_obra_en_soles_segun_et_en_soles"] / d["plazo_de_ejecucion_en_dias"])
    f["ea_con_supervision"] = d["ruc_supervision"].notna().astype(int)
    f["ea_terreno_entregado"] = d["porcentaje_de_terreno_entregado"]
    f["ea_entrega_parcial"] = (d["tipo_de_entrega"] == "Parcial").astype(int)
    f["ea_dias_expediente_inicio"] = (s - d["fecha_de_aprobacion_del_expediente"]).dt.days.where(lambda x: x.between(-400, 5000))
    f["ea_dias_viabilidad_inicio"] = (s - pd.to_datetime(d["fecha_viabilidad"])).dt.days.where(lambda x: x.between(-400, 8000))
    f["ea_saldo_de_obra"] = (d["corresponde_a_un_saldo_de_obra"] == "SI").astype(int)
    f["ea_reconstruccion"] = (d["marca_reconstruccion_con_cambios_si_no"] == "Si").astype(int)
    f["ea_reactivacion"] = (d["marca_reactivacion_economicas_si_no"] == "Si").astype(int)
    f["ea_mes_inicio"] = s.dt.month
    f["ea_anio_inicio"] = s.dt.year
    f["ea_tiene_cui"] = d["codigo_unico_de_inversion"].notna().astype(int)
    for key, pre in (("codigo_entidad", "hist_entidad"), ("ruc_ejecucion", "hist_contratista"), ("provincia", "hist_provincia")):
        f = f.join(_history(d, key, pre))
    keep = ["codigo_infobras", "codigo_unico_de_inversion", "nombre_de_obra", "entidad_publica", "codigo_entidad", "ruc_ejecucion",
            "nombre_o_razon_social_de_la_empresa_o_consorcio", "departamento", "provincia", "distrito", "estado_de_ejecucion",
            "fecha_de_inicio_de_obra", "plazo_de_ejecucion_en_dias", "fin_prog", "fecha_de_finalizacion_real", "sobreplazo",
            "costo_de_obra_en_soles_segun_et_en_soles", "modalidad_de_ejecucion_de_la_obra", "tipo_de_obra_clasificador_nivel_1"]
    keep += [c for c in d.columns if c.startswith(("y_", "known_"))]
    ds = pd.concat([d[keep], f], axis=1)
    dst = out / "exante_dataset.parquet"
    ds.to_parquet(dst, index=False)
    lab = ds["y_30"].notna()
    log.info("ex-ante: %s obras, %s con etiqueta (prevalencia %.3f); Arequipa %s con etiqueta",
             len(ds), int(lab.sum()), ds.loc[lab, "y_30"].mean(), int((lab & (ds["departamento"] == "AREQUIPA")).sum()))
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build()
