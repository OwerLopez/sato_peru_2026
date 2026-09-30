"""Pruebas del despliegue real (nginx -> API): controles que solo existen en el proxy y no en la API aislada.

    SATO_E2E_URL=http://localhost:8080 pytest tests/e2e/test_despliegue.py
"""

from __future__ import annotations

import os
import socket
import urllib.request
import uuid

import pytest

httpx = pytest.importorskip("httpx")
URL = os.environ.get("SATO_E2E_URL", "http://localhost:8080").rstrip("/")


def _arriba() -> bool:
    try:
        return urllib.request.urlopen(f"{URL}/api/ready", timeout=5).status == 200
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _arriba(), reason=f"la plataforma no responde en {URL}")


def _limpiar_auditoria(prefijo: str) -> None:
    if os.environ.get("SATO_DATABASE_URL"):
        from sato.api import db

        db.execute("delete from auditoria where detalle->>'email' like :p", p=prefijo + "%")


def test_ip_falsificada_no_evita_el_limite_de_ingreso():
    """Cada intento declara otra IP en X-Forwarded-For: nginx debe seguir limitando por la IP real de la conexion."""
    prefijo = f"xff-{uuid.uuid4().hex[:6]}"
    codigos = []
    with httpx.Client(base_url=URL, timeout=20) as c:
        for i in range(20):
            r = c.post("/api/v1/auth/login", json={"email": f"{prefijo}-{i}@sato.test", "password": "x" * 12},
                       headers={"X-Forwarded-For": f"203.0.113.{i + 1}"})
            codigos.append(r.status_code)
            if r.status_code == 429:
                break
    _limpiar_auditoria(prefijo)
    assert 429 in codigos, codigos


def test_cabeceras_de_seguridad_en_estaticos_y_spa():
    with httpx.Client(base_url=URL, timeout=20) as c:
        html = c.get("/obras")
        assert html.status_code == 200 and "text/html" in html.headers["content-type"]
        csp = html.headers["content-security-policy"]
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        js = next(x for x in html.text.split('"') if x.startswith("/assets/") and x.endswith(".js"))
        a = c.get(js)
        assert a.status_code == 200 and a.headers["x-content-type-options"] == "nosniff" and "immutable" in a.headers["cache-control"]
        assert "server" not in a.headers or "/" not in a.headers["server"]  # sin version de nginx


def test_api_y_base_no_expuestas_fuera_del_equipo():
    # la API solo es alcanzable a traves de nginx; PostgreSQL solo escucha en 127.0.0.1
    s = socket.socket()
    s.settimeout(2)
    try:
        assert s.connect_ex(("127.0.0.1", 8000)) != 0, "la API publica el puerto 8000"
    finally:
        s.close()


def test_metodos_no_permitidos_y_cuerpo_grande():
    with httpx.Client(base_url=URL, timeout=20) as c:
        assert c.delete("/api/v1/obras").status_code in (404, 405)
        grande = {"email": "a@b.pe", "password": "x" * (2 * 1024 * 1024)}
        assert c.post("/api/v1/auth/login", json=grande).status_code in (413, 422, 429)
