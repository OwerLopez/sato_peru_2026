"""Lenguaje claro para los factores que explican cada prediccion.

Traduce cada variable del modelo y su VALOR REAL observado a una frase comprensible para un auditor, un funcionario o
un ciudadano, sin jerga tecnica. No se agregan causas ni interpretaciones: la frase solo describe el dato, y el sentido
de su efecto (aumenta o reduce el riesgo) lo aporta el valor SHAP que acompana a cada factor.

    factor_cuaderno("ib_dias_para_fin_programado", -45)  -> "El plazo original vencio hace 45 dias"
    factor_cartera("hist_entidad_tasa_retraso", 0.63)     -> "El 63 % de las obras anteriores de la entidad termino con retraso significativo"

Los textos se escriben con tildes (UTF-8). `GRUPOS_CLAROS` renombra los grupos de variables para la interfaz.
"""

from __future__ import annotations

import math
import re

DEPARTAMENTO_INEI = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho", "06": "Cajamarca", "07": "Callao",
    "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque",
    "15": "Lima", "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura", "21": "Puno",
    "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
TIPO_ENTIDAD = {"MUNI_DISTRITAL": "municipalidad distrital", "MUNI_PROVINCIAL": "municipalidad provincial", "GOB_REGIONAL": "gobierno regional",
                "PROGRAMA_NACIONAL": "programa nacional", "MINISTERIO": "ministerio", "OTRA": "otra entidad pública"}
NIVEL_GOBIERNO = {"GN": "gobierno nacional", "GR": "gobierno regional", "GL": "gobierno local"}
MARCO = {"SNIP": "SNIP (sistema anterior a Invierte.pe)", "INVIERTE": "Invierte.pe"}
ENLACE = {"regex_nombre": "por el código citado en el nombre de la obra", "fuzzy_tfidf": "por similitud del nombre de la obra",
          "infobras": "por INFOBRAS"}

TIPO_ASIENTO = {
    "ampliacion_plazo": "ampliación de plazo", "suspension_plazo": "suspensión del plazo", "adicionales": "adicionales de obra",
    "mayores_metrados": "mayores metrados", "consultas": "consultas", "respuestas_consultas": "respuestas a consultas",
    "penalidades": "aplicación de penalidades", "ordenes": "órdenes", "riesgos": "gestión de riesgos",
    "constatacion_fisica": "constatación física", "programa_cpm": "programa de ejecución", "calendario_valorizado": "calendario de avance valorizado",
    "valorizaciones": "valorizaciones y metrados", "otras_modificaciones": "otras modificaciones del contrato", "reducciones": "reducciones de obra",
    "personal_clave": "personal clave", "expediente_tecnico": "expediente técnico", "adelantos": "adelantos", "otras_ocurrencias": "otras ocurrencias",
    "inicio_plazo": "inicio del plazo",
}
TEMA = {
    "atraso": "atraso, retraso o demora", "proxy_80": "la regla del 80 % o un calendario acelerado", "paralizacion": "paralización o frentes sin trabajo",
    "clima": "lluvias u otros eventos climáticos", "financiero": "pagos, adelantos o presupuesto", "materiales": "falta de materiales",
    "equipo": "maquinaria o equipos", "personal": "falta o cambio de personal", "expediente": "deficiencias del expediente técnico",
    "terreno": "interferencias, terreno o conflictos sociales", "adicionales": "adicionales, deductivos o mayores metrados",
    "controversia": "controversias o arbitraje", "incumplimiento": "penalidades, incumplimientos o cartas notariales",
    "calidad": "observaciones de calidad", "suspension": "suspensión o reinicio de la obra", "progreso": "avance normal o adelantado",
}

GRUPOS_CLAROS = {
    "Registros del cuaderno de obra": "Actividad del cuaderno de obra",
    "Contenido de los asientos (NLP)": "Contenido de los asientos",
    "Avance reportado en asientos (NLP)": "Avance declarado en el cuaderno",
    "Ejecucion financiera (SIAF)": "Ejecución del gasto (SIAF)",
    "Ejecución financiera (SIAF)": "Ejecución del gasto (SIAF)",
    "Seguimiento Invierte.pe (F12B)": "Seguimiento en Invierte.pe",
    "Historial de actores": "Historial de la entidad y el contratista",
    "Contrato (INFOBRAS, al inicio)": "Datos del contrato",
    "Caracteristicas de la obra": "Características de la obra",
    "Características de la obra": "Características de la obra",
    "Calendario": "Época del año",
    "Caracteristicas de la obra al inicio": "Características de la obra",
    "Características de la obra al inicio": "Características de la obra",
    "Nombre de la obra (NLP)": "Nombre de la obra",
}


def _nulo(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _num(v) -> float | None:
    if _nulo(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def entero(v) -> str:
    """Numero entero con separador de miles de uso peruano (1,234)."""
    return f"{round(v):,}"


def soles(v) -> str:
    return "S/ 0" if abs(v) < 1 else f"S/ {v:,.0f}"


def pct(v) -> str:
    return f"{100 * v:.0f} %"


def indice(v) -> str:
    return f"{v:.2f}"


def plural(n: float, uno: str, varios: str) -> str:
    return uno if round(n) == 1 else varios


CATEGORICAS_CUADERNO = {"est_dep_code", "est_tipo_entidad", "est_nivel_gobierno", "est_marco", "est_link_method", "est_sector", "est_tipo_inversion"}


def factor_cuaderno(f: str, v=None, cat: str | None = None) -> str:
    """Frase clara para una variable del modelo de alerta a 60 dias (cuaderno de obra digital)."""
    x = _num(v)
    if f in CATEGORICAS_CUADERNO:
        cat = cat if cat is not None else (None if _nulo(v) else str(v))
        x = None
    else:
        cat = None  # variable numerica: sin valor es "sin dato", nunca un texto
    sin = x is None and cat is None
    m = re.match(r"asi_(cum|90d)_(.+)", f)
    if m:
        tipo = TIPO_ASIENTO.get(m.group(2), m.group(2).replace("_", " "))
        cuando = "desde el inicio del cuaderno" if m.group(1) == "cum" else "en los últimos 90 días"
        if sin:
            return f"Asientos de {tipo} {cuando}: sin dato"
        return f"{entero(x)} {plural(x, 'asiento', 'asientos')} de {tipo} {cuando}" if x else f"Ningún asiento de {tipo} {cuando}"
    m = re.match(r"txt_lx_(.+)", f)
    if m:
        tema = TEMA.get(m.group(1), m.group(1))
        if sin:
            return f"Menciones de {tema} en los asientos recientes: sin dato"
        return f"El {pct(x)} de los asientos de los últimos 60 días menciona {tema}" if x else f"Ningún asiento de los últimos 60 días menciona {tema}"
    if f.startswith(("txt_lsa_", "txt_emb_")):
        return "Rasgo del contenido de los asientos recientes (representación semántica)"
    if sin:
        return f"{etiqueta(f, 'cuaderno')}: sin dato"
    if f == "txt_stack_tfidf":
        return f"Índice de alerta por las palabras usadas en los asientos recientes: {indice(x)} (escala de 0 a 1)"
    if f == "txt_stack_emb":
        return f"Índice de alerta por el contenido de los asientos recientes: {indice(x)} (escala de 0 a 1)"
    if f == "ib_dias_para_fin_programado":
        return f"El plazo original venció hace {entero(-x)} días" if x < 0 else f"Faltan {entero(x)} días para el fin del plazo original"
    if f == "ib_frac_plazo_transcurrido":
        return f"Ha transcurrido el {pct(x)} del plazo original"
    if f == "asi_dias_desde_ultimo":
        return "Hubo un asiento el mismo día del corte" if x < 1 else f"El último asiento se registró hace {entero(x)} {plural(x, 'día', 'días')}"
    if f == "asi_dias_desde_primero":
        return f"El cuaderno de obra se abrió hace {entero(x)} días"
    if f == "asi_dias_desde_inicio_plazo":
        return f"Han pasado {entero(x)} días desde el inicio del plazo de ejecución"
    if f == "asi_dias_activos_30d":
        return f"Hubo registros en el cuaderno {entero(x)} {plural(x, 'día', 'días')} del último mes" if x else "No hubo registros en el cuaderno en el último mes"
    if f == "asi_ritmo_30d_vs_90d":
        return f"Registros del último mes: {indice(x)} veces el promedio mensual del trimestre" if x else "Sin registros en el último mes, pese a haberlos en el trimestre"
    if f in ("asi_n_30d", "asi_n_90d", "asi_n_total", "txt_n_asientos_60d"):
        periodo = {"asi_n_30d": "en los últimos 30 días", "asi_n_90d": "en los últimos 90 días", "asi_n_total": "en total",
                   "txt_n_asientos_60d": "con texto en los últimos 60 días"}[f]
        return f"{entero(x)} {plural(x, 'asiento registrado', 'asientos registrados')} {periodo}"
    if f == "asi_frac_supervision_90d":
        return f"El {pct(x)} de los asientos de los últimos 90 días fue registrado por la supervisión o inspección"
    if f == "asi_consultas_pendientes":
        return "No hay consultas pendientes de respuesta" if x <= 0 else f"{entero(x)} {plural(x, 'consulta', 'consultas')} sin respuesta registrada"
    if f == "txt_len_media_60d":
        return f"Extensión media de los asientos recientes: {entero(x)} caracteres"
    if f == "ie_ratio_ultimo":
        return f"Según el último avance declarado en el cuaderno, se ejecutó el {pct(x)} de lo programado"
    if f == "ie_ratio_min_90d":
        return f"El menor avance declarado en los últimos 90 días fue el {pct(x)} de lo programado"
    if f == "ie_brecha_ultima":
        pp = 100 * x
        return f"El último avance declarado está {abs(pp):.0f} puntos {'por debajo' if pp < 0 else 'por encima'} de lo programado"
    if f == "ie_n_atrasada_60d":
        return f"{entero(x)} {plural(x, 'asiento declara', 'asientos declaran')} la obra atrasada en los últimos 60 días"
    if f == "ie_n_adelantada_60d":
        return f"{entero(x)} {plural(x, 'asiento declara', 'asientos declaran')} la obra adelantada en los últimos 60 días"
    if f == "ie_dias_desde_reporte":
        return f"El último avance declarado en el cuaderno tiene {entero(x)} días"
    if f == "siaf_dev_acum":
        return f"Gasto acumulado de la inversión (devengado): {soles(x)}"
    if f == "siaf_dev_3m":
        return f"Gasto devengado en los últimos 3 meses: {soles(x)}"
    if f == "siaf_dev_ytd":
        return f"Gasto devengado en lo que va del año: {soles(x)}"
    if f == "siaf_pia_anio":
        return f"Presupuesto inicial asignado este año (PIA): {soles(x)}"
    if f == "siaf_meses_desde_ultimo_dev":
        return f"{entero(x)} {plural(x, 'mes', 'meses')} sin gasto devengado" if x else "Hubo gasto devengado el mes anterior"
    if f == "siaf_dev_acum_sobre_viable":
        return f"Se ha gastado el {pct(x)} del monto aprobado de la inversión"
    if f == "siaf_dev_ytd_sobre_pia":
        return f"Se ha gastado el {pct(x)} del presupuesto inicial del año"
    if f == "mefseg_registros_180d":
        return f"{entero(x)} {plural(x, 'registro', 'registros')} de seguimiento en Invierte.pe en los últimos 180 días"
    if f == "mefseg_problemas_180d":
        return f"{entero(x)} {plural(x, 'problema reportado', 'problemas reportados')} en el seguimiento de Invierte.pe (180 días)"
    if f == "mefseg_problema_atraso_180d":
        return f"{entero(x)} {plural(x, 'reporte', 'reportes')} de atraso o paralización en Invierte.pe (180 días)"
    if f == "actor_contratista_obras_previas":
        return f"El contratista tiene {entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} con cuaderno digital"
    if f == "actor_contratista_atrasos_previos":
        return f"{entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} del contratista {plural(x, 'tuvo', 'tuvieron')} atraso formal"
    if f == "actor_entidad_obras_previas":
        return f"La entidad tiene {entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} con cuaderno digital"
    if f == "actor_entidad_atrasos_previos":
        return f"{entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} de la entidad {plural(x, 'tuvo', 'tuvieron')} atraso formal"
    if f in ("ib_plazo_original_dias", "est_plazo_vigencia_dias"):
        return f"{'Plazo de ejecución original' if f.startswith('ib_') else 'Vigencia original del contrato'}: {entero(x)} días"
    if f in ("ib_log_monto_contrato", "est_log_monto_viable", "est_log_monto_contratado"):
        monto = math.expm1(x)
        nombre = {"ib_log_monto_contrato": "Monto del contrato", "est_log_monto_viable": "Monto aprobado de la inversión",
                  "est_log_monto_contratado": "Monto contratado según SEACE"}[f]
        return f"{nombre}: sin monto registrado" if monto < 1 else f"{nombre}: {soles(monto)}"
    if f == "est_n_miembros_consorcio":
        return f"El consorcio contratista tiene {entero(x)} integrantes"
    booleanos = {
        "est_es_consorcio": ("El contratista es un consorcio", "El contratista no es un consorcio"),
        "est_arequipa": ("La obra está en Arequipa", "La obra está fuera de Arequipa"),
        "est_tiene_cui": ("La obra está enlazada a una inversión pública (CUI)", "La obra no está enlazada a una inversión pública (CUI)"),
        "est_tiene_seace": ("El contrato está publicado en SEACE", "El contrato no se encontró en SEACE"),
        "est_regimen_ley32069": ("El cuaderno se rige por la nueva Ley 32069", "El cuaderno se rige por la Ley 30225"),
        "tmp_vigencia_ley32069": ("Corte posterior a la vigencia de la Ley 32069", "Corte anterior a la vigencia de la Ley 32069"),
    }
    if f in booleanos:
        return booleanos[f][0 if x >= 0.5 else 1]
    if f == "tmp_mes":
        return f"Mes del corte: {MESES[int(x) - 1]}" if 1 <= x <= 12 else f"Mes del corte: {entero(x)}"
    c = cat.strip() if cat else None
    if f in CATEGORICAS_CUADERNO and c is None:
        return f"{etiqueta(f, 'cuaderno')}: sin dato"
    if f == "est_dep_code":
        return f"Departamento: {DEPARTAMENTO_INEI.get(c, 'no identificado')}"
    if f == "est_tipo_entidad":
        return f"Entidad contratante: {TIPO_ENTIDAD.get(c, c.lower())}"
    if f == "est_nivel_gobierno":
        return f"Nivel de gobierno de la inversión: {NIVEL_GOBIERNO.get(c, 'no identificado')}"
    if f == "est_marco":
        return f"Sistema de inversión: {MARCO.get(c, 'no identificado')}"
    if f == "est_link_method":
        return f"La inversión se identificó {ENLACE.get(c, c)}"
    if f in ETIQUETA_CUADERNO:
        return f"{ETIQUETA_CUADERNO[f]}: {c if c is not None else entero(x)}"
    return f"{f.split('_', 1)[-1].replace('_', ' ').capitalize()}: {c if c is not None else x}"


ETIQUETA_CUADERNO = {
    "est_sector": "Sector de la inversión", "est_tipo_inversion": "Tipo de inversión", "txt_stack_tfidf": "Índice de alerta por las palabras de los asientos",
    "txt_stack_emb": "Índice de alerta por el contenido de los asientos", "ib_dias_para_fin_programado": "Días para el fin del plazo original",
    "ib_frac_plazo_transcurrido": "Plazo original transcurrido", "asi_dias_desde_ultimo": "Días desde el último asiento",
    "asi_dias_desde_inicio_plazo": "Días desde el inicio del plazo", "asi_consultas_pendientes": "Consultas sin respuesta",
    "siaf_dev_acum_sobre_viable": "Gasto respecto del monto aprobado", "siaf_dev_ytd_sobre_pia": "Gasto respecto del presupuesto del año",
    "siaf_dev_3m": "Gasto de los últimos 3 meses", "siaf_meses_desde_ultimo_dev": "Meses sin gasto devengado",
    "ib_log_monto_contrato": "Monto del contrato", "est_log_monto_viable": "Monto aprobado de la inversión",
    "est_log_monto_contratado": "Monto contratado según SEACE", "ie_ratio_ultimo": "Último avance declarado",
    "ie_dias_desde_reporte": "Días desde el último avance declarado", "est_dep_code": "Departamento", "tmp_mes": "Mes del corte",
    "est_tipo_entidad": "Entidad contratante", "est_nivel_gobierno": "Nivel de gobierno de la inversión", "est_marco": "Sistema de inversión",
    "est_link_method": "Identificación de la inversión",
    "txt_len_media_60d": "Extensión media de los asientos recientes", "txt_n_asientos_60d": "Asientos con texto en los últimos 60 días",
}


HIST_ACTOR = {"hist_entidad": ("la entidad", "de la entidad"), "hist_contratista": ("el ejecutor", "del ejecutor"),
              "hist_provincia": ("la provincia", "de la provincia")}


def factor_cartera(f: str, v=None, cat: str | None = None) -> str:
    """Frase clara para una variable de los modelos de cartera INFOBRAS (al inicio y de seguimiento)."""
    x = _num(v)
    c = cat.strip() if cat else None
    for pre, (quien, de) in HIST_ACTOR.items():
        if f.startswith(pre + "_"):
            var = f[len(pre) + 1:]
            if x is None:
                return f"Historial {de}: sin obras anteriores con resultado conocido"
            if var == "tasa_retraso":
                return f"El {pct(x)} de las obras anteriores {de} terminó con retraso significativo"
            if var == "sobreplazo_mediano":
                if x <= 0:
                    return f"Las obras anteriores {de} terminaron, en la mediana, dentro de su plazo"
                return f"Las obras anteriores {de} se extendieron, en la mediana, un {pct(x)} de su plazo"
            if var == "obras_previas":
                return f"{quien.capitalize()} tiene {entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} registradas en INFOBRAS"
            if var == "resultados_previos":
                return f"{quien.capitalize()} tiene {entero(x)} {plural(x, 'obra anterior', 'obras anteriores')} con resultado conocido"
            if var == "en_curso":
                return f"{quien.capitalize()} tenía {entero(x)} {plural(x, 'obra', 'obras')} en curso al iniciar esta"
            return f"Historial {de}: {var.replace('_', ' ')} {entero(x)}"
    cats = {"ea_modalidad": "Modalidad de ejecución", "ea_naturaleza": "Naturaleza de la obra", "ea_tipo1": "Tipo de obra", "ea_tipo2": "Subtipo de obra",
            "ea_tipo3": "Tipo de obra (detalle)", "ea_nivel_gobierno": "Nivel de gobierno", "ea_sector_entidad": "Sector de la entidad",
            "ea_departamento": "Departamento", "ea_tipo_inversion": "Tipo de inversión", "ea_marco": "Sistema de inversión", "ea_funcion": "Función presupuestal"}
    if f in cats:
        valor = c if c is not None else (str(v) if v is not None else "sin dato")
        if f in ("ea_departamento", "ea_funcion", "ea_sector_entidad", "ea_tipo_inversion"):
            valor = valor.capitalize() if valor.isupper() else valor
        return f"{cats[f]}: {valor}"
    if x is None:
        return f"{etiqueta(f, 'cartera')}: sin dato"
    if f in ("ea_log_monto_contrato", "ea_log_costo_et", "ea_log_monto_viable", "ea_costo_por_dia"):
        monto = math.expm1(x)
        return f"{ETIQUETA_CARTERA[f]}: sin monto registrado" if monto < 1 else f"{ETIQUETA_CARTERA[f]}: {soles(monto)}"
    if f == "ea_log_plazo":
        return f"Plazo de ejecución original: {entero(math.exp(x))} días"
    if f == "ea_ratio_contrato_et":
        return f"El monto del contrato equivale al {pct(x)} del costo del expediente técnico"
    if f == "ea_txt_nombre":
        return f"Índice de alerta por el nombre de la obra: {indice(x)} (escala de 0 a 1, según obras con nombres parecidos)"
    if f == "ea_anio_inicio":
        return f"Año de inicio: {int(round(x))}"
    if f == "ea_mes_inicio":
        return f"Mes de inicio: {MESES[int(x) - 1]}" if 1 <= x <= 12 else f"Mes de inicio: {entero(x)}"
    if f == "ea_dias_expediente_inicio":
        if x < 0:
            return f"El expediente técnico figura aprobado {entero(-x)} días después del inicio de la obra"
        return f"Pasaron {entero(x)} días entre la aprobación del expediente técnico y el inicio"
    if f == "ea_dias_viabilidad_inicio":
        return f"Pasaron {entero(x)} días entre la declaración de viabilidad y el inicio de la obra"
    if f == "ea_terreno_entregado":
        return f"Terreno entregado al inicio: {entero(x)} %"
    if f == "sg_frac_plazo":
        return f"Ha transcurrido el {pct(x)} del plazo original"
    if f == "sg_dias_al_fin_prog":
        return f"El plazo original venció hace {entero(-x)} días" if x < 0 else f"Faltan {entero(x)} días para el fin del plazo original"
    if f in ("sg_dev_acum_costo", "sg_dev_desde_inicio_costo", "sg_dev_3m_costo", "sg_pia_anio_costo"):
        que = {"sg_dev_acum_costo": "El gasto acumulado de la inversión", "sg_dev_desde_inicio_costo": "El gasto desde el inicio de la obra",
               "sg_dev_3m_costo": "El gasto de los últimos 3 meses", "sg_pia_anio_costo": "El presupuesto inicial del año"}[f]
        return f"{que} equivale al {pct(x)} del costo de la obra"
    if f == "sg_meses_sin_dev":
        return f"{entero(x)} {plural(x, 'mes', 'meses')} seguidos sin gasto devengado" if x else "Hubo gasto devengado el último mes con datos"
    if f == "sg_meses_con_dev":
        return f"{entero(x)} {plural(x, 'mes', 'meses')} con gasto devengado desde el inicio"
    if f == "sg_brecha_ritmo":
        pp = 100 * x
        return f"El avance del gasto va {abs(pp):.0f} puntos {'por detrás' if pp < 0 else 'por delante'} del avance del plazo"
    booleanos = {
        "ea_con_supervision": ("Tiene supervisión contratada registrada", "No registra supervisión contratada"),
        "ea_entrega_parcial": ("El terreno se entregó de forma parcial", "El terreno no se entregó de forma parcial"),
        "ea_saldo_de_obra": ("Es el saldo de una obra anterior", "No es saldo de una obra anterior"),
        "ea_reconstruccion": ("Forma parte de la Reconstrucción con Cambios", "No forma parte de la Reconstrucción con Cambios"),
        "ea_reactivacion": ("Marcada como obra de reactivación económica", "No marcada como obra de reactivación económica"),
        "ea_tiene_cui": ("Tiene código único de inversión (CUI)", "No tiene código único de inversión (CUI)"),
        "sg_vencido": ("El plazo original ya venció", "El plazo original aún no vence"),
    }
    if f in booleanos:
        return booleanos[f][0 if x >= 0.5 else 1]
    return f"{ETIQUETA_CARTERA.get(f, f)}: {entero(x)}"


ETIQUETA_CARTERA = {
    "ea_log_monto_contrato": "Monto del contrato", "ea_log_costo_et": "Costo según expediente técnico", "ea_log_monto_viable": "Monto aprobado de la inversión",
    "ea_costo_por_dia": "Costo por día de plazo", "ea_log_plazo": "Plazo de ejecución original", "ea_txt_nombre": "Índice de alerta por el nombre de la obra",
    "ea_dias_expediente_inicio": "Días entre el expediente técnico y el inicio", "ea_anio_inicio": "Año de inicio", "ea_mes_inicio": "Mes de inicio",
    "sg_brecha_ritmo": "Ritmo del gasto frente al plazo", "sg_frac_plazo": "Plazo original transcurrido",
    "ea_dias_viabilidad_inicio": "Días entre la viabilidad y el inicio", "ea_ratio_contrato_et": "Monto del contrato respecto del expediente técnico",
}


def etiqueta(f: str, modelo: str) -> str:
    """Nombre legible de una variable; si no tiene etiqueta propia, usa la descripcion tecnica acentuada (nunca el codigo interno)."""
    from sato.serving.texto_es import acentuar

    propia = (ETIQUETA_CUADERNO if modelo == "cuaderno" else ETIQUETA_CARTERA).get(f)
    if propia:
        return propia
    if modelo == "cuaderno":
        from sato.serving.descriptions import describe_tecnico as tec
    else:
        from sato.serving.descriptions_cartera import describe_c_tecnico as tec
    texto = tec(f, None).rsplit(":", 1)[0]
    return acentuar(texto) if texto != f else f.split("_", 1)[-1].replace("_", " ").capitalize()


def categoria(descripcion: str | None) -> str | None:
    """Recupera el valor categorico escrito al final de una descripcion tecnica ('Departamento de la obra (codigo INEI): 04' -> '04')."""
    if not descripcion or ":" not in descripcion:
        return None
    v = descripcion.rsplit(":", 1)[1].strip()
    return None if v in ("", "sin dato") else v
