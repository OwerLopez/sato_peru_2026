"""Pruebas de seguridad de caja negra contra el prototipo desplegado (Docker, nginx + API).

    python docs/articulo/evaluacion/pruebas_seguridad.py [http://localhost:8080]
Salida: docs/articulo/evaluacion/seguridad_resultados.json (cada caso con resultado esperado, observado y veredicto).
Casos basados en categorias OWASP Top 10 (2021) aplicables a una API de consulta: inyeccion, control de acceso, configuracion
de seguridad (cabeceras), validacion de entrada, limitacion de tasa y exposicion de informacion.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
OUT = Path(__file__).with_name("seguridad_resultados.json")
c = httpx.Client(base_url=BASE, timeout=30)
casos = []


def caso(categoria, nombre, esperado, fn):
    try:
        observado, ok = fn()
    except Exception as e:  # noqa: BLE001
        observado, ok = f"excepcion: {type(e).__name__}: {e}", False
    casos.append({"categoria": categoria, "caso": nombre, "esperado": esperado, "observado": observado, "aprobado": bool(ok)})
    print(("OK   " if ok else "FALLA"), categoria, "|", nombre, "|", observado)


def cabeceras():
    r = c.get("/api/v1/obras?tamanio=1")
    req = ["content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy"]
    faltan = [h for h in req if h not in r.headers]
    return f"presentes: {[h for h in req if h in r.headers]}; faltan: {faltan}", not faltan


def sqli():
    payloads = ["' or '1'='1", "'; drop table sato.obra; --", "1 union select password_hash from sato.usuario--"]
    total = c.get("/api/v1/obras?tamanio=1").json()["total"]
    res = [c.get("/api/v1/obras", params={"q": p}).status_code for p in payloads]
    despues = c.get("/api/v1/obras?tamanio=1").json()["total"]
    return f"codigos {res}; total obras antes {total} / despues {despues}", all(s == 200 for s in res) and total == despues


def sin_token():
    r = c.post(f"/api/v1/alertas/{uuid.uuid4()}/2026-08-31/revisiones", json={"decision": "CONFIRMADA"})
    a = c.get("/api/v1/admin/auditoria")
    return f"revision sin token {r.status_code}; auditoria sin token {a.status_code}", r.status_code == 401 and a.status_code == 401


def token_falso():
    h = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInJvbCI6ImFkbWluIn0.firma-invalida"}
    a = c.get("/api/v1/admin/auditoria", headers=h)
    return f"auditoria con JWT falsificado {a.status_code}", a.status_code == 401


def login_invalido():
    r = c.post("/api/v1/auth/login", json={"email": "noexiste@example.com", "password": "x" * 12})
    return f"login con credenciales invalidas {r.status_code}", r.status_code in (400, 401)


def validacion():
    s = [c.get("/api/v1/obras", params={"tamanio": 1000}).status_code, c.get("/api/v1/obras/no-es-uuid").status_code,
         c.get("/api/v1/comparador", params={"por": "x"}).status_code, c.get("/api/v1/obras", params={"q": "a" * 500}).status_code,
         c.post("/api/v1/suscripciones", json={"email": "no-es-correo"}).status_code]
    return f"codigos {s}", all(x == 422 for x in s)


def errores_sin_traza():
    r = c.get(f"/api/v1/obras/{uuid.uuid4()}")
    t = r.text.lower()
    return f"404 cuerpo={r.text[:80]}", r.status_code == 404 and "traceback" not in t and "sqlalchemy" not in t and "psycopg" not in t


def xss_reflejado():
    p = "<script>alert(1)</script>"
    r = c.get("/api/v1/suscripciones/confirmar", params={"token": p})
    return f"status {r.status_code}; payload reflejado={p in r.text}", p not in r.text


def limite_tasa():
    codigos = []
    t0 = time.time()
    for _ in range(200):
        codigos.append(c.get("/api/v1/ambitos").status_code)
        if codigos[-1] == 429:
            break
    return f"primer 429 tras {len(codigos)} solicitudes en {time.time() - t0:.1f} s", 429 in codigos


def metodos():
    r = c.delete("/api/v1/obras")
    return f"DELETE /obras -> {r.status_code}", r.status_code in (404, 405)


caso("A05 Configuracion de seguridad", "Cabeceras de seguridad HTTP", "CSP, nosniff, X-Frame-Options, Referrer-Policy", cabeceras)
caso("A03 Inyeccion", "Inyeccion SQL en busqueda de texto", "200 sin efecto sobre los datos", sqli)
caso("A03 Inyeccion", "XSS reflejado en pagina HTML de confirmacion", "payload no reflejado", xss_reflejado)
caso("A01 Control de acceso", "Acciones protegidas sin token", "401", sin_token)
caso("A07 Autenticacion", "JWT con firma invalida", "401", token_falso)
caso("A07 Autenticacion", "Credenciales invalidas", "400/401", login_invalido)
caso("A04 Diseno inseguro", "Validacion de entrada (tamano, UUID, enumeraciones, longitud, correo)", "422", validacion)
caso("A05 Configuracion de seguridad", "Errores sin trazas internas", "404 sin traceback", errores_sin_traza)
caso("A05 Configuracion de seguridad", "Metodos HTTP no expuestos", "404/405", metodos)
caso("A04 Diseno inseguro", "Limitacion de tasa por IP", "429 al exceder el limite", limite_tasa)

OUT.write_text(json.dumps({"base": BASE, "fecha": time.strftime("%Y-%m-%d %H:%M"), "aprobados": sum(x["aprobado"] for x in casos),
                           "total": len(casos), "casos": casos}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{sum(x['aprobado'] for x in casos)}/{len(casos)} casos aprobados")
