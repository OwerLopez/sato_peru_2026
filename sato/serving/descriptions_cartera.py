"""Descripciones en espanol de las variables de los modelos de cartera (inicio y seguimiento).

Describen el VALOR REAL de la variable; el sentido de la contribucion lo aporta TreeSHAP.
"""

from __future__ import annotations

import math

GRUPOS = [("hist_entidad", "Historial de la entidad"), ("hist_contratista", "Historial del contratista"), ("hist_provincia", "Historial de la provincia"),
          ("sg_", "Ejecucion financiera (SIAF)"), ("ea_txt", "Nombre de la obra (NLP)"), ("ea_", "Caracteristicas de la obra al inicio")]

TXT = {
    "ea_log_plazo": ("Plazo de ejecucion original", "dias_log"), "ea_log_costo_et": ("Costo segun expediente tecnico", "soles_log"),
    "ea_log_monto_contrato": ("Monto del contrato", "soles_log"), "ea_ratio_contrato_et": ("Monto de contrato / costo del expediente", "pct"),
    "ea_log_monto_viable": ("Monto viable de la inversion", "soles_log"), "ea_costo_por_dia": ("Costo por dia de plazo", "soles_log"),
    "ea_con_supervision": ("Supervision contratada registrada", "bool"), "ea_terreno_entregado": ("Terreno entregado al inicio (%)", "num"),
    "ea_entrega_parcial": ("Entrega parcial del terreno", "bool"), "ea_dias_expediente_inicio": ("Dias entre aprobacion del expediente e inicio", "num"),
    "ea_dias_viabilidad_inicio": ("Dias entre viabilidad e inicio", "num"), "ea_saldo_de_obra": ("Es saldo de una obra anterior", "bool"),
    "ea_reconstruccion": ("Marca Reconstruccion con Cambios", "bool"), "ea_reactivacion": ("Marca de reactivacion economica", "bool"),
    "ea_mes_inicio": ("Mes de inicio", "num"), "ea_anio_inicio": ("Anio de inicio", "num"), "ea_tiene_cui": ("Tiene codigo unico de inversion", "bool"),
    "ea_txt_nombre": ("Riesgo inferido del nombre de la obra (modelo TF-IDF)", "prob"),
    "ea_modalidad": ("Modalidad de ejecucion", "cat"), "ea_naturaleza": ("Naturaleza de la obra", "cat"), "ea_tipo1": ("Tipo de obra", "cat"),
    "ea_tipo2": ("Subtipo de obra", "cat"), "ea_tipo3": ("Detalle del tipo de obra", "cat"), "ea_nivel_gobierno": ("Nivel de gobierno", "cat"),
    "ea_sector_entidad": ("Sector de la entidad", "cat"), "ea_departamento": ("Departamento", "cat"), "ea_tipo_inversion": ("Tipo de inversion", "cat"),
    "ea_marco": ("Marco de inversion", "cat"), "ea_funcion": ("Funcion presupuestal", "cat"),
    "sg_frac_plazo": ("Fraccion del plazo original transcurrida", "pct"), "sg_dias_al_fin_prog": ("Dias al fin programado original", "num"),
    "sg_dev_acum_costo": ("Devengado acumulado de la inversion / costo de obra", "pct"), "sg_dev_desde_inicio_costo": ("Devengado desde el inicio / costo de obra", "pct"),
    "sg_dev_3m_costo": ("Devengado de los ultimos 3 meses / costo de obra", "pct"), "sg_meses_sin_dev": ("Meses sin devengado", "num"),
    "sg_meses_con_dev": ("Meses con devengado desde el inicio", "num"), "sg_pia_anio_costo": ("PIA del anio / costo de obra", "pct"),
    "sg_brecha_ritmo": ("Brecha de ritmo: devengado/costo menos plazo transcurrido", "pct"), "sg_vencido": ("Plazo original ya vencido", "bool"),
}
HIST = {"obras_previas": ("obras previas", "num"), "resultados_previos": ("obras previas con resultado conocido", "num"),
        "tasa_retraso": ("tasa historica de retraso significativo", "pct"), "sobreplazo_mediano": ("sobre-plazo mediano historico", "pct"),
        "en_curso": ("obras en curso al inicio", "num")}
ACTOR = {"hist_entidad": "Entidad", "hist_contratista": "Contratista", "hist_provincia": "Provincia"}


def group_c(f: str) -> str:
    from sato.serving.lenguaje import GRUPOS_CLAROS

    for p, g in GRUPOS:
        if f.startswith(p):
            return GRUPOS_CLAROS.get(g, g)
    return "Otros"


def _fmt(v, kind):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "sin dato"
    if kind == "cat":
        return str(v)
    if kind == "bool":
        return "si" if float(v) >= 0.5 else "no"
    if kind == "pct":
        return f"{100 * float(v):.0f}%"
    if kind == "prob":
        return f"{float(v):.2f}"
    if kind == "soles_log":
        return f"S/ {math.expm1(float(v)):,.0f}"
    if kind == "dias_log":
        return f"{math.exp(float(v)):,.0f} dias"
    return f"{float(v):,.0f}" if abs(float(v)) >= 10 else f"{float(v):.2f}".rstrip("0").rstrip(".")


def describe_c(f: str, v) -> str:
    """Frase en lenguaje claro (ver sato.serving.lenguaje); `v` es numerico o, para variables categoricas, texto."""
    from sato.serving.lenguaje import factor_cartera

    if isinstance(v, str):
        return factor_cartera(f, None, v)
    return factor_cartera(f, v)


def describe_c_tecnico(f: str, v) -> str:
    if f in TXT:
        name, kind = TXT[f]
        return f"{name}: {_fmt(v, kind)}"
    for pre, actor in ACTOR.items():
        if f.startswith(pre + "_"):
            name, kind = HIST.get(f[len(pre) + 1:], (f[len(pre) + 1:], "num"))
            return f"{actor}: {name}: {_fmt(v, kind)}"
    return f"{f}: {_fmt(v, 'num') if isinstance(v, (int, float)) else v}"
