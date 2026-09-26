"""Verifica referencias del articulo contra Crossref y genera la bibliografia IEEE a partir de los metadatos oficiales.

    python docs/articulo/verificar_referencias.py doi       # verifica la lista de DOI y escribe referencias_verificadas.json
    python docs/articulo/verificar_referencias.py buscar "consulta"   # busqueda bibliografica en Crossref (exploracion)

Solo se aceptan referencias cuyo DOI resuelve en Crossref; titulo, autores, anio, revista, volumen y paginas se toman
de la respuesta (no se escriben a mano).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path(__file__).with_name("referencias_verificadas.json")
API = "https://api.crossref.org/works"
HDR = {"User-Agent": "SATO-referencias/1.0 (verificacion academica)"}

DOIS = [
    "10.1061/(ASCE)CO.1943-7862.0001736",
    "10.1016/j.mlwa.2021.100166",
    "10.1016/j.ijproman.2005.11.010",
    "10.1016/j.ijproman.2006.11.007",
    "10.1002/pmj.21409",
    "10.1080/15623599.2020.1768326",
    "10.3390/su12041514",
    "10.1108/IJMPB-09-2018-0178",
    "10.1016/j.ijforecast.2020.06.006",
    "10.1093/jleo/ewaa004",
    "10.1017/S0007123417000461",
    "10.1257/aer.104.4.1288",
    "10.1145/2382577.2382579",
    "10.1371/journal.pone.0118432",
    "10.1038/s42256-019-0138-9",
    "10.18653/v1/D19-1410",
    "10.18653/v1/2020.emnlp-main.365",
    "10.1016/j.autcon.2015.11.001",
    "10.1016/j.autcon.2018.12.016",
    "10.1145/2939672.2939785",
    "10.1023/A:1010933404324",
    "10.1016/S0169-2070(00)00065-0",
    "10.1016/j.ins.2011.12.028",
    "10.1214/aos/1176344552",
    "10.1080/01621459.1969.10501049",
    "10.2307/25148625",
    "10.2753/MIS0742-1222240302",
    "10.1145/1102351.1102430",
    "10.1038/s42256-019-0048-x",
    "10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2",
    "10.1016/S0263-7863(00)00021-1",
    "10.1007/978-3-642-31164-2",
    "10.3390/en12101956",
    "10.3389/fbuil.2026.1815172",
    "10.3390/en17010182",
    "10.1080/15623599.2026.2664477",
    "10.1061/9780784486986.002",
]


def get(doi: str) -> dict | None:
    for _ in range(3):
        try:
            r = httpx.get(f"{API}/{doi}", headers=HDR, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()["message"]
        except httpx.HTTPError:
            time.sleep(2)
    return None


def resumen(m: dict) -> dict:
    autores = [f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "") for a in m.get("author", [])]
    fecha = (m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts", [[None]])[0]
    gf = [[a.get("given", ""), a.get("family", a.get("name", ""))] for a in m.get("author", [])]
    return {"doi": m["DOI"], "tipo": m.get("type"), "titulo": ((m.get("title") or [""])[0] + (": " + m["subtitle"][0] if m.get("subtitle") else "")), "autores": autores, "autores_gf": gf, "anio": fecha[0],
            "revista": (m.get("container-title") or [""])[0], "volumen": m.get("volume"), "numero": m.get("issue"),
            "paginas": m.get("page") or m.get("article-number"), "editorial": m.get("publisher"), "evento": (m.get("event") or {}).get("name")}


def verificar() -> None:
    res, fallos = [], []
    for d in DOIS:
        m = get(d)
        if m is None:
            fallos.append(d)
            print("NO RESUELVE", d)
            continue
        r = resumen(m)
        res.append(r)
        print(f"OK {r['anio']} | {r['titulo'][:90]} | {', '.join(r['autores'][:3])} | {r['revista'][:60]}")
    OUT.write_text(json.dumps({"verificado_en": time.strftime("%Y-%m-%d"), "fuente": API, "referencias": res, "no_resueltos": fallos},
                              ensure_ascii=False, indent=1), encoding="utf-8")


def buscar(q: str, n: int = 15) -> None:
    r = httpx.get(API, params={"query.bibliographic": q, "rows": n, "select": "DOI,title,author,issued,container-title,type,is-referenced-by-count"},
                  headers=HDR, timeout=60).json()
    for m in r["message"]["items"]:
        au = ", ".join(a.get("family", "") for a in m.get("author", [])[:3])
        y = (m.get("issued") or {}).get("date-parts", [[None]])[0][0]
        print(f"{y} | {m['DOI']} | {(m.get('title') or [''])[0][:110]} | {au} | {(m.get('container-title') or [''])[0][:50]} | citas={m.get('is-referenced-by-count')}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "doi":
        verificar()
    else:
        buscar(sys.argv[2])
