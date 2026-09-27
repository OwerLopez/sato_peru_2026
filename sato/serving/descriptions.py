"""Descripciones en espanol de cada feature, para explicaciones legibles.

Las frases describen el VALOR observado de la variable (dato real) y el
sentido de su contribucion lo aporta el valor SHAP; no se genera narrativa
libre ni se inventan causas.
"""

from __future__ import annotations

import math
import re

TIPO_ES = {
    "ampliacion_plazo": "ampliaciones de plazo", "suspension_plazo": "suspensiones del plazo", "adicionales": "adicionales de obra",
    "mayores_metrados": "mayores metrados", "consultas": "consultas", "respuestas_consultas": "respuestas a consultas",
    "penalidades": "aplicacion de penalidades", "ordenes": "ordenes", "riesgos": "administracion de riesgos",
    "constatacion_fisica": "constataciones fisicas", "programa_cpm": "programas de ejecucion (CPM)",
    "calendario_valorizado": "calendarios de avance valorizado", "valorizaciones": "valorizaciones y metrados",
    "otras_modificaciones": "otras modificaciones contractuales", "reducciones": "reducciones de obra",
    "personal_clave": "participacion de personal clave", "expediente_tecnico": "expediente tecnico",
    "adelantos": "adelantos", "otras_ocurrencias": "otras ocurrencias", "inicio_plazo": "inicio del plazo",
}
LEX_ES = {
    "atraso": "atraso/retraso/demora", "proxy_80": "la regla del 80% o calendario acelerado", "paralizacion": "paralizacion o frentes sin trabajo",
    "clima": "lluvias u otros eventos climaticos", "financiero": "pagos, adelantos o presupuesto", "materiales": "falta o desabastecimiento de materiales",
    "equipo": "maquinaria o equipos", "personal": "falta o cambio de personal", "expediente": "deficiencias del expediente tecnico",
    "terreno": "interferencias, terreno o conflictos con la poblacion", "adicionales": "adicionales, deductivos o mayores metrados",
    "controversia": "controversias o arbitraje", "incumplimiento": "penalidades, incumplimientos o cartas notariales",
    "calidad": "observaciones o no conformidades de calidad", "suspension": "suspension o reinicio", "progreso": "avance normal o adelantado",
}

GROUPS = [
    ("asi_", "Registros del cuaderno de obra"), ("txt_", "Contenido de los asientos (NLP)"), ("ie_", "Avance reportado en asientos (NLP)"),
    ("siaf_", "Ejecucion financiera (SIAF)"), ("mefseg_", "Seguimiento Invierte.pe (F12B)"), ("actor_", "Historial de actores"),
    ("ib_", "Contrato (INFOBRAS, al inicio)"), ("est_", "Caracteristicas de la obra"), ("tmp_", "Calendario"),
]


def group_of(f: str) -> str:
    from sato.serving.lenguaje import GRUPOS_CLAROS

    for p, g in GROUPS:
        if f.startswith(p):
            return GRUPOS_CLAROS.get(g, g)
    return "Otros"


def _n(v):
    return "sin dato" if v is None or (isinstance(v, float) and math.isnan(v)) else (f"{v:,.0f}" if abs(v) >= 10 else f"{v:.2f}".rstrip("0").rstrip("."))


def _pct(v):
    return "sin dato" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{100 * v:.0f}%"


def describe(f: str, v) -> str:
    """Frase en lenguaje claro (ver sato.serving.lenguaje); `v` es numerico o, para variables categoricas, texto."""
    from sato.serving.lenguaje import factor_cuaderno

    if isinstance(v, str):
        return factor_cuaderno(f, None, v)
    return factor_cuaderno(f, v)


def describe_tecnico(f: str, v) -> str:
    m = re.match(r"asi_(cum|90d)_(.+)", f)
    if m:
        per = "acumulados" if m.group(1) == "cum" else "en los ultimos 90 dias"
        return f"Asientos de {TIPO_ES.get(m.group(2), m.group(2))} {per}: {_n(v)}"
    m = re.match(r"txt_lx_(.+)", f)
    if m:
        return f"Asientos de los ultimos 60 dias que mencionan {LEX_ES.get(m.group(1), m.group(1))}: {_pct(v)}"
    if f.startswith("txt_lsa_") or f.startswith("txt_emb_"):
        return f"Componente semantico del texto reciente ({f.split('_')[1].upper()} {f.split('_')[-1]}): {_n(v)}"
    fixed = {
        "asi_n_total": "Total de asientos registrados", "asi_n_30d": "Asientos en los ultimos 30 dias", "asi_n_90d": "Asientos en los ultimos 90 dias",
        "asi_dias_activos_30d": "Dias con asientos en los ultimos 30 dias", "asi_dias_desde_ultimo": "Dias desde el ultimo asiento",
        "asi_dias_desde_primero": "Dias desde la apertura del cuaderno", "asi_dias_desde_inicio_plazo": "Dias desde el inicio del plazo de ejecucion",
        "asi_frac_supervision_90d": "Proporcion de asientos del supervisor/inspector (90 dias)",
        "asi_consultas_pendientes": "Consultas sin respuesta registrada", "asi_ritmo_30d_vs_90d": "Ritmo de asientos del ultimo mes vs. trimestre",
        "txt_n_asientos_60d": "Asientos con texto en los ultimos 60 dias", "txt_len_media_60d": "Longitud media de los asientos (caracteres)",
        "txt_stack_tfidf": "Riesgo inferido del vocabulario de los asientos recientes (modelo TF-IDF)",
        "txt_stack_emb": "Riesgo inferido del significado de los asientos recientes (modelo de embeddings)",
        "ie_ratio_ultimo": "Ultimo avance reportado ejecutado/programado", "ie_ratio_min_90d": "Minimo ejecutado/programado reportado (90 dias)",
        "ie_brecha_ultima": "Ultima brecha ejecutado - programado (puntos porcentuales)", "ie_n_atrasada_60d": "Asientos que declaran la obra atrasada (60 dias)",
        "ie_n_adelantada_60d": "Asientos que declaran la obra adelantada (60 dias)", "ie_dias_desde_reporte": "Dias desde el ultimo avance reportado",
        "siaf_dev_acum": "Devengado acumulado de la inversion (S/)", "siaf_dev_3m": "Devengado de los ultimos 3 meses (S/)",
        "siaf_dev_ytd": "Devengado del anio (S/)", "siaf_meses_desde_ultimo_dev": "Meses desde el ultimo devengado",
        "siaf_pia_anio": "PIA del anio (S/)", "siaf_dev_acum_sobre_viable": "Devengado acumulado / monto viable",
        "siaf_dev_ytd_sobre_pia": "Devengado del anio / PIA",
        "mefseg_registros_180d": "Registros de seguimiento F12B (180 dias)", "mefseg_problemas_180d": "Problemas registrados en F12B (180 dias)",
        "mefseg_problema_atraso_180d": "Problemas de atraso/paralizacion en F12B (180 dias)",
        "actor_contratista_obras_previas": "Obras previas del contratista con cuaderno digital", "actor_contratista_atrasos_previos": "Obras previas del contratista con atraso normativo",
        "actor_entidad_obras_previas": "Obras previas de la entidad con cuaderno digital", "actor_entidad_atrasos_previos": "Obras previas de la entidad con atraso normativo",
        "ib_plazo_original_dias": "Plazo de ejecucion original (dias)", "ib_log_monto_contrato": "Monto del contrato (escala log)",
        "ib_frac_plazo_transcurrido": "Fraccion del plazo original transcurrida", "ib_dias_para_fin_programado": "Dias para el fin programado original",
        "est_es_consorcio": "Contratista es consorcio", "est_n_miembros_consorcio": "Miembros del consorcio", "est_arequipa": "Obra en Arequipa",
        "est_tiene_cui": "Obra enlazada a una inversion (CUI)", "est_log_monto_viable": "Monto viable de la inversion (escala log)",
        "est_log_monto_contratado": "Monto contratado SEACE (escala log)", "est_plazo_vigencia_dias": "Vigencia original del contrato SEACE (dias)",
        "est_tiene_seace": "Contrato disponible en SEACE", "est_regimen_ley32069": "Cuaderno bajo el regimen de la Ley 32069",
        "tmp_mes": "Mes del corte", "tmp_vigencia_ley32069": "Corte posterior a la vigencia de la Ley 32069",
    }
    if f in fixed:
        if f in ("ib_frac_plazo_transcurrido", "siaf_dev_acum_sobre_viable", "siaf_dev_ytd_sobre_pia", "asi_frac_supervision_90d", "ie_ratio_ultimo", "ie_ratio_min_90d"):
            return f"{fixed[f]}: {_pct(v)}"
        if f == "ib_log_monto_contrato" or f.startswith("est_log_"):
            return f"{fixed[f].replace(' (escala log)', '')}: S/ {_n(math.exp(v) - 1) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 'sin dato'}"
        return f"{fixed[f]}: {_n(v)}"
    cat = {"est_dep_code": "Departamento de la obra (codigo INEI)", "est_sector": "Sector de la inversion", "est_nivel_gobierno": "Nivel de gobierno",
           "est_tipo_inversion": "Tipo de inversion", "est_marco": "Marco de inversion (SNIP/Invierte.pe)", "est_tipo_entidad": "Tipo de entidad contratante",
           "est_link_method": "Metodo de enlace con el CUI"}
    if f in cat:
        return f"{cat[f]}: {v}"
    if f.startswith("est_"):
        return f"{f[4:].replace('_', ' ').capitalize()}: {v}"
    return f"{f}: {_n(v) if isinstance(v, (int, float)) else v}"
