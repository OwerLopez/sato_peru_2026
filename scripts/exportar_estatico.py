"""Exporta una copia estatica de solo lectura de SATO para GitHub Pages.

1. Recorre la interfaz real con un navegador (Playwright + Microsoft Edge) contra una API local sin limites de tasa
   y registra cada consulta GET que la interfaz hace a /api/v1: paginas, pestanas, filtros por nivel, ambitos
   departamentales y fichas de las obras en riesgo alto y medio.
2. Descarga la respuesta real de cada consulta y la guarda como JSON con la misma clave que calcula
   web/src/estatico.ts, ademas del informe PDF de cada obra con ficha exportada.

No se generan ni se editan datos: cada archivo es la respuesta de la API sobre la base cargada.
Requisitos: API en http://127.0.0.1:8000 (uvicorn, sin limite de tasa) y la web NORMAL (no estatica) servida con
vite preview, que reenvia /api a esa API. El procedimiento completo esta en scripts/publicar_pages.ps1.
    python scripts/exportar_estatico.py --web http://127.0.0.1:4173 --salida web/dist-pages/datos
"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

from playwright.async_api import async_playwright

API = "http://127.0.0.1:8000"
PREFIJO = "/api/v1"


def _fnv(s: str, h: int) -> str:
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def clave(ruta: str) -> str:
    """Misma normalizacion que claveDatos() en web/src/estatico.ts."""
    p, _, q = ruta.partition("?")
    pares = sorted(parse_qsl(q, keep_blank_values=True))
    norm = p + ("?" + "&".join(f"{k}={v}" for k, v in pares) if pares else "")
    return _fnv(norm, 0x811C9DC5) + _fnv(norm, 0x050C5D1F)


def get(ruta: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(API + ruta, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def ids(ruta: str, campo: str, paginas: int = 1) -> list[str]:
    out = []
    for n in range(1, paginas + 1):
        sep = "&" if "?" in ruta else "?"
        items = json.loads(get(f"{PREFIJO}{ruta}{sep}pagina={n}&tamanio=100")[1])["items"]
        out += [str(i[campo]) for i in items]
    return out


async def pulsar_todo(pg) -> None:
    """Activa cada pestana y cada control segmentado visible (sin enviar formularios ni descargar)."""
    for sel in ('[role="tab"]', "button[aria-pressed]"):
        n = await pg.locator(sel).count()
        for i in range(n):
            el = pg.locator(sel).nth(i)
            try:
                if await el.is_visible():
                    await el.click(timeout=3000)
                    await pg.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass


async def visitar(pg, web: str, ruta: str, interactuar: bool) -> None:
    try:
        await pg.goto(web + ruta, wait_until="networkidle", timeout=60000)
        await pg.wait_for_selector("main h1", timeout=30000)
        if interactuar:
            await pulsar_todo(pg)
    except Exception as e:  # la ruta queda registrada aunque la pagina falle: se informa y se sigue
        print("aviso", ruta, type(e).__name__)


async def trabajador(ctx, web, cola, registro, interactuar=True):
    pg = await ctx.new_page()
    pg.on("request", lambda r: registro.add(r.url) if r.method == "GET" and PREFIJO + "/" in r.url else None)
    await pg.goto(web + "/", wait_until="domcontentloaded")  # el almacenamiento local exige estar en el origen del sitio
    while True:
        try:
            ruta, ambito = cola.get_nowait()
        except asyncio.QueueEmpty:
            break
        await pg.evaluate("a => a ? localStorage.setItem('sato_ambito', a) : localStorage.removeItem('sato_ambito')", ambito)
        await visitar(pg, web, ruta, interactuar)
    await pg.close()


async def recorrer(web: str) -> set[str]:
    registro: set[str] = set()
    deps = [d["departamento"] for d in json.loads(get(f"{PREFIJO}/ambitos")[1])]
    alto = ids("/obras?solo_vigentes=true&nivel=ALTO", "cuaderno_id", paginas=2)
    medio = ids("/obras?solo_vigentes=true&nivel=MEDIO", "cuaderno_id")[:60]
    cartera = ids("/cartera?estado=ACTIVA&nivel=ALTO", "codigo_infobras")
    print(f"departamentos {len(deps)}; fichas cuaderno {len(alto)} alto + {len(medio)} medio; fichas cartera {len(cartera)}")

    cola: asyncio.Queue = asyncio.Queue()
    for r in ("/", "/obras", "/cartera", "/comparador", "/laboratorio", "/modelo", "/alertas", "/fuentes", "/sistema", "/guia",
              "/suscribirse", "/login"):
        cola.put_nowait((r, None))
    for d in deps:
        for r in ("/", "/obras", "/cartera"):
            cola.put_nowait((r, d))
    for i in alto + medio:
        cola.put_nowait((f"/obras/{i}", None))
    for c in cartera:
        cola.put_nowait((f"/cartera/{c}", None))

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge")
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, locale="es-PE")
        # primera visita para fijar el origen del almacenamiento local
        pg = await ctx.new_page()
        await pg.goto(web + "/", wait_until="networkidle")
        await pg.close()
        await asyncio.gather(*(trabajador(ctx, web, cola, registro) for _ in range(4)))
        await b.close()

    # consultas que dependen de una seleccion del usuario y no de la navegacion
    for d in deps:
        registro.add(f"{API}{PREFIJO}/ambitos/{quote(d, safe='')}/provincias")
    return registro


def exportar(urls: set[str], salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "pdf").mkdir(exist_ok=True)
    vistas: dict[str, str] = {}
    ok = omitidas = 0
    fichas = set()
    for u in sorted(urls):
        s = urlsplit(u)
        ruta = s.path[len(PREFIJO):] + (f"?{s.query}" if s.query else "")
        if not s.path.startswith(PREFIJO) or s.path.endswith("/informe-pdf"):
            continue
        k = clave(ruta)
        if k in vistas and vistas[k] != ruta:
            raise SystemExit(f"colision de clave {k}: {vistas[k]} / {ruta}")
        vistas[k] = ruta
        estado, cuerpo = get(PREFIJO + ruta)
        if estado != 200:
            omitidas += 1
            continue
        (salida / f"{k}.json").write_bytes(cuerpo)
        ok += 1
        partes = s.path.split("/")
        if len(partes) == 5 and partes[3] == "obras" and partes[4].count("-") == 4:
            fichas.add(partes[4])
    for f in sorted(fichas):
        estado, cuerpo = get(f"{PREFIJO}/obras/{f}/informe-pdf")
        if estado == 200:
            (salida / "pdf" / f"{f}.pdf").write_bytes(cuerpo)
    total = sum(p.stat().st_size for p in salida.rglob("*") if p.is_file())
    print(f"respuestas exportadas {ok}; omitidas (no 200) {omitidas}; informes PDF {len(fichas)}; tamano {total / 1e6:.1f} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    urls = asyncio.run(recorrer(a.web.rstrip("/")))
    print("consultas registradas", len(urls))
    exportar(urls, a.salida)


if __name__ == "__main__":
    main()
