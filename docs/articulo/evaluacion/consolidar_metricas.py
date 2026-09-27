"""Consolida las mediciones del prototipo (k6, seguridad, Lighthouse, pruebas, BD) en metricas_prototipo.json.

Solo lee archivos producidos por las mediciones y consulta la base de datos cargada; no escribe valores a mano.
    python docs/articulo/evaluacion/consolidar_metricas.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import psycopg

EV = Path(__file__).parent
ROOT = EV.parents[2]
out = {}

for v in (1, 20, 50):
    m = json.loads((EV / f"k6_vus{v}.json").read_text(encoding="utf-8"))["metrics"]
    d = m["http_req_duration"]
    out[f"k6_{v}"] = {"p50_ms": round(d["med"], 1), "p95_ms": round(d["p(95)"], 1), "p90_ms": round(d["p(90)"], 1), "max_ms": round(d["max"], 1),
                      "media_ms": round(d["avg"], 1), "rps": round(m["http_reqs"]["rate"], 1), "solicitudes": int(m["http_reqs"]["count"]),
                      "error_pct": round(100 * m["http_req_failed"]["value"], 3)}

seg = json.loads((EV / "seguridad_resultados.json").read_text(encoding="utf-8"))
out["seguridad"] = {"aprobados": seg["aprobados"], "total": seg["total"], "fecha": seg["fecha"]}

out["lighthouse"] = {}
for n in ("panorama", "ficha", "cartera"):
    r = json.loads((EV / f"lighthouse_{n}.json").read_text(encoding="utf-8"))
    out["lighthouse"][n] = {k: round(100 * v["score"]) for k, v in r["categories"].items()}
    out["lighthouse"][n]["lcp_s"] = round(r["audits"]["largest-contentful-paint"]["numericValue"] / 1000, 2)

py = subprocess.run([str(ROOT / ".venv/Scripts/python"), "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True, env=os.environ)
m = re.search(r"(\d+) passed", py.stdout)
f = re.search(r"(\d+) failed", py.stdout)
out["pytest"] = {"aprobadas": int(m.group(1)) if m else 0, "fallidas": int(f.group(1)) if f else 0}

log = (ROOT / "artifacts" / "load_db.log").read_text(encoding="utf-8", errors="replace")
t = re.findall(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", log, re.M)
from datetime import datetime  # noqa: E402

out["carga_bd_segundos"] = int((datetime.fromisoformat(t[-1]) - datetime.fromisoformat(t[0])).total_seconds())

dsn = os.environ["DATABASE_URL"]
with psycopg.connect(dsn) as c:
    tablas = [r[0] for r in c.execute("select table_name from information_schema.tables where table_schema='sato' and table_type='BASE TABLE' order by 1")]
    out["bd_tablas"] = len(tablas)
    out["bd_filas"] = {t: c.execute(f"select count(*) from sato.{t}").fetchone()[0] for t in tablas}
    out["bd_tamano_mb"] = round(c.execute("select pg_database_size(current_database())").fetchone()[0] / 1e6)

rutas = 0
for p in (ROOT / "sato" / "api" / "routes").glob("*.py"):
    rutas += len(re.findall(r"@router\.(get|post|put|delete|patch)\(", p.read_text(encoding="utf-8")))
out["api_endpoints"] = rutas
app = (ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
out["frontend_rutas"] = len(re.findall(r"<Route\s", app))
dist = ROOT / "web" / "dist" / "assets"
out["frontend_js_kb"] = round(sum(p.stat().st_size for p in dist.glob("*.js")) / 1024)
(EV / "metricas_prototipo.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "bd_filas"}, indent=1))
print({k: out["bd_filas"][k] for k in sorted(out["bd_filas"], key=lambda x: -out["bd_filas"][x])[:12]})
