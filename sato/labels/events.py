"""Definicion del evento objetivo: ATRASO SIGNIFICATIVO NORMATIVO.

Definicion operacional (reproducible, medible, fechada):

    Una obra entra en ATRASO SIGNIFICATIVO en la fecha del PRIMER asiento de su
    cuaderno de obra digital cuyo tipo sea
      - "Valorizacion acumulada ejecutada menor al 80% del monto acumulado
         programado", o
      - "Calendario acelerado de obra".

Justificacion normativa (texto oficial verificado, ver docs/research/EVIDENCE_LOG.md E5):
  * RLCE, DS 344-2018-EF, art. 203.1 (Ley 30225): si la valorizacion acumulada
    ejecutada es menor al 80% de la programada, el inspector/supervisor ordena
    un calendario acelerado "anotando tal hecho en el cuaderno de obra".
  * Reglamento de la Ley 32069, DS 009-2025-EF, art. 207.1 (modificado por DS
    001-2026-EF): misma regla (80% o atraso en la ruta critica), anotacion en
    el cuaderno de incidencias.
Ambos tipos de asiento son la manifestacion registral directa de esa regla.

Definicion alternativa para analisis de sensibilidad (DISRUPCION):
    atraso normativo  OR  suspension del plazo de ejecucion  OR  resolucion de contrato.
"""

from __future__ import annotations

import pandas as pd

ATRASO_TYPES = ("VALORIZACION_MENOR_80", "CALENDARIO_ACELERADO")
DISRUPCION_TYPES = ATRASO_TYPES + ("SUSPENSION_PLAZO", "RESOLUCION_CONTRATO")
FIN_TYPES = ("CULMINACION", "RECEPCION", "CIERRE", "RESOLUCION_CONTRATO")

TARGETS = {"atraso": ATRASO_TYPES, "disrupcion": DISRUPCION_TYPES}


def onset_dates(asientos: pd.DataFrame, types: tuple[str, ...]) -> pd.Series:
    """Fecha del primer asiento de alguno de los tipos dados, por cuaderno."""
    a = asientos[asientos["tipo_std"].isin(types)]
    return a.groupby("cuaderno_id")["fecha"].min()


def end_dates(asientos: pd.DataFrame) -> pd.Series:
    """Fin de la ventana de observacion util: primera culminacion/recepcion/cierre/resolucion."""
    a = asientos[asientos["tipo_std"].isin(FIN_TYPES)]
    return a.groupby("cuaderno_id")["fecha"].min()
