"""Descarga idempotente de todas las fuentes oficiales con registro de linaje.

    python -m sato.ingest.download [oece|mef|siaf|infobras|contraloria|seace|all]

Cada archivo descargado se registra en data/raw/manifest.jsonl con: fuente, URL,
ruta local, bytes, SHA-256, Last-Modified del servidor y fecha de descarga.
Si el archivo ya existe con el mismo tamanio remoto, no se vuelve a descargar.
Reintentos con backoff exponencial ante errores transitorios.

Nota: el certificado TLS de datosabiertos.mef.gob.pe fallo la validacion de la
libreria estandar de Python durante la investigacion (cadena expirada); se usa
`requests` con el almacen de certificados de `certifi` y, si falla, se reporta
el error (no se desactiva la verificacion TLS silenciosamente).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path

import requests

from sato.config import RAW
from sato.ingest import sources as S

log = logging.getLogger(__name__)
MANIFEST = RAW / "manifest.jsonl"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = S.USER_AGENT


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _record(source: str, url: str, path: Path, last_modified: str | None) -> None:
    rec = dict(source=source, url=url, path=path.relative_to(RAW).as_posix(), bytes=path.stat().st_size, sha256=_sha256(path),
               last_modified=last_modified, downloaded_at=dt.datetime.now(dt.UTC).isoformat())
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fetch(url: str, dest: Path, source: str, retries: int = 5, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_mod = None
    for attempt in range(retries):
        try:
            head = SESSION.head(url, allow_redirects=True, timeout=60)
            size = int(head.headers.get("Content-Length", -1))
            last_mod = head.headers.get("Last-Modified")
            if dest.exists() and not force and (size < 0 or dest.stat().st_size == size):
                log.info("sin cambios: %s", dest.name)
                return dest
            tmp = dest.with_suffix(dest.suffix + ".part")
            with SESSION.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            tmp.replace(dest)
            _record(source, url, dest, last_mod)
            log.info("descargado %s (%s bytes)", dest.name, dest.stat().st_size)
            return dest
        except requests.RequestException as e:
            wait = 2 ** attempt * 5
            log.warning("error %s en %s; reintento en %ss", e, url, wait)
            time.sleep(wait)
    raise RuntimeError(f"No se pudo descargar {url}")


def oece() -> None:
    for page, prefixes in S.OECE_PAGES.items():
        r = SESSION.get(f"{S.OECE_WIKI}/rest/api/content/{page}/child/attachment", params={"limit": 500}, timeout=60)
        r.raise_for_status()
        for att in r.json()["results"]:
            title = att["title"]
            if title.startswith(prefixes) and title.endswith(".csv"):
                fetch(S.OECE_WIKI + att["_links"]["download"], RAW / "oece" / title, "OECE")


def mef() -> None:
    for f in S.MEF_FILES:
        sub = "docs" if "Diccionario" in f else ""
        fetch(f"{S.MEF_FS}/{f}", RAW / "mef" / sub / f, "MEF")


def siaf() -> None:
    for _, f in S.SIAF_YEARS.items():
        fetch(f"{S.MEF_FS}/{f}", RAW / "mef" / "siaf" / f, "MEF-SIAF")


def infobras() -> None:
    html = SESSION.get(S.INFOBRAS_DATASETS, timeout=60).text
    name = re.search(r'data-filename="(DataSet-Obras-Publicas [0-9-]+)"', html).group(1)
    fecha = dt.datetime.strptime(name.split()[-1], "%d-%m-%Y").date().isoformat()
    url = S.INFOBRAS_DOWNLOAD.format(name=requests.utils.quote(name))
    fetch(url, RAW / "infobras" / f"DataSet-Obras-Publicas_{fecha}.xlsx", "INFOBRAS")


def contraloria() -> None:
    col = SESSION.get(S.CONTRALORIA_COLLECTION, timeout=60).text
    for rep in sorted(set(re.findall(r"informes-publicaciones/(\d+)-(?:informe|reporte)-de-obras-(?:publicas-)?paralizadas[a-z0-9-]*", col))):
        page = SESSION.get(f"https://www.gob.pe/institucion/contraloria/informes-publicaciones/{rep}", timeout=60).text
        for u in sorted(set(re.findall(r"https://cdn\.www\.gob\.pe/uploads/document/file/[^\"?]+\.(?:xlsx|XLSX|pdf|PDF)", page))):
            if "preview_" in u:
                continue
            fetch(u, RAW / "contraloria" / f"{rep}_{u.rsplit('/', 1)[-1]}", "CONTRALORIA")


def seace() -> None:
    for y in S.CONOSCE_YEARS:
        fetch(S.CONOSCE_CONTRATOS.format(y=y), RAW / "seace" / f"CONOSCE_CONTRATOS{y}_0.xlsx", "OECE-CONOSCE")


def register_existing() -> None:
    """Registra en el manifest (con SHA-256) los archivos locales ya descargados que no esten registrados.

    Sirve para congelar el corte de datos realmente usado sin volver a descargar
    (las fuentes MEF se regeneran a diario y cambiarian los resultados).
    """
    known = set()
    if MANIFEST.exists():
        known = {json.loads(line)["path"] for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()}
    oece_urls = {}
    for page in S.OECE_PAGES:
        try:
            r = SESSION.get(f"{S.OECE_WIKI}/rest/api/content/{page}/child/attachment", params={"limit": 500}, timeout=60).json()
            oece_urls.update({a["title"]: S.OECE_WIKI + a["_links"]["download"] for a in r["results"]})
        except requests.RequestException:
            pass
    rules = [
        ("oece", "OECE", lambda f: oece_urls.get(f.name, S.OECE_WIKI)),
        ("mef/siaf", "MEF-SIAF", lambda f: f"{S.MEF_FS}/{f.name}"),
        ("mef", "MEF", lambda f: f"{S.MEF_FS}/{f.name}"),
        ("infobras", "INFOBRAS", lambda f: S.INFOBRAS_DATASETS),
        ("contraloria", "CONTRALORIA", lambda f: S.CONTRALORIA_COLLECTION),
        ("seace", "OECE-CONOSCE", lambda f: S.CONOSCE_CONTRATOS.format(y=re.findall(r"\d{4}", f.name)[0]) if re.findall(r"\d{4}", f.name) else ""),
    ]
    for sub, source, url in rules:
        base = RAW / sub
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.suffix in (".part", ".log", ".html", ".txt") or f.name == "manifest.jsonl":
                continue
            rel = f.relative_to(RAW).as_posix()
            if rel in known or (sub == "mef" and "siaf" in f.parts):
                continue
            _record(source, url(f), f, None)
            known.add(rel)
            log.info("registrado %s", rel)


STEPS = dict(oece=oece, mef=mef, siaf=siaf, infobras=infobras, contraloria=contraloria, seace=seace)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which == "register":
        register_existing()
        sys.exit(0)
    for name, fn in STEPS.items():
        if which in (name, "all"):
            fn()
