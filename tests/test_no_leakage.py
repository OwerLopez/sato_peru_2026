"""Pruebas de NO FUGA TEMPORAL sobre los datos reales construidos por el pipeline.

Se omiten si los artefactos de datos no existen (p.ej. en CI sin datos).
Verifican, por muestreo y de forma independiente al codigo de features:
  1. Las etiquetas solo son positivas si el onset cae en (T, T+H].
  2. Los conteos de asientos en T se reproducen usando SOLO asientos con fecha <= T.
  3. Ninguna feature de "dias desde" es negativa (no hay registros posteriores a T).
  4. Las features SIAF de T solo usan meses anteriores al mes de T.
  5. Las filas de test del experimento son posteriores a todas las de entrenamiento + H.
"""

import numpy as np
import pandas as pd
import pytest

from sato.config import CURATED, FEATURES, STAGING

pytestmark = pytest.mark.skipif(not (FEATURES / "features_structured.parquet").exists(), reason="requiere datos del pipeline")


@pytest.fixture(scope="module")
def panel():
    return pd.read_parquet(FEATURES / "panel.parquet")


@pytest.fixture(scope="module")
def feats():
    return pd.read_parquet(FEATURES / "features_structured.parquet")


@pytest.mark.parametrize("H", [30, 60, 90])
def test_etiqueta_en_ventana(panel, H):
    p = panel[panel[f"y_atraso_{H}"] == 1]
    assert ((p["onset_atraso"] > p["T"]) & (p["onset_atraso"] <= p["T"] + pd.Timedelta(days=H))).all()
    n = panel[(panel[f"y_atraso_{H}"] == 0) & panel["onset_atraso"].notna() & panel["eligible_atraso"]]
    assert not ((n["onset_atraso"] > n["T"]) & (n["onset_atraso"] <= n["T"] + pd.Timedelta(days=H))).any()
    fut = panel[panel[f"y_atraso_{H}"] == -1]
    assert (fut["T"] + pd.Timedelta(days=H) > fut["data_end"]).all()


def test_elegibles_no_han_tenido_el_evento(panel):
    e = panel[panel["eligible_atraso"]]
    assert not (e["onset_atraso"] <= e["T"]).any()


def test_conteos_reproducibles_solo_con_pasado(feats):
    rng = np.random.default_rng(3)
    sample = feats.sample(300, random_state=3)[["cuaderno_id", "T", "asi_n_total", "asi_n_90d", "asi_cum_ampliacion_plazo"]]
    asi = pd.read_parquet(CURATED / "asiento.parquet", columns=["cuaderno_id", "fecha", "tipo_std"],
                          filters=[("cuaderno_id", "in", list(sample["cuaderno_id"].unique()))])
    asi["fecha"] = pd.to_datetime(asi["fecha"])
    for r in sample.itertuples():
        a = asi[(asi["cuaderno_id"] == r.cuaderno_id) & (asi["fecha"] <= r.T)]
        assert len(a) == r.asi_n_total
        assert (a["fecha"] > r.T - pd.Timedelta(days=90)).sum() == r.asi_n_90d
        assert (a["tipo_std"] == "AMPLIACION_PLAZO").sum() == r.asi_cum_ampliacion_plazo
    assert rng is not None


@pytest.mark.parametrize("col", ["asi_dias_desde_ultimo", "asi_dias_desde_primero", "asi_dias_desde_inicio_plazo", "siaf_meses_desde_ultimo_dev"])
def test_sin_registros_posteriores(feats, col):
    v = feats[col].dropna()
    assert (v >= 0).all(), f"{col} tiene valores negativos: registros posteriores a T"


def test_siaf_rezago_un_mes(feats, panel):
    """Recalcula el devengado acumulado de una muestra usando solo meses < mes(T) (configuracion evaluada: SIAF 2020+)."""
    cua = pd.read_parquet(CURATED / "cuaderno.parquet", columns=["cuaderno_id", "cui"])
    s = feats[feats["siaf_dev_acum"].notna()].sample(80, random_state=5)[["cuaderno_id", "T", "siaf_dev_acum"]].merge(cua, on="cuaderno_id")
    siaf = pd.concat([pd.read_parquet(f, columns=["cui", "anio", "mes", "monto_devengado"]) for f in sorted((STAGING / "siaf").glob("*.parquet"))])
    siaf = siaf[siaf["mes"].between(1, 12) & (siaf["anio"] >= 2020) & siaf["cui"].isin(s["cui"])]
    siaf["mes_ini"] = pd.to_datetime(dict(year=siaf["anio"], month=siaf["mes"], day=1))
    for r in s.itertuples():
        m = siaf[(siaf["cui"] == r.cui) & (siaf["mes_ini"] < r.T.replace(day=1))]["monto_devengado"].sum()
        assert m == pytest.approx(r.siaf_dev_acum, rel=1e-6, abs=0.01)


def test_particion_temporal_con_purga():
    from sato.models.experiment import Config, load_dataset, splits

    for H in (30, 60, 90):
        df, _ = load_dataset(Config(H=H))
        train, valid, trainval, test = splits(df, H)
        assert df.loc[trainval, "T"].max() + pd.Timedelta(days=H) <= df.loc[test, "T"].min()
        assert df.loc[train, "T"].max() + pd.Timedelta(days=H) <= df.loc[valid, "T"].min()
        assert (df.loc[test, "T"] + pd.Timedelta(days=H) <= df["data_end"].iloc[0]).all()
