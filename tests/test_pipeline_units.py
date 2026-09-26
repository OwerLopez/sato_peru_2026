"""Pruebas unitarias de componentes del pipeline (no requieren datos descargados)."""

import numpy as np
import pandas as pd
import pytest

from sato.features.extraction import extract
from sato.integration.linkage import RX_CUI, ascii_upper, norm_name
from sato.models.evaluate import cluster_bootstrap, lead_times, point_metrics, threshold_for_fbeta
from sato.serving.descriptions import describe, group_of
from sato.staging.infobras import parse_number
from sato.staging.oece import SPECS, _split_quoted, _split_record


class TestOeceParsing:
    header = ["FECHA_CORTE", "ID_CUADERNO", "TIPO_USUARIO_REGISTRANTE", "TIPO_DOCUMENTO_IDENTIFICACION_USUARIO_REGISTRANTE",
              "NRO_ASIENTO_REGISTRADO", "FECHA_REGISTRO_ASIENTO", "HORA_REGISTRO_ASIENTO", "TIPO_ASIENTO_REGISTRADO",
              "TITULO_ASIENTO_REGISTRADO", "DESCRIPCION_DEL_ASIENTO", "ASIENTO_ENLAZADO", "ESTADO_ASIENTO",
              "LATITUD_REFERENCIAL_ASIENTO", "LONGITUD_REFERENCIAL_ASIENTO"]
    uid = "99988ce6-de8c-4772-a05d-861c9ed5c4e6"

    def test_registro_exacto(self):
        parts = ["20260901", self.uid, "SOEC_RESI", "DNI", "5", "20260824", "17:53", "Otras ocurrencias", "T", "texto", "", "DEFINITIVO", "", ""]
        out, st = _split_record(parts, self.header, SPECS["asientos"])
        assert st == "ok" and out == parts

    def test_repara_separador_en_texto_libre(self):
        parts = ["20260901", self.uid, "SOEC_RESI", "DNI", "5", "20260824", "17:53", "Otras ocurrencias", "T", "a", "b", "", "DEFINITIVO", "", ""]
        out, st = _split_record(parts, self.header, SPECS["asientos"])
        assert st == "repaired"
        assert out[9] == "a|b" and out[11] == "DEFINITIVO" and len(out) == len(self.header)

    def test_rechaza_si_anclas_no_validan(self):
        parts = ["20260901", "no-es-uuid", "SOEC_RESI", "DNI", "5", "20260824", "17:53", "X", "T", "a", "b", "", "DEFINITIVO", "", ""]
        _, st = _split_record(parts, self.header, SPECS["asientos"])
        assert st == "rejected"

    def test_dialecto_con_comillas(self):
        assert _split_quoted('"a"|"b ""c"" d"|5') == ["a", 'b "c" d', "5"]


def test_numeros_infobras_con_espacio_decimal():
    s = parse_number(pd.Series(["1205287 56", "37103", "0", "", None, "94 87"]))
    assert s.iloc[0] == pytest.approx(1205287.56) and s.iloc[1] == 37103 and s.iloc[5] == pytest.approx(94.87)
    assert pd.isna(s.iloc[3])


class TestEnlaceCUI:
    @pytest.mark.parametrize("texto,cui", [
        ('SALDO DE OBRA "AGUA POTABLE" Código CUI N° 2196734 (SNIP N° 286898).', "2196734"),
        ("MEJORAMIENTO ... CON CODIGO UNICO DE INVERSION N° 2485123", "2485123"),
        ("OBRA X - C.U.I. 2301234", "2301234"),
    ])
    def test_regex_cui(self, texto, cui):
        assert RX_CUI.findall(ascii_upper(texto))[0] == cui

    def test_normalizacion_elimina_prefijo_contractual(self):
        n = norm_name('CONTRATACIÓN DE LA EJECUCIÓN DE LA OBRA: "MEJORAMIENTO DEL SERVICIO DE AGUA" CUI N° 2196734')
        assert n.startswith("MEJORAMIENTO DEL SERVICIO DE AGUA") and "2196734" not in n


class TestExtraccion:
    def test_ejecutado_y_programado(self):
        e, p, est, _ = extract("La valorización alcanza un avance ejecutado acumulado del 40.33% y un programado acumulado del 26.03%, la obra se encuentra adelantada en 7.07%")
        assert e == pytest.approx(40.33) and p == pytest.approx(26.03) and est == "adelantada"

    def test_tolera_fecha_intermedia(self):
        e, p, _, _ = extract("avance acumulado ejecutado al 30.06.2025 : 27.39% del monto contractual. avance acumulado programado al 30.06.2025 : 37.89%")
        assert e == pytest.approx(27.39) and p == pytest.approx(37.89)

    def test_no_confunde_regla_del_80(self):
        e, p, _, _ = extract("la valorización acumulada ejecutada es menor al 80% del monto acumulado programado")
        assert e is None and p is None

    def test_atrasada(self):
        _, _, est, br = extract("la obra se encuentra atrasada en 12.5% respecto al calendario")
        assert est == "atrasada" and br == pytest.approx(-12.5)


class TestEvaluacion:
    def test_umbral_f2_prioriza_recall(self):
        rng = np.random.default_rng(0)
        y = (rng.random(2000) < 0.1).astype(int)
        s = np.clip(y * 0.3 + rng.random(2000) * 0.7, 0, 1)
        thr = threshold_for_fbeta(y, s, beta=2)
        m = point_metrics(y, s, thr)
        assert m["recall"] >= m["precision"]

    def test_bootstrap_detecta_score_mejor(self):
        rng = np.random.default_rng(1)
        n = 3000
        df = pd.DataFrame({"cuaderno_id": rng.integers(0, 300, n), "y": (rng.random(n) < 0.15).astype(int)})
        df["malo"] = rng.random(n)
        df["bueno"] = df["y"] * 0.5 + rng.random(n) * 0.5
        b = cluster_bootstrap(df, ["malo", "bueno"], n_boot=200)
        d = b[(b.score == "bueno - malo") & (b.metrica == "roc")].iloc[0]
        assert d.ic_inf > 0

    def test_anticipacion(self):
        df = pd.DataFrame({"cuaderno_id": ["a"] * 3, "T": pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"]),
                           "s": [0.1, 0.8, 0.9], "onset": pd.to_datetime(["2025-04-10"] * 3)})
        lt = lead_times(df, "s", 0.5, "onset")
        assert lt.iloc[0]["anticipacion_dias"] == (pd.Timestamp("2025-04-10") - pd.Timestamp("2025-02-28")).days


def test_descripciones_legibles():
    assert "suspensiones del plazo" in describe("asi_90d_suspension_plazo", 2.0)
    assert "lluvias" in describe("txt_lx_clima", 0.25) and "25%" in describe("txt_lx_clima", 0.25)
    assert group_of("siaf_dev_3m") == "Ejecucion financiera (SIAF)"
