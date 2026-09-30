"""Pruebas de extremo a extremo (navegador real -> nginx -> API -> PostgreSQL con los datos oficiales cargados).

    SATO_E2E_URL=http://localhost:8080 pytest tests/e2e      (por defecto http://localhost:8080)

Usan Playwright con el navegador Edge o Chrome instalado en el equipo (channel msedge/chrome), sin descargar
navegadores. Se omiten si Playwright no esta instalado o si la plataforma no responde.
Verifican flujos reales de usuario, ausencia de errores de consola, estados de error, accesibilidad por teclado
y diseno sin desborde horizontal en pantallas de telefono.
"""

from __future__ import annotations

import os
import re
import urllib.request

import pytest

URL = os.environ.get("SATO_E2E_URL", "http://localhost:8080").rstrip("/")
pw = pytest.importorskip("playwright.sync_api")


def _arriba() -> bool:
    try:
        return urllib.request.urlopen(f"{URL}/api/ready", timeout=5).status == 200
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _arriba(), reason=f"la plataforma no responde en {URL}")
RUTAS = ["/", "/obras", "/cartera", "/comparador", "/laboratorio", "/fuentes", "/sistema", "/guia", "/suscribirse", "/login", "/buscar?q=colegio"]


@pytest.fixture(scope="module")
def navegador():
    with pw.sync_playwright() as p:
        b = None
        for canal in ("msedge", "chrome", None):
            try:
                b = p.chromium.launch(channel=canal) if canal else p.chromium.launch()
                break
            except Exception:  # noqa: BLE001
                continue
        if b is None:
            pytest.skip("no hay un navegador Chromium disponible")
        yield b
        b.close()


@pytest.fixture
def pagina(navegador):
    ctx = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="es-PE")
    pg = ctx.new_page()
    pg.errores = []  # type: ignore[attr-defined]
    pg.on("console", lambda m: m.type == "error" and pg.errores.append(m.text))  # type: ignore[attr-defined]
    pg.on("pageerror", lambda e: pg.errores.append(str(e)))  # type: ignore[attr-defined]
    yield pg
    ctx.close()


def _ir(pg, ruta: str):
    pg.goto(URL + ruta, wait_until="networkidle")
    pg.wait_for_selector("main h1", timeout=15000)


@pytest.mark.parametrize("ruta", RUTAS)
def test_cada_pantalla_carga_sin_errores(pagina, ruta):
    _ir(pagina, ruta)
    assert pagina.locator("main h1").first.inner_text().strip()
    assert not pagina.locator("[role=alert]").count(), pagina.locator("[role=alert]").first.inner_text()
    assert pagina.errores == []  # type: ignore[attr-defined]


def test_panorama_muestra_datos_reales(pagina):
    # la cifra se compara con la API publica (datos cargados), no con un valor fijo
    _ir(pagina, "/")
    resumen = pagina.request.get(URL + "/api/v1/resumen").json()
    alto = resumen["consolidado"]["alto"]
    assert f"{alto:,}" in pagina.locator("main").inner_text()


def test_busqueda_global_y_ficha_de_obra(pagina):
    _ir(pagina, "/")
    pagina.get_by_label("Buscar obras").fill("puente")
    pagina.keyboard.press("Enter")
    pagina.wait_for_url(re.compile(r"/buscar\?q=puente"))
    pagina.wait_for_selector("main a[href^='/obras/'], main a[href^='/cartera/']", timeout=15000)
    pagina.locator("main a[href^='/obras/'], main a[href^='/cartera/']").first.click()
    pagina.wait_for_url(re.compile(r"/(obras|cartera)/"))
    pagina.wait_for_selector("main h1")
    assert pagina.errores == []  # type: ignore[attr-defined]


def test_ficha_con_pestanas_y_evidencia(pagina):
    obra = pagina.request.get(URL + "/api/v1/obras?solo_vigentes=true&nivel=ALTO&tamanio=1").json()["items"][0]
    _ir(pagina, f"/obras/{obra['cuaderno_id']}")
    pestanas = pagina.get_by_role("tab")
    assert pestanas.count() >= 4
    for i in range(pestanas.count()):
        pestanas.nth(i).click()
        assert pagina.get_by_role("tabpanel").is_visible()
    pestanas.first.click()
    ver = pagina.get_by_role("button", name=re.compile("Ver evidencia"))
    if ver.count():
        ver.first.click()
        dialogo = pagina.get_by_role("dialog")
        assert dialogo.is_visible()
        pagina.keyboard.press("Escape")
        assert dialogo.count() == 0 or not dialogo.is_visible()
    assert pagina.errores == []  # type: ignore[attr-defined]


def test_filtros_se_guardan_en_la_url(pagina):
    _ir(pagina, "/obras?nivel=ALTO")
    pagina.wait_for_selector("main table tbody tr")
    badges = pagina.locator("main table tbody tr").all_inner_texts()
    assert badges and all("Alto" in b for b in badges)
    pagina.reload(wait_until="networkidle")
    assert "nivel=ALTO" in pagina.url


def test_error_de_la_api_muestra_mensaje_y_reintento(pagina):
    pagina.route("**/api/v1/sistema/estado", lambda r: r.fulfill(status=503, body='{"detail":"x"}', content_type="application/json"))
    pagina.goto(URL + "/sistema", wait_until="networkidle")
    alerta = pagina.get_by_role("alert")
    alerta.wait_for(timeout=15000)
    assert "no está disponible" in alerta.inner_text()
    pagina.unroute("**/api/v1/sistema/estado")
    alerta.get_by_role("button", name="Reintentar").click()
    pagina.wait_for_selector("main h1", timeout=15000)
    assert "Estado y monitoreo" in pagina.locator("main h1").inner_text()


def test_ruta_inexistente(pagina):
    pagina.goto(URL + "/no-existe", wait_until="networkidle")
    assert pagina.get_by_text("Página no encontrada").is_visible()


def test_enlace_para_saltar_al_contenido(pagina):
    _ir(pagina, "/")
    pagina.keyboard.press("Tab")
    enlace = pagina.get_by_role("link", name="Saltar al contenido principal")
    assert enlace.is_visible()
    enlace.press("Enter")
    assert pagina.evaluate("document.activeElement.id") == "contenido"


def test_controles_con_nombre_accesible(pagina):
    for ruta in ("/", "/obras", "/sistema"):
        _ir(pagina, ruta)
        sin_nombre = pagina.evaluate("""() => [...document.querySelectorAll('button, a[href], input, select')]
            .filter(e => e.offsetParent !== null)
            .filter(e => !(e.getAttribute('aria-label') || e.innerText.trim() || e.getAttribute('title') || (e.labels && e.labels.length)
                           || e.getAttribute('aria-labelledby') || e.getAttribute('placeholder')))
            .map(e => e.outerHTML.slice(0, 120))""")
        assert sin_nombre == [], (ruta, sin_nombre)


@pytest.mark.parametrize("ruta", [*RUTAS, "ficha-obra", "ficha-cartera"])
def test_telefono_sin_desborde_horizontal(navegador, ruta):
    ctx = navegador.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, locale="es-PE")
    pg = ctx.new_page()
    if ruta == "ficha-obra":
        ruta = "/obras/" + pg.request.get(URL + "/api/v1/obras?solo_vigentes=true&tamanio=1").json()["items"][0]["cuaderno_id"]
    elif ruta == "ficha-cartera":
        ruta = "/cartera/" + pg.request.get(URL + "/api/v1/cartera?estado=ACTIVA&tamanio=1").json()["items"][0]["codigo_infobras"]
    try:
        pg.goto(URL + ruta, wait_until="networkidle")
        pg.wait_for_selector("main h1")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 375 + 1
        pg.get_by_role("button", name="Abrir menú").click()
        assert pg.get_by_role("dialog").get_by_role("link", name="Estado y monitoreo").is_visible()
    finally:
        ctx.close()
