"""Informe tecnico de alerta temprana en PDF (una obra con cuaderno de obra digital).

Documento TECNICO generado por SATO a partir de datos abiertos oficiales; no es un documento
oficial de ninguna entidad ni una determinacion de responsabilidad. Incluye: datos de la obra y
del contrato, riesgo vigente a 60 dias con su serie historica, factores TreeSHAP, asientos del
cuaderno de obra que sustentan la alerta, escenarios de sensibilidad y marco normativo.
"""

from __future__ import annotations

import datetime as dt
import io
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from sato.api import db
from sato.api.security import audit

router = APIRouter(tags=["informes"])
AZUL = colors.HexColor("#0f3d5e")
COLOR = {"ALTO": colors.HexColor("#b91c1c"), "MEDIO": colors.HexColor("#d97706"), "BAJO": colors.HexColor("#15803d")}


def _p(txt, st):
    from xml.sax.saxutils import escape

    return Paragraph(escape(str(txt if txt is not None else "-")), st)


def _soles(x):
    return "-" if x is None else f"S/ {float(x):,.2f}"


def _fecha(x):
    return "-" if x is None else (x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x))


def _grafico(serie, umbral):
    d = Drawing(16 * cm, 5.2 * cm)
    if not serie:
        return d
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 1.2 * cm, 0.8 * cm, 14.3 * cm, 3.9 * cm
    lp.data = [[(i, 100 * s["score"]) for i, s in enumerate(serie)]]
    lp.lines[0].strokeColor = COLOR["ALTO"]
    lp.lines[0].strokeWidth = 1.6
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = -0.5, max(len(serie) - 0.5, 0.5)
    lp.xValueAxis.valueSteps = list(range(len(serie)))
    lp.xValueAxis.labelTextFormat = lambda i: serie[int(i)]["fecha_corte"].strftime("%m/%y") if 0 <= int(i) < len(serie) else ""
    lp.xValueAxis.labels.fontSize = 6
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax, lp.yValueAxis.valueStep = 0, 100, 25
    lp.yValueAxis.labels.fontSize = 7
    d.add(lp)
    y = lp.y + lp.height * (100 * umbral) / 100
    d.add(Line(lp.x, y, lp.x + lp.width, y, strokeColor=COLOR["MEDIO"], strokeDashArray=[3, 2], strokeWidth=0.8))
    d.add(String(lp.x + lp.width - 2.6 * cm, y + 2, "umbral de alerta", fontSize=6, fillColor=COLOR["MEDIO"]))
    d.add(String(0, lp.y + lp.height + 6, "Probabilidad estimada (%)", fontSize=7))
    return d


@router.get("/obras/{cuaderno_id}/informe-pdf")
def informe_pdf(cuaderno_id: UUID, request: Request):
    oid = str(cuaderno_id)
    o = db.one("""select o.*, e.nombre entidad, c.nombre contratista, i.nombre inversion_nombre, i.funcion, i.monto_viable
                  from obra o left join entidad e on e.ruc = o.entidad_ruc left join contratista c on c.ruc = o.contratista_ruc
                  left join inversion i on i.cui = o.cui where o.cuaderno_id = :id""", id=oid)
    if not o:
        raise HTTPException(404, "Obra no encontrada")
    m = db.one("select id, version, horizonte_dias, umbral_alerta, entrenado_hasta, metricas from modelo where activo")
    serie = db.rows("select id, fecha_corte, tipo, score, nivel, alerta from prediccion where cuaderno_id = :id and modelo_id = :m order by fecha_corte", id=oid, m=m["id"])
    if not serie:
        raise HTTPException(409, "La obra no tiene predicciones del modelo activo")
    ult = serie[-1]
    fact = db.rows("select descripcion, grupo, shap from explicacion where prediccion_id = :p order by rango", p=ult["id"])
    evid = db.rows("""select ev.feature, ev.fuente, ev.fecha, ev.extracto, a.nro_asiento, a.tipo, a.rol, a.archivo_fuente
                      from evidencia ev left join asiento a on a.id = ev.asiento_id where ev.prediccion_id = :p
                      order by ev.fecha desc nulls last limit 12""", p=ult["id"])
    sims = db.rows("select descripcion, score_base, score_escenario from simulacion where prediccion_id = :p order by score_escenario", p=ult["id"])

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.8, leading=11.5, alignment=TA_JUSTIFY)
    small = ParagraphStyle("s", parent=body, fontSize=7.4, leading=9.4)
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=13.5, textColor=AZUL, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=10, textColor=AZUL, spaceBefore=8, spaceAfter=4)
    grid = TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef6fb")), ("FONTSIZE", (0, 0), (-1, -1), 8)])
    ahora = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    E = []
    E.append(_p("SATO - Sistema de Alerta Temprana de Obras Publicas", ParagraphStyle("k", parent=small, textColor=colors.grey)))
    E.append(_p("INFORME TECNICO DE ALERTA TEMPRANA DE ATRASO EN OBRA PUBLICA", h1))
    E.append(_p(f"Generado el {ahora} con el modelo {m['version']} a partir de datos abiertos oficiales (OECE, MEF, Contraloria). "
                "Documento tecnico de apoyo a la supervision: no es un documento oficial de la entidad contratante ni determina responsabilidades.", small))
    E.append(Spacer(1, 6))
    E.append(_p("1. Identificacion de la obra", h2))
    filas = [["Obra", _p(o["denominacion"], body)], ["Entidad", _p(o.get("entidad"), body)], ["Contratista", _p(o.get("contratista"), body)],
             ["Ubicacion", _p(f"{o.get('distrito')} / {o.get('provincia')} / {o.get('departamento')}", body)],
             ["CUI (Invierte.pe)", _p(o.get("cui") or "no enlazado", body)], ["Id. contrato (SEACE)", _p(o.get("contrato_id"), body)],
             ["Monto del contrato", _p(_soles(o.get("monto_contrato")), body)], ["Monto viable de la inversion", _p(_soles(o.get("monto_viable")), body)],
             ["Plazo original", _p(f"{o['plazo_original_dias']} dias" if o.get("plazo_original_dias") else "-", body)],
             ["Cuaderno de obra digital", _p(f"{o.get('n_asientos')} asientos entre {_fecha(o.get('primer_asiento'))} y {_fecha(o.get('ultimo_asiento'))}", body)]]
    t = Table(filas, colWidths=[4.2 * cm, 12.8 * cm])
    t.setStyle(grid)
    E.append(t)

    E.append(_p("2. Riesgo estimado a 60 dias", h2))
    nivel = ult["nivel"]
    msg = (f"Al corte del {_fecha(ult['fecha_corte'])} la obra no registra el evento formal de atraso. El modelo estima una probabilidad de "
           f"{100 * ult['score']:.1f} % de que se registre la causal de demora injustificada (valorizacion acumulada ejecutada menor al 80 % de la "
           f"programada; RLCE art. 203 / RLGCP art. 207) en los proximos {m['horizonte_dias']} dias si persisten los factores detectados. "
           f"Nivel: {nivel}.")
    if o.get("fecha_atraso"):
        msg = f"La obra ya registro el evento formal de atraso el {_fecha(o['fecha_atraso'])}. Ultima estimacion disponible: {100 * ult['score']:.1f} % (nivel {nivel})."
    box = Table([[_p(msg, ParagraphStyle("m", parent=body, textColor=colors.white))]], colWidths=[17 * cm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), COLOR[nivel]), ("BOX", (0, 0), (-1, -1), 0, COLOR[nivel]),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    E.append(box)
    E.append(Spacer(1, 4))
    E.append(_grafico(serie, m["umbral_alerta"]))
    E.append(_p("Serie de estimaciones mensuales calculadas solo con la informacion disponible en cada fecha (reentrenamiento trimestral).", small))

    E.append(_p("3. Factores que explican la estimacion (TreeSHAP)", h2))
    ft = [["Factor (valor observado)", "Grupo", "Efecto"]] + [[_p(f["descripcion"], small), _p(f["grupo"], small),
                                                              _p(("aumenta" if f["shap"] > 0 else "reduce") + f" ({f['shap']:+.3f})", small)] for f in fact]
    t = Table(ft, colWidths=[10.2 * cm, 4.3 * cm, 2.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    E.append(t)

    if sims:
        E.append(_p("4. Sensibilidad del modelo (escenarios)", h2))
        E.append(_p("Recalculo de la probabilidad modificando una senal a la vez. Indica cuanto depende la estimacion de cada senal; "
                    "no es una estimacion causal del efecto de una intervencion real.", small))
        st = [["Escenario", "Actual", "Escenario"]] + [[_p(s["descripcion"], small), f"{100 * s['score_base']:.1f} %", f"{100 * s['score_escenario']:.1f} %"] for s in sims]
        t = Table(st, colWidths=[12 * cm, 2.5 * cm, 2.5 * cm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7.5)]))
        E.append(t)

    E.append(_p("5. Evidencia documental (asientos del cuaderno de obra digital y otros registros)", h2))
    if not evid:
        E.append(_p("No hay registros asociados a los factores que aumentan el riesgo.", small))
    for e in evid:
        cab = (f"Asiento N. {e['nro_asiento']} - {e['tipo']} - {e.get('rol') or ''} - {_fecha(e['fecha'])} - fuente: {e.get('archivo_fuente') or ''}"
               if e["fuente"] == "ASIENTO" else f"{e['fuente']} - {_fecha(e['fecha'])}")
        E.append(KeepTogether([_p(cab, ParagraphStyle("c", parent=small, textColor=AZUL)), _p(e["extracto"], small), Spacer(1, 3)]))

    met = m["metricas"].get("arequipa", {})
    nac = m["metricas"].get("nacional", {})
    E.append(_p("6. Marco normativo y validez del modelo", h2))
    E.append(_p("Evento: primer asiento del cuaderno de obra digital de tipo 'Valorizacion acumulada ejecutada menor al 80% del monto acumulado "
                "programado' o 'Calendario acelerado de obra' (Reglamento de la Ley 30225, D.S. 344-2018-EF, art. 203; Reglamento de la Ley 32069, "
                "D.S. 009-2025-EF, art. 207). "
                f"Desempeno en el periodo de prueba temporal ciego: ROC-AUC {nac.get('roc_auc', float('nan')):.3f} (nacional) y "
                f"{met.get('roc_auc', float('nan')):.3f} (Arequipa); PR-AUC {nac.get('pr_auc', float('nan')):.3f} (nacional) frente a una prevalencia de "
                f"{nac.get('prevalencia', float('nan')):.3f}. Las estimaciones son probabilisticas y sirven para priorizar la supervision.", small))
    audit(request, "INFORME_PDF", None, f"obra:{oid}")

    buf = io.BytesIO()

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, f"SATO - Informe tecnico de alerta temprana - {oid}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Informe tecnico de alerta temprana", author="SATO")
    doc.build(E, onFirstPage=pie, onLaterPages=pie)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="informe_alerta_{oid[:8]}.pdf"'})


@router.get("/predicciones/{prediccion_id}/simulacion")
def simulacion(prediccion_id: int):
    return db.rows("select escenario, descripcion, score_base, score_escenario, alerta_escenario from simulacion where prediccion_id = :p order by score_escenario",
                   p=prediccion_id)
