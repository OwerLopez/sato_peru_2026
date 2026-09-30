"""Utilidades compartidas por las pruebas.

Las pruebas marcadas con `requiere_bd` se ejecutan contra la base PostgreSQL real cargada por el pipeline
(SATO_DATABASE_URL); se omiten si no esta disponible. Nunca se insertan datos de dominio ficticios: las pruebas
solo crean usuarios, suscripciones o registros de operacion temporales y los eliminan al terminar.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

# el limite de tasa por IP se prueba en nginx (docs/articulo/evaluacion/pruebas_seguridad.py); aqui todas las solicitudes
# llegan desde el mismo cliente de pruebas y no deben agotar el limite de la API
os.environ.setdefault("SATO_RATE_LIMIT", "100000/minute")


def _servidor_disponible() -> bool:
    if not os.environ.get("SATO_DATABASE_URL"):
        return False
    try:
        import psycopg

        with psycopg.connect(os.environ["SATO_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"), connect_timeout=5):
            return True
    except Exception:  # noqa: BLE001
        return False


def _bd_cargada() -> bool:
    try:
        from sato.api import db

        return db.one("select 1 x from sato.modelo where activo limit 1") is not None
    except Exception:  # noqa: BLE001
        return False


SERVIDOR = _servidor_disponible()
BD = SERVIDOR and _bd_cargada()
# migraciones y restricciones: basta un PostgreSQL alcanzable (en CI, uno vacio)
requiere_servidor = pytest.mark.skipif(not SERVIDOR, reason="requiere un servidor PostgreSQL (SATO_DATABASE_URL)")
# consultas sobre los datos oficiales: requiere la base cargada por el pipeline
requiere_bd = pytest.mark.skipif(not BD, reason="requiere PostgreSQL cargado con los datos (SATO_DATABASE_URL)")


@pytest.fixture(scope="session")
def api_client():
    from fastapi.testclient import TestClient

    from sato.api.main import app

    return TestClient(app)


@pytest.fixture
def crear_usuario() -> Iterator:
    """Crea usuarios temporales (analista o admin) y los elimina con todo lo que registraron."""
    import bcrypt

    from sato.api import db

    creados: list[int] = []

    def _crear(rol: str = "analista", activo: bool = True) -> dict:
        email = f"prueba-{uuid.uuid4().hex[:10]}@sato.test"
        pwd = uuid.uuid4().hex
        u = db.execute("""insert into usuario (email, nombre, rol, password_hash, activo) values (:e, 'Usuario de prueba', :r, :h, :a)
                          returning id""", e=email, r=rol, h=bcrypt.hashpw(pwd.encode(), bcrypt.gensalt(4)).decode(), a=activo)
        creados.append(u["id"])
        return {"id": u["id"], "email": email, "password": pwd, "rol": rol}

    yield _crear
    for uid in creados:
        email = db.one("select email from usuario where id = :u", u=uid)["email"]
        db.execute("delete from revision_alerta where usuario_id = :u", u=uid)
        db.execute("delete from auditoria where usuario_id = :u or lower(detalle->>'email') = lower(:e)", u=uid, e=email)
        db.execute("delete from usuario where id = :u", u=uid)


def token_de(client, u: dict) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def bandeja(tmp_path, monkeypatch):
    """Bandeja de correo local aislada: sin SMTP, los mensajes quedan como .eml en un directorio temporal."""
    monkeypatch.delenv("SATO_SMTP_HOST", raising=False)
    monkeypatch.setenv("SATO_OUTBOX", str(tmp_path))
    return tmp_path


@pytest.fixture
def limpiar_suscripciones() -> Iterator[list[str]]:
    from sato.api import db

    correos: list[str] = []
    yield correos
    for e in correos:
        db.execute("delete from auditoria where recurso in (select 'suscripcion:' || id from suscripcion where email = :e)", e=e)
        db.execute("delete from suscripcion where email = :e", e=e)
