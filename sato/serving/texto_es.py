"""Ortografia de los textos generados para la interfaz (descripciones de factores, grupos y escenarios).

Los identificadores internos se escriben sin tildes; esta funcion restituye la acentuacion en palabras completas antes de
mostrarlas. Es idempotente y no toca los valores numericos ni los textos de las fuentes oficiales (asientos).
"""

from __future__ import annotations

import re

_PALABRAS = {
    "anio": "año", "Anio": "Año", "aprobacion": "aprobación", "administracion": "administración", "aplicacion": "aplicación",
    "Caracteristicas": "Características", "caracteristicas": "características", "climaticos": "climáticos", "codigo": "código",
    "Dias": "Días", "dias": "días", "dia": "día", "Ejecucion": "Ejecución", "ejecucion": "ejecución", "fisicas": "físicas",
    "Fraccion": "Fracción", "Funcion": "Función", "inversion": "inversión", "Metodo": "Método", "Minimo": "Mínimo",
    "ordenes": "órdenes", "paralizacion": "paralización", "participacion": "participación", "poblacion": "población",
    "Proporcion": "Proporción", "segun": "según", "Supervision": "Supervisión", "suspension": "suspensión", "tecnico": "técnico",
    "Ultima": "Última", "Ultimo": "Último", "ultimo": "último", "ultimos": "últimos", "ultima": "última", "ultimas": "últimas",
}
_RX = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _PALABRAS), key=len, reverse=True)) + r")\b")


def acentuar(texto):
    if not isinstance(texto, str):
        return texto
    return _RX.sub(lambda m: _PALABRAS[m.group(1)], texto)
