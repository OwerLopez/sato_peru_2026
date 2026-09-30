"""Informe tecnico de alerta temprana en PDF (una obra con cuaderno de obra digital).

Documento TECNICO generado por SATO a partir de datos abiertos oficiales; no es un documento
oficial de ninguna entidad ni una determinacion de responsabilidad. Incluye: resumen ejecutivo con
el riesgo vigente a 60 dias, datos de la obra y del contrato, serie historica de estimaciones,
factores TreeSHAP, escenarios de sensibilidad, asientos del cuaderno de obra que sustentan la
alerta y marco normativo.

El diseno sigue el sistema visual de la interfaz web: la misma paleta de nivel (con forma ademas
de color, para que el nivel no dependa solo del color), la serie azul validada para los graficos y
una jerarquia tipografica sobria apta para impresion en blanco y negro.
"""

from __future__ import annotations

import datetime as dt
import io
from uuid import UUID
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from sato.api import db
from sato.api.security import audit

router = APIRouter(tags=["informes"])

# Tokens del sistema visual (coinciden con web/src/index.css y web/src/lib/colores.ts)
TINTA = colors.HexColor("#16202c")
TENUE = colors.HexColor("#3e4a5b")
SUAVE = colors.HexColor("#4b5a6d")
LINEA = colors.HexColor("#dde3ea")
FONDO = colors.HexColor("#f4f6f9")
MARCA = colors.HexColor("#1f72b4")
MARCA_OSC = colors.HexColor("#0f4c7f")
MARCA_900 = colors.HexColor("#0a1c30")
MARCA_50 = colors.HexColor("#eff6fc")
SERIE = colors.HexColor("#2a78d6")
COLOR = {"ALTO": colors.HexColor("#b42318"), "MEDIO": colors.HexColor("#a64106"), "BAJO": colors.HexColor("#067647")}
SUAVE_NIVEL = {"ALTO": colors.HexColor("#fef3f2"), "MEDIO": colors.HexColor("#fef6ee"), "BAJO": colors.HexColor("#ecfdf3")}
NIVEL_TXT = {"ALTO": "RIESGO ALTO", "MEDIO": "RIESGO MEDIO", "BAJO": "RIESGO BAJO"}

ANCHO = A4[0] - 3.6 * cm  # ancho util con margenes de 1,8 cm


def _estilos() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.2, leading=13, textColor=TINTA, alignment=TA_LEFT)
    return {
        "cuerpo": base,
        "chico": ParagraphStyle("chico", parent=base, fontSize=7.8, leading=10.6, textColor=TENUE),
        "celda": ParagraphStyle("celda", parent=base, fontSize=8.4, leading=11),
        "etiqueta": ParagraphStyle("etiqueta", parent=base, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=SUAVE),
        "sobre": ParagraphStyle("sobre", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=MARCA),
        "titulo": ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=MARCA_900),
        "obra": ParagraphStyle("obra", parent=base, fontSize=10.5, leading=14, textColor=TENUE),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=MARCA_900),
        "kpi": ParagraphStyle("kpi", parent=base, fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=TINTA),
        "cifra": ParagraphStyle("cifra", parent=base, fontName="Helvetica-Bold", fontSize=30, leading=32),
        "cita": ParagraphStyle("cita", parent=base, fontName="Helvetica-Oblique", fontSize=8.2, leading=11.2, textColor=TINTA),
        "cab_tabla": ParagraphStyle("cab_tabla", parent=base, fontName="Helvetica-Bold", fontSize=7.6, leading=9.5, textColor=colors.white),
        "der": ParagraphStyle("der", parent=base, fontSize=8.4, leading=11, alignment=TA_RIGHT),
    }


def _p(txt, st) -> Paragraph:
    return Paragraph(escape(str(txt if txt is not None else "-")), st)


def _soles(x) -> str:
    return "-" if x is None else f"S/ {float(x):,.2f}"


def _fecha(x) -> str:
    return "-" if x is None else (x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x))


def _pct(x, d=1) -> str:
    return "-" if x is None else f"{100 * float(x):.{d}f} %"


SIGLAS = {"AA.HH.", "CUI", "EIRL", "GR", "I.E.", "IE", "IEI", "MD", "MDL", "MP", "MPA", "N°", "PIP", "SAC", "S.A.C.", "SRL", "UGEL"}


def nombre_legible(s: str | None) -> str:
    """Pasa a tipo oracion una denominacion publicada en mayusculas, sin tocar codigos ni siglas."""
    if not s:
        return "-"
    letras = [c for c in s if c.isalpha()]
    if not letras or sum(c.islower() for c in letras) / len(letras) > 0.2:
        return s
    out, inicio = [], True
    for tok in s.split(" "):
        limpio = tok.strip("()[],;:\"'")
        if any(c.isdigit() for c in tok) or limpio in SIGLAS or (tok.endswith(".") and len(tok) <= 4):
            out.append(tok)
        else:
            w = tok.lower()
            out.append(w[:1].upper() + w[1:] if inicio else w)
        inicio = tok.endswith((".", ":", ";")) and not tok.endswith("..")
    return " ".join(out)


def _forma(nivel: str, x: float, y: float, r: float, color) -> Polygon | Circle:
    """Forma asociada al nivel (triangulo, circulo, cuadrado): el nivel no depende solo del color."""
    if nivel == "ALTO":
        return Polygon([x - r, y - r * 0.85, x + r, y - r * 0.85, x, y + r], fillColor=color, strokeColor=None)
    if nivel == "MEDIO":
        return Circle(x, y, r * 0.9, fillColor=color, strokeColor=None)
    return Rect(x - r * 0.8, y - r * 0.8, 1.6 * r, 1.6 * r, fillColor=color, strokeColor=None)


def _insignia(nivel: str) -> Drawing:
    txt = NIVEL_TXT.get(nivel, nivel)
    w = 1.05 * cm + 0.2 * cm * len(txt)
    d = Drawing(w, 0.62 * cm)
    d.add(Rect(0, 0, w, 0.62 * cm, rx=0.31 * cm, ry=0.31 * cm, fillColor=COLOR[nivel], strokeColor=None))
    d.add(_forma(nivel, 0.36 * cm, 0.31 * cm, 0.13 * cm, colors.white))
    d.add(String(0.62 * cm, 0.19 * cm, txt, fontName="Helvetica-Bold", fontSize=7.6, fillColor=colors.white))
    return d


def _escala(score: float, umbral: float | None, nivel: str, ancho: float) -> Drawing:
    """Escala 0-100 % con la posicion de la obra y el umbral de riesgo alto del modelo."""
    h = 1.35 * cm
    d = Drawing(ancho, h)
    y = 0.62 * cm
    d.add(Rect(0, y, ancho, 0.16 * cm, rx=0.08 * cm, ry=0.08 * cm, fillColor=LINEA, strokeColor=None))
    d.add(Rect(0, y, max(0.16 * cm, ancho * min(score, 1)), 0.16 * cm, rx=0.08 * cm, ry=0.08 * cm, fillColor=COLOR[nivel], strokeColor=None))
    if umbral is not None:
        ux = ancho * umbral
        d.add(Line(ux, y - 0.14 * cm, ux, y + 0.3 * cm, strokeColor=TINTA, strokeWidth=0.9, strokeDashArray=[2, 1.5]))
        d.add(String(ux, y + 0.42 * cm, f"umbral de riesgo alto {100 * umbral:.1f} %", fontName="Helvetica", fontSize=6.6, fillColor=TENUE,
                     textAnchor="middle" if 0.2 < umbral < 0.8 else "start"))
    sx = ancho * min(score, 1)
    d.add(Circle(sx, y + 0.08 * cm, 0.15 * cm, fillColor=colors.white, strokeColor=COLOR[nivel], strokeWidth=1.6))
    for v in (0, 25, 50, 75, 100):
        d.add(String(ancho * v / 100, 0.06 * cm, f"{v} %", fontName="Helvetica", fontSize=6.4, fillColor=SUAVE,
                     textAnchor="start" if v == 0 else ("end" if v == 100 else "middle")))
    return d


def _grafico(serie, umbral, ancho) -> Drawing:
    d = Drawing(ancho, 6 * cm)
    if not serie:
        return d
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 1.1 * cm, 0.9 * cm, ancho - 1.4 * cm, 4.5 * cm
    lp.data = [[(i, 100 * s["score"]) for i, s in enumerate(serie)]]
    lp.lines[0].strokeColor = SERIE
    lp.lines[0].strokeWidth = 2
    lp.lines[0].symbol = makeMarker("FilledCircle", size=3.2, fillColor=SERIE, strokeColor=colors.white)
    n = len(serie)
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = -0.5, max(n - 0.5, 0.5)
    paso = max(1, (n + 11) // 12)
    lp.xValueAxis.valueSteps = list(range(0, n, paso))
    lp.xValueAxis.labelTextFormat = lambda i: serie[int(i)]["fecha_corte"].strftime("%m/%y") if 0 <= int(i) < n else ""
    lp.xValueAxis.labels.fontName = "Helvetica"
    lp.xValueAxis.labels.fontSize = 6.8
    lp.xValueAxis.labels.fillColor = TENUE
    lp.xValueAxis.strokeColor = LINEA
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax, lp.yValueAxis.valueStep = 0, 100, 25
    lp.yValueAxis.labelTextFormat = "%d %%"
    lp.yValueAxis.labels.fontName = "Helvetica"
    lp.yValueAxis.labels.fontSize = 6.8
    lp.yValueAxis.labels.fillColor = TENUE
    lp.yValueAxis.strokeColor = None
    lp.yValueAxis.visibleGrid = 1
    lp.yValueAxis.gridStrokeColor = LINEA
    lp.yValueAxis.gridStrokeWidth = 0.5
    lp.yValueAxis.gridStart, lp.yValueAxis.gridEnd = lp.x, lp.x + lp.width
    d.add(lp)
    if umbral is not None:
        y = lp.y + lp.height * umbral
        d.add(Line(lp.x, y, lp.x + lp.width, y, strokeColor=TINTA, strokeDashArray=[3, 2], strokeWidth=0.8))
        d.add(String(lp.x + lp.width, y + 3, "umbral de riesgo alto", fontName="Helvetica", fontSize=6.6, fillColor=TINTA, textAnchor="end"))
    ult = serie[-1]
    xu = lp.x + lp.width * ((n - 1) + 0.5) / max(n, 1)
    yu = lp.y + lp.height * ult["score"]
    d.add(String(min(xu, lp.x + lp.width) - 3, yu + 6, f"{100 * ult['score']:.1f} %", fontName="Helvetica-Bold", fontSize=7.4, fillColor=TINTA,
                 textAnchor="end"))
    d.add(String(0, lp.y + lp.height + 10, "Probabilidad estimada de atraso formal a 60 días", fontName="Helvetica-Bold", fontSize=7.4, fillColor=TENUE))
    return d


def _barra_factor(shap: float, maximo: float, ancho: float) -> Drawing:
    """Barra divergente: hacia la derecha eleva el riesgo, hacia la izquierda lo reduce."""
    d = Drawing(ancho, 0.42 * cm)
    c = ancho / 2
    d.add(Line(c, 0, c, 0.42 * cm, strokeColor=SUAVE, strokeWidth=0.6))
    w = max(1.5, (ancho / 2 - 2) * abs(shap) / maximo)
    color = COLOR["ALTO"] if shap > 0 else COLOR["BAJO"]
    d.add(Rect(c if shap > 0 else c - w, 0.1 * cm, w, 0.22 * cm, fillColor=color, strokeColor=None))
    return d


def _seccion(num: int, texto: str, st) -> Table:
    t = Table([[_p(f"{num:02d}", st["sobre"]), Paragraph(escape(texto), st["h2"])]], colWidths=[0.95 * cm, ANCHO - 0.95 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.8, MARCA_900), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _tabla(filas, anchos, cabecera=True, zebra=True, alinear_der: tuple[int, ...] = ()) -> Table:
    t = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    est = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
           ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA)]
    if cabecera:
        est += [("BACKGROUND", (0, 0), (-1, 0), MARCA_900), ("LINEBELOW", (0, 0), (-1, 0), 0, MARCA_900)]
    if zebra:
        for i in range(1 if cabecera else 0, len(filas)):
            if (i - (1 if cabecera else 0)) % 2 == 1:
                est.append(("BACKGROUND", (0, i), (-1, i), FONDO))
    for c in alinear_der:
        est.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(est))
    return t


class _Lienzo(rl_canvas.Canvas):
    """Lienzo en dos pasadas para numerar 'Pagina X de Y'."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._paginas: list[dict] = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont("Helvetica", 7)
            self.setFillColor(SUAVE)
            self.drawRightString(A4[0] - 1.8 * cm, 1.05 * cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _construir(o, m, serie, fact, evid, sims, cal, oid: str) -> bytes:
    st = _estilos()
    ult = serie[-1]
    nivel = ult["nivel"]
    ahora = dt.datetime.now()
    folio = oid[:8].upper()
    E: list = []

    # ---------------------------------------------------------------- portada / resumen ejecutivo
    E.append(_p("INFORME TÉCNICO DE ALERTA TEMPRANA", st["sobre"]))
    E.append(Spacer(1, 3))
    E.append(_p("Riesgo de atraso formal en la ejecución de la obra", st["titulo"]))
    E.append(Spacer(1, 4))
    E.append(_p(nombre_legible(o["denominacion"]), st["obra"]))
    E.append(Spacer(1, 10))

    if o.get("fecha_atraso"):
        msg = (f"La obra ya registró el evento formal de atraso el {_fecha(o['fecha_atraso'])}. La última estimación disponible antes de "
               f"esa fecha fue de {_pct(ult['score'])} (nivel {nivel.lower()}).")
    else:
        msg = (f"Al corte del {_fecha(ult['fecha_corte'])} la obra no registra el evento formal de atraso. El modelo estima una probabilidad de "
               f"<b>{_pct(ult['score'])}</b> de que se registre la causal de demora injustificada (valorización acumulada ejecutada menor al 80 % "
               f"de la programada; RLCE art. 203 / RLGCP art. 207) en los próximos {m['horizonte_dias']} días si persisten los factores detectados.")
    conf = ""
    if cal and cal["tasa"] is not None and cal["base"]:
        veces = cal["tasa"] / cal["base"] if cal["base"] else None
        conf = (f"En la validación con datos pasados, {_pct(cal['tasa'])} de las obras clasificadas en nivel {nivel.lower()} registró el atraso "
                f"formal dentro de {m['horizonte_dias']} días, frente a un promedio general de {_pct(cal['base'])}"
                + (f" ({veces:.1f} veces el promedio)." if veces and nivel == "ALTO" else "."))
    izq = [
        _p("PROBABILIDAD A " + str(m["horizonte_dias"]) + " DÍAS", st["etiqueta"]),
        Spacer(1, 2),
        Paragraph(f'<font color="{COLOR[nivel].hexval().replace("0x", "#")}">{100 * ult["score"]:.1f}</font>'
                  f'<font size="14" color="{TENUE.hexval().replace("0x", "#")}"> %</font>', st["cifra"]),
        Spacer(1, 4),
        _insignia(nivel),
    ]
    der = [Paragraph(msg, st["cuerpo"])]
    if conf:
        der += [Spacer(1, 5), _p(conf, st["chico"])]
    resumen = Table([[izq, der]], colWidths=[4.6 * cm, ANCHO - 4.6 * cm - 0.8 * cm])
    resumen.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 14),
                                 ("LINEAFTER", (0, 0), (0, 0), 0.6, LINEA), ("LEFTPADDING", (1, 0), (1, 0), 14)]))
    caja = Table([[resumen], [_escala(float(ult["score"]), m.get("umbral_alerta"), nivel, ANCHO - 0.8 * cm)]], colWidths=[ANCHO])
    caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SUAVE_NIVEL[nivel]), ("LINEBEFORE", (0, 0), (0, -1), 3.5, COLOR[nivel]),
                              ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, 0), 12),
                              ("BOTTOMPADDING", (0, -1), (-1, -1), 8), ("TOPPADDING", (0, 1), (-1, 1), 10)]))
    E.append(caja)
    E.append(Spacer(1, 10))

    def kpi(t, v, det=""):
        return [_p(t.upper(), st["etiqueta"]), Spacer(1, 2), _p(v, st["kpi"])] + ([_p(det, st["chico"])] if det else [])

    k = Table([[kpi("Monto del contrato", _soles(o["monto_contrato"]) if o.get("monto_contrato") is not None else "No publicado"),
                kpi("Plazo original", f"{o['plazo_original_dias']} días" if o.get("plazo_original_dias") else "No publicado"),
                kpi("Asientos del cuaderno", f"{o.get('n_asientos') or 0:,}", f"desde {_fecha(o.get('primer_asiento'))}"),
                kpi("Último asiento", _fecha(o.get("ultimo_asiento")))]], colWidths=[ANCHO / 4] * 4)
    k.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, LINEA), ("LINEAFTER", (0, 0), (-2, 0), 0.6, LINEA),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    E.append(k)
    E.append(Spacer(1, 14))

    # ---------------------------------------------------------------- 1. identificacion
    E.append(_seccion(1, "Identificación de la obra y del contrato", st))
    E.append(Spacer(1, 6))
    ubic = " / ".join(x for x in (o.get("distrito"), o.get("provincia"), o.get("departamento")) if x) or "-"
    filas = [("Denominación oficial", o["denominacion"]), ("Entidad contratante", o.get("entidad")), ("Contratista", o.get("contratista")),
             ("Ubicación (distrito / provincia / departamento)", ubic), ("Código Único de Inversión (CUI)", o.get("cui") or "no enlazado"),
             ("Inversión asociada", o.get("inversion_nombre")), ("Función", o.get("funcion")),
             ("Identificador del contrato (SEACE)", o.get("contrato_id")), ("Monto del contrato", _soles(o.get("monto_contrato"))),
             ("Monto aprobado de la inversión", _soles(o.get("monto_viable"))),
             ("Cuaderno de obra digital", f"{o.get('n_asientos')} asientos entre {_fecha(o.get('primer_asiento'))} y {_fecha(o.get('ultimo_asiento'))}")]
    E.append(_tabla([[_p(a, st["etiqueta"]), _p(b, st["celda"])] for a, b in filas], [5.4 * cm, ANCHO - 5.4 * cm], cabecera=False))

    # ---------------------------------------------------------------- 2. evolucion
    E.append(Spacer(1, 14))
    E.append(KeepTogether([
        _seccion(2, f"Evolución del riesgo estimado a {m['horizonte_dias']} días", st), Spacer(1, 8),
        _grafico(serie, m.get("umbral_alerta"), ANCHO),
        _p(f"Estimaciones mensuales calculadas solo con la información disponible en cada fecha de corte ({len(serie)} {'corte' if len(serie) == 1 else 'cortes'}, "
           f"del {_fecha(serie[0]['fecha_corte'])} al {_fecha(ult['fecha_corte'])}), con reentrenamiento trimestral del modelo.", st["chico"]),
    ]))

    # ---------------------------------------------------------------- 3. factores
    E.append(Spacer(1, 14))
    E.append(CondPageBreak(6 * cm))
    E.append(_seccion(3, "Factores que explican la estimación", st))
    E.append(Spacer(1, 4))
    E.append(_p("Contribución de cada dato a la probabilidad (valores TreeSHAP en log-odds). Las barras hacia la derecha elevan el riesgo y "
                "las barras hacia la izquierda lo reducen, respecto del promedio de las obras.", st["chico"]))
    E.append(Spacer(1, 6))
    if fact:
        maximo = max(abs(f["shap"]) for f in fact) or 1
        ft = [[_p("Dato de la obra", st["cab_tabla"]), _p("Grupo", st["cab_tabla"]), _p("Reduce  |  Eleva", st["cab_tabla"]),
               _p("Efecto", st["cab_tabla"])]]
        for f in fact:
            ft.append([_p(f["descripcion"], st["celda"]), _p(f["grupo"], st["chico"]), _barra_factor(f["shap"], maximo, 3.4 * cm),
                       _p(f"{f['shap']:+.3f}", st["der"])])
        E.append(_tabla(ft, [ANCHO - 9.2 * cm, 3.6 * cm, 3.8 * cm, 1.8 * cm], alinear_der=(3,)))
    else:
        E.append(_p("La estimación no tiene factores registrados.", st["chico"]))

    # ---------------------------------------------------------------- 4. sensibilidad
    n = 4
    if sims:
        E.append(Spacer(1, 14))
        E.append(KeepTogether([
            _seccion(n, "Qué cambiaría la estimación (sensibilidad del modelo)", st), Spacer(1, 4),
            _p("Recálculo de la probabilidad modificando una señal a la vez. Indica cuánto depende la estimación de cada señal; no es una "
               "estimación causal del efecto de una intervención real.", st["chico"]), Spacer(1, 6),
            _tabla([[_p("Escenario", st["cab_tabla"]), _p("Actual", st["cab_tabla"]), _p("Escenario", st["cab_tabla"]), _p("Cambio", st["cab_tabla"])]]
                   + [[_p(s["descripcion"], st["celda"]), _pct(s["score_base"]), _pct(s["score_escenario"]),
                       f"{100 * (s['score_escenario'] - s['score_base']):+.1f} pp"] for s in sims],
                   [ANCHO - 6.6 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm], alinear_der=(1, 2, 3)),
        ]))
        n += 1

    # ---------------------------------------------------------------- 5. evidencia
    E.append(Spacer(1, 14))
    E.append(CondPageBreak(5 * cm))
    E.append(_seccion(n, "Evidencia documental", st))
    E.append(Spacer(1, 4))
    E.append(_p("Asientos del cuaderno de obra digital y otros registros oficiales asociados a los factores que elevan el riesgo, del más reciente "
                "al más antiguo (hasta 12).", st["chico"]))
    E.append(Spacer(1, 6))
    if not evid:
        E.append(_p("No hay registros asociados a los factores que aumentan el riesgo.", st["chico"]))
    for e in evid:
        if e["fuente"] == "ASIENTO":
            cab = f"Asiento N.° {e['nro_asiento']}  ·  {e['tipo']}" + (f"  ·  {e['rol']}" if e.get("rol") else "") + f"  ·  {_fecha(e['fecha'])}"
            pie = f"Fuente: {e.get('archivo_fuente') or 'cuaderno de obra digital (OECE)'}"
        else:
            cab, pie = f"{e['fuente']}  ·  {_fecha(e['fecha'])}", ""
        contenido = [_p(cab, ParagraphStyle("ec", parent=st["celda"], fontName="Helvetica-Bold", textColor=MARCA_OSC)), Spacer(1, 2),
                     _p(e["extracto"], st["cita"])] + ([Spacer(1, 2), _p(pie, st["chico"])] if pie else [])
        tarjeta = Table([[contenido]], colWidths=[ANCHO])
        tarjeta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("LINEBEFORE", (0, 0), (0, -1), 2.5, MARCA),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                     ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        E += [KeepTogether([tarjeta]), Spacer(1, 5)]
    n += 1

    # ---------------------------------------------------------------- 6. marco y validez
    met = (m["metricas"] or {}).get("arequipa", {})
    nac = (m["metricas"] or {}).get("nacional", {})

    def f3(d, k):
        v = d.get(k)
        return "-" if v is None else f"{float(v):.3f}"

    E.append(Spacer(1, 10))
    E.append(CondPageBreak(6 * cm))
    E.append(_seccion(n, "Marco normativo, validez del modelo y lectura del informe", st))
    E.append(Spacer(1, 6))
    E.append(_p("Evento que se anticipa: primer asiento del cuaderno de obra digital de tipo «Valorización acumulada ejecutada menor al 80 % del "
                "monto acumulado programado» o «Calendario acelerado de obra» (Reglamento de la Ley N.° 30225, D.S. N.° 344-2018-EF, art. 203; "
                "Reglamento de la Ley N.° 32069, D.S. N.° 009-2025-EF, art. 207).", st["cuerpo"]))
    E.append(Spacer(1, 6))
    E.append(_tabla([[_p("Indicador (prueba temporal ciega)", st["cab_tabla"]), _p("Nacional", st["cab_tabla"]), _p("Arequipa", st["cab_tabla"])],
                     *[[_p(t, st["celda"]), _p(f3(nac, k), st["der"]), _p(f3(met, k), st["der"])]
                       for t, k in (("ROC-AUC", "roc_auc"), ("PR-AUC", "pr_auc"), ("Prevalencia del evento", "prevalencia"))]],
                    [ANCHO - 6 * cm, 3 * cm, 3 * cm], alinear_der=(1, 2)))
    E.append(Spacer(1, 6))
    E.append(_p(f"Modelo {m['version']}, entrenado con información hasta el {_fecha(m.get('entrenado_hasta'))}. Una PR-AUC mayor que la "
                "prevalencia indica que el modelo ordena las obras mejor que el azar.", st["chico"]))
    E.append(Spacer(1, 8))
    lectura = Table([[[_p("CÓMO USAR ESTE INFORME", st["etiqueta"]), Spacer(1, 3),
                       _p("La probabilidad es una estimación para priorizar la supervisión, no una certeza ni una determinación de "
                          "responsabilidades. Contraste siempre los factores y la evidencia con el expediente de la obra y con la información "
                          "del supervisor o inspector antes de adoptar decisiones.", st["celda"])]]], colWidths=[ANCHO])
    lectura.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MARCA_50), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#b7d4ee")),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    E.append(KeepTogether([lectura]))

    # ---------------------------------------------------------------- paginas
    def portada(c, doc):
        c.saveState()
        c.setFillColor(MARCA_900)
        c.rect(0, A4[1] - 2.7 * cm, A4[0], 2.7 * cm, fill=1, stroke=0)
        c.setFillColor(MARCA)
        c.rect(0, A4[1] - 2.8 * cm, A4[0], 0.1 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(1.8 * cm, A4[1] - 1.45 * cm, "SATO")
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#b7d4ee"))
        c.drawString(1.8 * cm, A4[1] - 1.95 * cm, "Sistema de Alerta Temprana de Obras Públicas")
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(A4[0] - 1.8 * cm, A4[1] - 1.2 * cm, f"INFORME N.° {folio}")
        c.setFont("Helvetica", 7.6)
        c.setFillColor(colors.HexColor("#b7d4ee"))
        c.drawRightString(A4[0] - 1.8 * cm, A4[1] - 1.62 * cm, f"Emitido el {ahora:%d/%m/%Y a las %H:%M}")
        c.drawRightString(A4[0] - 1.8 * cm, A4[1] - 2.0 * cm, f"Modelo {m['version']}  ·  corte {_fecha(ult['fecha_corte'])}")
        c.restoreState()
        pie(c, doc)

    def interior(c, doc):
        c.saveState()
        c.setFont("Helvetica-Bold", 7.4)
        c.setFillColor(MARCA_900)
        c.drawString(1.8 * cm, A4[1] - 1.2 * cm, "SATO")
        c.setFont("Helvetica", 7.4)
        c.setFillColor(SUAVE)
        c.drawString(2.7 * cm, A4[1] - 1.2 * cm, "Informe técnico de alerta temprana")
        c.drawRightString(A4[0] - 1.8 * cm, A4[1] - 1.2 * cm, f"Informe N.° {folio}")
        c.setStrokeColor(LINEA)
        c.setLineWidth(0.6)
        c.line(1.8 * cm, A4[1] - 1.4 * cm, A4[0] - 1.8 * cm, A4[1] - 1.4 * cm)
        c.restoreState()
        pie(c, doc)

    def pie(c, doc):
        c.saveState()
        c.setStrokeColor(LINEA)
        c.setLineWidth(0.6)
        c.line(1.8 * cm, 1.45 * cm, A4[0] - 1.8 * cm, 1.45 * cm)
        c.setFont("Helvetica", 6.8)
        c.setFillColor(SUAVE)
        c.drawString(1.8 * cm, 1.05 * cm, "Documento técnico elaborado con datos abiertos oficiales (OECE, MEF, Contraloría). "
                                         "No es un documento oficial ni determina responsabilidades.")
        c.drawString(1.8 * cm, 0.72 * cm, f"Identificador de la obra: {oid}")
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.9 * cm,
                          title=f"Informe técnico de alerta temprana N.° {folio}", author="SATO",
                          subject="Riesgo de atraso formal en obra pública", creator="SATO", keywords="alerta temprana, obra pública, Perú")
    marco_portada = Frame(doc.leftMargin, doc.bottomMargin, doc.width, A4[1] - doc.bottomMargin - 3.5 * cm, id="portada", leftPadding=0,
                          rightPadding=0, topPadding=0, bottomPadding=0)
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="interior", leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="portada", frames=[marco_portada], onPage=portada, autoNextPageTemplate="interior"),
                          PageTemplate(id="interior", frames=[marco], onPage=interior)])
    doc.build(E, canvasmaker=_Lienzo)
    return buf.getvalue()


@router.get("/obras/{cuaderno_id}/informe-pdf")
def informe_pdf(cuaderno_id: UUID, request: Request):
    oid = str(cuaderno_id)
    o = db.one("""select o.*, e.nombre entidad, c.nombre contratista, i.nombre inversion_nombre, i.funcion, i.monto_viable
                  from obra o left join entidad e on e.ruc = o.entidad_ruc left join contratista c on c.ruc = o.contratista_ruc
                  left join inversion i on i.cui = o.cui where o.cuaderno_id = :id""", id=oid)
    if not o:
        raise HTTPException(404, "Obra no encontrada")
    m = db.one("select id, version, horizonte_dias, umbral_alerta, entrenado_hasta, metricas from modelo where activo")
    if not m:
        raise HTTPException(503, "No hay un modelo activo cargado")
    serie = db.rows("select id, fecha_corte, tipo, score, nivel, alerta from prediccion where cuaderno_id = :id and modelo_id = :m order by fecha_corte",
                    id=oid, m=m["id"])
    if not serie:
        raise HTTPException(409, "La obra no tiene predicciones del modelo activo")
    ult = serie[-1]
    fact = db.rows("select descripcion, grupo, shap from explicacion where prediccion_id = :p order by rango", p=ult["id"])
    evid = db.rows("""select ev.feature, ev.fuente, ev.fecha, ev.extracto, a.nro_asiento, a.tipo, a.rol, a.archivo_fuente
                      from evidencia ev left join asiento a on a.id = ev.asiento_id where ev.prediccion_id = :p
                      order by ev.fecha desc nulls last limit 12""", p=ult["id"])
    vistos: set = set()
    evid = [e for e in evid if not ((e["fuente"], e["nro_asiento"], e["extracto"]) in vistos or vistos.add((e["fuente"], e["nro_asiento"], e["extracto"])))]
    sims = db.rows("select descripcion, score_base, score_escenario from simulacion where prediccion_id = :p order by score_escenario", p=ult["id"])
    cal = db.one("""select avg(y_observado::float) filter (where nivel = :n) tasa, avg(y_observado::float) base
                    from prediccion where modelo_id = :m and tipo = 'backtest' and y_observado is not null""", n=ult["nivel"], m=m["id"])
    pdf = _construir(o, m, serie, fact, evid, sims, cal, oid)
    audit(request, "INFORME_PDF", None, f"obra:{oid}")
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="informe_alerta_{oid[:8]}.pdf"'})


@router.get("/predicciones/{prediccion_id}/simulacion")
def simulacion(prediccion_id: int):
    return db.rows("select escenario, descripcion, score_base, score_escenario, alerta_escenario from simulacion where prediccion_id = :p order by score_escenario",
                   p=prediccion_id)
