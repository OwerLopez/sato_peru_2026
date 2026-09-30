"""Capturas de la interfaz para el articulo (figuras 7 a 10, 12 y 13), tomadas del sistema en ejecucion.

Requiere el sistema levantado (docker compose up -d db api web) y Playwright con Microsoft Edge:
    pip install -r requirements-e2e.txt pymupdf
    python docs/articulo/capturar_interfaz.py
Las obras mostradas son las primeras del corte vigente en nivel alto: no se eligen ni se editan a mano.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from playwright.sync_api import sync_playwright

URL = "http://localhost:8080"
OUT = Path(__file__).parent / "figuras"
ANCHO = 1280


def recorte(pg, destino: str, alto: int) -> None:
    alto = min(alto, pg.evaluate("document.documentElement.scrollHeight"))
    pg.screenshot(path=str(OUT / destino), clip={"x": 0, "y": 0, "width": ANCHO, "height": alto}, full_page=True)


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": ANCHO, "height": 900}, device_scale_factor=2, locale="es-PE")
        req = ctx.request
        obra = req.get(URL + "/api/v1/obras?solo_vigentes=true&nivel=ALTO&tamanio=1").json()["items"][0]["cuaderno_id"]
        pg = ctx.new_page()

        def ir(ruta: str) -> None:
            pg.goto(URL + ruta, wait_until="networkidle")
            pg.wait_for_selector("main h1")
            pg.wait_for_timeout(1200)

        ir("/")
        recorte(pg, "fig7_panorama.png", 1500)
        ir(f"/obras/{obra}")
        recorte(pg, "fig8_ficha_obra.png", 1050)
        pg.get_by_role("tab", name="Factores").first.click()
        pg.wait_for_timeout(1200)
        pg.locator("main").screenshot(path=str(OUT / "fig9_factores_evidencia.png"))
        ir("/laboratorio")
        recorte(pg, "fig10_validacion.png", 1250)
        ir("/sistema")
        recorte(pg, "fig12_estado_monitoreo.png", 1300)

        pdf = req.get(URL + f"/api/v1/obras/{obra}/informe-pdf").body()
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        doc[0].get_pixmap(dpi=150).save(str(OUT / "fig13_informe_pdf.png"))
        b.close()
    print("capturas en", OUT, "obra", obra)


if __name__ == "__main__":
    main()
