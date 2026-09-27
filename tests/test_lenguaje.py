"""Pruebas unitarias de la traduccion de factores a lenguaje claro (sin base de datos)."""

import math

from sato.serving.lenguaje import categoria, factor_cartera, factor_cuaderno


def test_plazo_vencido_y_por_vencer():
    assert factor_cuaderno("ib_dias_para_fin_programado", -45) == "El plazo original venció hace 45 días"
    assert factor_cuaderno("ib_dias_para_fin_programado", 30) == "Faltan 30 días para el fin del plazo original"


def test_conteos_con_singular_plural_y_cero():
    assert factor_cuaderno("asi_90d_ampliacion_plazo", 1) == "1 asiento de ampliación de plazo en los últimos 90 días"
    assert factor_cuaderno("asi_90d_ampliacion_plazo", 3) == "3 asientos de ampliación de plazo en los últimos 90 días"
    assert factor_cuaderno("asi_90d_ampliacion_plazo", 0) == "Ningún asiento de ampliación de plazo en los últimos 90 días"


def test_valores_fuera_de_rango_se_explican():
    assert factor_cuaderno("asi_consultas_pendientes", -1) == "No hay consultas pendientes de respuesta"
    assert "después del inicio" in factor_cartera("ea_dias_expediente_inicio", -297)
    assert factor_cartera("ea_anio_inicio", 2016.0) == "Año de inicio: 2016"
    assert factor_cuaderno("siaf_dev_3m", -0.04).endswith("S/ 0")


def test_categorias_y_codigos():
    assert factor_cuaderno("est_dep_code", None, "04") == "Departamento: Arequipa"
    assert factor_cuaderno("est_dep_code", None, "00") == "Departamento: no identificado"
    assert factor_cuaderno("est_tipo_entidad", None, "GOB_REGIONAL") == "Entidad contratante: gobierno regional"
    assert categoria("Departamento de la obra (código INEI): 04") == "04"
    assert categoria("Monto: sin dato") is None


def test_sin_dato_nunca_falla():
    for f in ("ib_log_monto_contrato", "asi_dias_desde_inicio_plazo", "txt_stack_tfidf", "siaf_dev_acum_sobre_viable", "tmp_mes", "est_marco"):
        assert "sin dato" in factor_cuaderno(f, None) or factor_cuaderno(f, None)
        assert factor_cuaderno(f, float("nan"))
    for f in ("hist_entidad_tasa_retraso", "ea_log_costo_et", "sg_brecha_ritmo", "ea_modalidad"):
        assert factor_cartera(f, None)


def test_montos_en_escala_logaritmica():
    assert factor_cuaderno("ib_log_monto_contrato", math.log1p(1_468_863)) == "Monto del contrato: S/ 1,468,863"
    assert factor_cartera("ea_log_monto_contrato", 0.0) == "Monto del contrato: sin monto registrado"


def test_sin_jerga_tecnica():
    textos = [factor_cuaderno("txt_stack_tfidf", 0.44), factor_cuaderno("txt_stack_emb", 0.2), factor_cartera("ea_txt_nombre", 0.7)]
    assert all("TF-IDF" not in t and "embedding" not in t.lower() for t in textos)


def test_sin_dato_nunca_muestra_codigos_internos():
    import re

    from sato.serving.descriptions import describe_tecnico
    from sato.serving.descriptions_cartera import TXT

    codigo = re.compile(r"(txt|asi|ie|siaf|mefseg|actor|ib|est|tmp|ea|sg|hist)_[a-z0-9_]+")
    cuaderno = ["txt_len_media_60d", "txt_n_asientos_60d", "asi_n_30d", "ie_ratio_ultimo", "mefseg_problemas_180d", "actor_entidad_obras_previas",
                "est_plazo_vigencia_dias", "tmp_vigencia_ley32069", "siaf_pia_anio"]
    for f in cuaderno:
        t = factor_cuaderno(f, None)
        assert not codigo.search(t), t
        assert describe_tecnico(f, None)
    for f in list(TXT) + ["hist_entidad_en_curso"]:
        t = factor_cartera(f, None)
        assert not codigo.search(t), t
