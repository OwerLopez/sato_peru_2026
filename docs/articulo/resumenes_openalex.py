"""Recupera el resumen (abstract) de trabajos por DOI desde OpenAlex para leerlos antes de citarlos.

    python docs/articulo/resumenes_openalex.py 10.1016/j.aei.2025.104219 [...]
"""

import sys

import httpx


def abstract(inv: dict | None) -> str:
    if not inv:
        return "(sin resumen en OpenAlex)"
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for doi in sys.argv[1:]:
        r = httpx.get(f"https://api.openalex.org/works/doi:{doi}", timeout=30)
        if r.status_code != 200:
            print(doi, "NO ENCONTRADO", r.status_code)
            continue
        m = r.json()
        print(f"== {doi} | {m.get('title')} | {m.get('publication_year')} | citas={m.get('cited_by_count')}")
        print(abstract(m.get("abstract_inverted_index"))[:1500])
        print()
