"""Pruebas unitarias (caja blanca) de la operacion autocontrolada: compuerta de carga, validacion de entradas,
planificacion y reintentos del worker, deteccion de anomalias y deriva. No requieren base de datos."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from sato.cron_runner import debe_sincronizar, reintentar
from sato.models.monitor import anomalia_tasa, psi
from sato.services.schedule import dia_sync, proxima_sync
from sato.serving.calidad import CHEQUEOS, estado_de
from sato.serving.load_db import ENTRADAS, TABLAS_CLAVE, CargaRechazada, compuerta, validar_entradas

# ---------------------------------------------------------------- compuerta de integridad


def _conteos(n: int) -> dict[str, int]:
    return {t: n for t in TABLAS_CLAVE}


def test_compuerta_acepta_crecimiento_y_caida_dentro_del_limite():
    assert compuerta(_conteos(1000), _conteos(1200), 0.2) == []
    assert compuerta(_conteos(1000), _conteos(800), 0.2) == []  # exactamente en el limite


def test_compuerta_rechaza_caida_mayor_al_limite():
    nuevos = {**_conteos(1000), "asiento": 799}
    fallas = compuerta(_conteos(1000), nuevos, 0.2)
    assert len(fallas) == 1 and fallas[0].startswith("asiento") and "20%" in fallas[0]


def test_compuerta_rechaza_tabla_vacia_salvo_cartera_opcional():
    nuevos = {**_conteos(10), "obra": 0, "cartera_obra": 0, "cartera_riesgo": 0}
    fallas = compuerta({}, nuevos, 0.2)  # primera carga: sin conteos previos
    assert fallas == ["obra: la carga dejaria la tabla vacia"]


def test_compuerta_primera_carga_sin_previos():
    assert compuerta({}, _conteos(5), 0.2) == []


# ---------------------------------------------------------------- validacion de entradas


def _entradas_validas() -> dict[str, pd.DataFrame]:
    return {k: pd.DataFrame({c: [f"{k}-{i}" for i in range(3)] for c in cols}) for k, (cols, _) in ENTRADAS.items()}


def test_validar_entradas_completas():
    assert validar_entradas(_entradas_validas()) == []


def test_validar_entradas_detecta_ausencias_columnas_nulos_y_duplicados():
    f = _entradas_validas()
    f["seace_contratos"] = None
    f["mef_inversiones"] = f["mef_inversiones"].drop(columns=["monto_viable"])
    f["cuaderno"].loc[0, "cuaderno_id"] = None
    f["cartera_obras"].loc[2, "codigo_infobras"] = f["cartera_obras"].loc[1, "codigo_infobras"]
    f["predicciones"] = f["predicciones"].iloc[0:0]
    fallas = validar_entradas(f)
    assert "seace_contratos: archivo ausente" in fallas
    assert any(x.startswith("mef_inversiones: faltan columnas") and "monto_viable" in x for x in fallas)
    assert "cuaderno: 1 filas sin cuaderno_id" in fallas
    assert "cartera_obras: 1 valores repetidos de codigo_infobras" in fallas
    assert "predicciones: archivo sin filas" in fallas


def test_cartera_es_opcional():
    f = _entradas_validas()
    f["cartera_obras"] = None
    assert validar_entradas(f) == []


# ---------------------------------------------------------------- auditoria de calidad


def test_estado_de_chequeo():
    assert estado_de("INFO", 10) == "INFO"
    assert estado_de("AVISO", 0) == "OK" and estado_de("AVISO", 3) == "AVISO"
    assert estado_de("CRITICO", 0) == "OK" and estado_de("CRITICO", 1) == "CRITICO"


def test_catalogo_de_chequeos_bien_formado():
    claves = [c[1] for c in CHEQUEOS]
    assert len(claves) == len(set(claves)), "claves repetidas"
    assert all(c[4] in ("INFO", "AVISO", "CRITICO") for c in CHEQUEOS)
    criticos = {c[1] for c in CHEQUEOS if c[4] == "CRITICO"}
    assert {"vigentes_sin_explicacion", "cartera_activa_sin_explicacion", "modelo_activo", "probabilidad_fuera_de_rango"} <= criticos


# ---------------------------------------------------------------- planificacion del worker

AHORA = dt.datetime(2026, 10, 5, 12, tzinfo=dt.UTC)


def test_no_sincroniza_antes_del_dia(monkeypatch):
    monkeypatch.setenv("SATO_SYNC_DIA", "10")
    assert debe_sincronizar(dt.date(2026, 10, 5), AHORA, None, 0, None, 3) == (False, "antes del dia de sincronizacion")


def test_no_repite_una_sincronizacion_exitosa_del_mes(monkeypatch):
    monkeypatch.setenv("SATO_SYNC_DIA", "2")
    ok, motivo = debe_sincronizar(dt.date(2026, 10, 5), AHORA, dt.date(2026, 10, 2), 0, None, 3)
    assert not ok and motivo == "ya sincronizado este mes"


def test_espera_exponencial_tras_fallos(monkeypatch):
    monkeypatch.setenv("SATO_SYNC_DIA", "2")
    hoy = dt.date(2026, 10, 5)
    ok, motivo = debe_sincronizar(hoy, AHORA, dt.date(2026, 9, 2), 2, AHORA - dt.timedelta(hours=3), 3)
    assert not ok and "esperando" in motivo  # 2 fallos -> 4 horas
    assert debe_sincronizar(hoy, AHORA, dt.date(2026, 9, 2), 2, AHORA - dt.timedelta(hours=5), 3)[0]


def test_tope_de_intentos_mensuales(monkeypatch):
    monkeypatch.setenv("SATO_SYNC_DIA", "2")
    ok, motivo = debe_sincronizar(dt.date(2026, 10, 20), AHORA, dt.date(2026, 9, 2), 3, AHORA - dt.timedelta(days=5), 3)
    assert not ok and "intentos" in motivo


def test_reintentos_con_espera_exponencial():
    esperas: list[float] = []
    fallos = iter([RuntimeError("red"), ConnectionError("timeout")])

    def paso():
        e = next(fallos, None)
        if e:
            raise e

    assert reintentar(paso, 2, 60, dormir=esperas.append) == 3
    assert esperas == [60, 120]


def test_reintentos_agotados_relanzan_el_error():
    esperas: list[float] = []

    def paso():
        raise RuntimeError("fuente caida")

    with pytest.raises(RuntimeError, match="fuente caida"):
        reintentar(paso, 2, 1, dormir=esperas.append)
    assert esperas == [1, 2]


def test_rechazo_de_compuerta_no_se_reintenta():
    esperas: list[float] = []

    def paso():
        raise CargaRechazada("caida de filas")

    with pytest.raises(CargaRechazada):
        reintentar(paso, 3, 1, dormir=esperas.append)
    assert esperas == []


# ---------------------------------------------------------------- calendario


def test_proxima_sincronizacion_cruza_el_anio(monkeypatch):
    monkeypatch.setenv("SATO_SYNC_DIA", "2")
    assert proxima_sync(dt.date(2026, 12, 15)) == dt.date(2027, 1, 2)
    assert proxima_sync(dt.date(2026, 12, 1)) == dt.date(2026, 12, 2)
    assert proxima_sync(dt.date(2026, 12, 2)) == dt.date(2027, 1, 2)


@pytest.mark.parametrize("valor,esperado", [("31", 28), ("0", 1), ("abc", 2), ("15", 15)])
def test_dia_de_sincronizacion_valido_en_todos_los_meses(monkeypatch, valor, esperado):
    monkeypatch.setenv("SATO_SYNC_DIA", valor)
    assert dia_sync() == esperado
    assert proxima_sync(dt.date(2027, 2, 10)).month in (2, 3)  # nunca falla en febrero


# ---------------------------------------------------------------- monitoreo del modelo


def test_psi_distribuciones_iguales_y_desplazadas():
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(0, 1, 5000))
    assert psi(ref, pd.Series(rng.normal(0, 1, 2000))) < 0.05
    assert psi(ref, pd.Series(rng.normal(1.5, 1, 2000))) > 0.25
    assert np.isnan(psi(ref.head(10), ref))  # muestra insuficiente


def _predicciones(tasas_hist: list[float], tasa_vig: float, n: int = 200) -> pd.DataFrame:
    filas = []
    cortes = pd.date_range("2024-01-31", periods=len(tasas_hist) + 1, freq="ME")
    for T, tasa, tipo in zip(cortes, [*tasas_hist, tasa_vig], ["backtest"] * len(tasas_hist) + ["vigente"], strict=True):
        k = round(tasa * n)
        filas += [{"T": T, "tipo": tipo, "nivel": "ALTO" if i < k else "BAJO"} for i in range(n)]
    return pd.DataFrame(filas)


def test_anomalia_de_tasa_normal_y_atipica():
    hist = [0.10, 0.11, 0.09, 0.10, 0.12, 0.10, 0.095, 0.105]
    normal = anomalia_tasa(_predicciones(hist, 0.11))
    assert normal["evaluable"] and not normal["anomala"]
    atipica = anomalia_tasa(_predicciones(hist, 0.40))
    assert atipica["anomala"] and atipica["z"] > 3.5


def test_anomalia_requiere_historial_minimo():
    assert anomalia_tasa(_predicciones([0.1, 0.1], 0.5))["evaluable"] is False
