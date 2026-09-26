"""Staging de los datasets abiertos de OECE (ex OSCE).

Los CSV publicados por OECE en su wiki de datos abiertos:
  * estan codificados en cp1252 (no UTF-8),
  * usan '|' como separador SIN comillas,
  * usan CRLF como fin de registro,
  * usan coma decimal ("97,91").

Un porcentaje muy pequeno de registros contiene '|' dentro de campos de texto
libre, lo que desplaza las columnas. Se reparan anclando las columnas fijas del
inicio y del final del registro y asignando el excedente al campo de texto
libre designado. Cada registro conserva `parse_status` para auditoria:
  ok            -> numero de campos exacto
  repaired      -> se absorbieron separadores extra en el campo libre y las
                   columnas ancla validan con su patron esperado
  rejected      -> no fue posible reparar con garantias (se descarta y se
                   reporta en el log de calidad)
"""

from __future__ import annotations

import csv
import glob
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sato.config import RAW, STAGING

log = logging.getLogger(__name__)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DATE8_RE = re.compile(r"^\d{8}$")
UBIGEO_RE = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class Spec:
    name: str
    pattern: str
    free_field: str  # campo que absorbe separadores excedentes
    anchors: dict  # campo -> regex que debe validar tras la reparacion


SPECS = {
    "asientos": Spec(
        name="asientos",
        pattern="cod-asientos*.csv",
        free_field="DESCRIPCION_DEL_ASIENTO",
        anchors={
            "ID_CUADERNO": UUID_RE,
            "FECHA_REGISTRO_ASIENTO": DATE8_RE,
            "ESTADO_ASIENTO": re.compile(r"^[A-Z_ ]*$"),
        },
    ),
    "cuadernos": Spec(
        name="cuadernos",
        pattern="cod-cuadernos*.csv",
        free_field="DENOMINACION_DE_LA_OBRA",
        anchors={
            "NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA": UUID_RE,
            "UBIGEO": re.compile(r"^\d{6}$|^$"),
        },
    ),
    "valorizaciones": Spec(
        name="valorizaciones",
        pattern="valorizaciones20*.csv",
        free_field="MOTIVO_DE_OBSERVACION",
        anchors={"FECHA_DE_REGISTRO": DATE8_RE},
    ),
}


def _split_quoted(line: str) -> list[str]:
    return next(csv.reader([line], delimiter="|", quotechar='"', doublequote=True))


def _split_record(parts: list[str], header: list[str], spec: Spec) -> tuple[list[str] | None, str]:
    n = len(header)
    if len(parts) == n:
        return parts, "ok"
    if len(parts) < n:
        return None, "rejected"
    k = len(parts) - n
    i = header.index(spec.free_field)
    fixed = parts[:i] + ["|".join(parts[i : i + 1 + k])] + parts[i + 1 + k :]
    rec = dict(zip(header, fixed, strict=True))
    for col, rx in spec.anchors.items():
        if not rx.match(rec.get(col, "")):
            return None, "rejected"
    return fixed, "repaired"


def stage(kind: str, raw_dir: Path = RAW / "oece", out_dir: Path = STAGING) -> dict:
    """Convierte todos los archivos de un tipo a un unico Parquet (todo como texto)."""
    spec = SPECS[kind]
    files = sorted(glob.glob(str(raw_dir / spec.pattern)))
    if not files:
        raise FileNotFoundError(f"No hay archivos {spec.pattern} en {raw_dir}")
    out = out_dir / f"oece_{kind}.parquet"
    writer = None
    stats: dict = {"files": {}, "totals": {"ok": 0, "repaired": 0, "rejected": 0}}
    schema = None
    for f in files:
        data = Path(f).read_bytes().decode("cp1252", errors="strict")
        recs = data.split("\r\n")
        # OECE publica la mayoria de meses sin comillas, pero algunos (p.ej.
        # 2024-11) con todos los campos entre comillas dobles y "" como escape.
        quoted = recs[0].startswith('"')
        split = _split_quoted if quoted else (lambda s: s.split("|"))
        header = split(recs[0].lstrip("﻿"))
        if schema is None:
            schema = pa.schema([(h, pa.string()) for h in header] + [("src_file", pa.string()), ("parse_status", pa.string())])
            writer = pq.ParquetWriter(out, schema, compression="zstd")
        elif [s.name for s in schema][: len(header)] != header:
            raise ValueError(f"Cabecera distinta en {f}: {header}")
        cols: dict[str, list] = {h: [] for h in header}
        cols["src_file"] = []
        cols["parse_status"] = []
        fs = {"ok": 0, "repaired": 0, "rejected": 0}
        for r in recs[1:]:
            if not r:
                continue
            parts, status = _split_record(split(r), header, spec)
            fs[status] += 1
            if parts is None:
                continue
            for h, v in zip(header, parts, strict=True):
                cols[h].append(v)
            cols["src_file"].append(Path(f).name)
            cols["parse_status"].append(status)
        writer.write_table(pa.table(cols, schema=schema))
        stats["files"][Path(f).name] = fs
        for k2, v in fs.items():
            stats["totals"][k2] += v
        log.info("%s %s", Path(f).name, fs)
    writer.close()
    (out_dir / f"oece_{kind}.quality.json").write_text(json.dumps(stats, indent=1))
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for k in ("cuadernos", "valorizaciones", "asientos"):
        print(k, stage(k)["totals"])
