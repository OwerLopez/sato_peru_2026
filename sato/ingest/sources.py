"""Catalogo de fuentes oficiales (URLs verificadas el 2026-09-25).

Cada fuente declara como descubrir sus archivos. Las URLs de OECE se obtienen
de la API REST publica de Confluence de su wiki de datos abiertos (enlazada
desde datosabiertos.gob.pe), porque los nombres de archivo cambian cada mes.
"""

from __future__ import annotations

OECE_WIKI = "https://osce-gob-pe.atlassian.net/wiki"
OECE_PAGES = {
    # pagina Confluence -> prefijos de adjuntos a descargar
    "106889263": ("cod-asientos",),          # Cuaderno de Obra Digital - Asientos (mensual)
    "106889274": ("cod-cuadernos",),         # Cuaderno de Obra Digital - Cuadernos (anual)
    "106889259": ("valorizaciones",),        # Valorizaciones del SEACE (anual)
    "106889271": ("penalidades",),           # Penalidades de contratistas
}

MEF_FS = "https://fs.datosabiertos.mef.gob.pe/datastorefiles"
MEF_FILES = [
    "DETALLE_INVERSIONES.csv", "CIERRE_INVERSIONES.csv", "INVERSIONES_DESACTIVADAS.csv",
    "ESTADO_SITUACIONAL.csv", "FORMATO_12B.csv", "INVERSIONES_ET.csv", "PROCESO_SELECCION.csv",
    "Detalle_Inversiones_Diccionario.csv", "Cierre_Inversiones_Diccionario.csv", "F12B_Diccionario.csv",
    "Estado_Situacional_Diccionario.csv", "Inversiones_Desactivadas_Diccionario.csv",
    "Inversiones_ET_Diccionario.csv", "Proceso_Selecccion_Diccionario.csv", "Gastos_Diccionario.csv",
]
# SIAF: un zip por anio; los anios cerrados usan "AAAA-Gasto.zip", los recientes "AAAA-Gasto-Mensual.zip"
SIAF_YEARS = {2020: "2020-Gasto.zip", 2021: "2021-Gasto.zip", 2022: "2022-Gasto.zip", 2023: "2023-Gasto.zip",
              2024: "2024-Gasto.zip", 2025: "2025-Gasto-Mensual.zip", 2026: "2026-Gasto-Mensual.zip"}

INFOBRAS_DATASETS = "https://infobras.contraloria.gob.pe/InfobrasWeb/DataSets"
INFOBRAS_DOWNLOAD = ("https://infobras.contraloria.gob.pe/InfobrasWeb/Archivo/DownloadFile?filename={name}&name={name}"
                     "&contentType=application%2Fvnd.openxmlformats-officedocument.spreadsheetml.sheet&extension=.xlsx")

CONTRALORIA_COLLECTION = "https://www.gob.pe/institucion/contraloria/colecciones/18230-obras-paralizadas-documentos"

CONOSCE_CONTRATOS = "https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/contratos/{y}/CONOSCE_CONTRATOS{y}_0.xlsx"
CONOSCE_YEARS = range(2018, 2027)

USER_AGENT = "Mozilla/5.0 (SATO-AQP; tesis UNSA; datos abiertos)"
