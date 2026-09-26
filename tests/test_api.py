"""Pruebas de integracion de la API contra una base PostgreSQL cargada.

Requiere SATO_DATABASE_URL apuntando a una BD cargada con `python -m sato.serving.load_db`.
Se omiten si la base no esta disponible.
"""

import os
import uuid

import pytest

try:
    from fastapi.testclient import TestClient

    from sato.api import db
    from sato.api.main import app

    db.one("select 1 x from sato.modelo limit 1")
    DISPONIBLE = True
except Exception:  # noqa: BLE001
    DISPONIBLE = False

pytestmark = pytest.mark.skipif(not DISPONIBLE or not os.environ.get("SATO_DATABASE_URL"), reason="requiere PostgreSQL cargado")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_y_ready(client):
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/ready")
    assert r.status_code == 200 and r.json()["modelo"]


def test_cabeceras_de_seguridad(client):
    r = client.get("/api/v1/obras?tamanio=1")
    for h in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy", "X-Request-ID"):
        assert h in r.headers


def test_listado_y_filtros(client):
    r = client.get("/api/v1/obras", params={"provincia": "AREQUIPA", "tamanio": 5})
    assert r.status_code == 200
    j = r.json()
    assert j["total"] > 0 and all(o["provincia"] == "AREQUIPA" for o in j["items"])


def test_validacion_de_entrada(client):
    assert client.get("/api/v1/obras", params={"tamanio": 1000}).status_code == 422
    assert client.get("/api/v1/obras", params={"estado": "X"}).status_code == 422
    assert client.get("/api/v1/obras/no-es-uuid").status_code == 422


def test_inyeccion_sql_no_afecta(client):
    r = client.get("/api/v1/obras", params={"q": "'; drop table sato.obra; --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/v1/obras", params={"tamanio": 1}).json()["total"] > 0


def test_detalle_riesgo_asientos_y_explicacion(client):
    o = client.get("/api/v1/obras", params={"solo_vigentes": True, "tamanio": 1}).json()["items"][0]
    cid = o["cuaderno_id"]
    d = client.get(f"/api/v1/obras/{cid}").json()
    assert d["obra"]["cuaderno_id"] == cid
    rg = client.get(f"/api/v1/obras/{cid}/riesgo").json()
    assert rg["predicciones"] and all(0 <= p["score"] <= 1 for p in rg["predicciones"])
    a = client.get(f"/api/v1/obras/{cid}/asientos", params={"tamanio": 3}).json()
    assert a["total"] > 0
    e = client.get(f"/api/v1/predicciones/{o['prediccion_id']}").json()
    assert e["factores"] and all(f["descripcion"] for f in e["factores"])


def test_obra_inexistente(client):
    assert client.get(f"/api/v1/obras/{uuid.uuid4()}").status_code == 404


def test_revision_requiere_autenticacion(client):
    r = client.post(f"/api/v1/alertas/{uuid.uuid4()}/2026-08-31/revisiones", json={"decision": "CONFIRMADA"})
    assert r.status_code == 401


def test_flujo_login_y_revision(client):
    import bcrypt

    email = f"test-{uuid.uuid4().hex[:8]}@sato.test"
    pwd = uuid.uuid4().hex
    db.execute("insert into usuario (email, nombre, rol, password_hash) values (:e, 'Analista de prueba', 'analista', :h)",
               e=email, h=bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode())
    try:
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "incorrecta"}).status_code == 401
        tok = client.post("/api/v1/auth/login", json={"email": email, "password": pwd}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        a = client.get("/api/v1/alertas", params={"limite": 1}).json()
        if a["items"]:
            it = a["items"][0]
            r = client.post(f"/api/v1/alertas/{it['cuaderno_id']}/{it['fecha_corte']}/revisiones", headers=h,
                            json={"decision": "EN_SEGUIMIENTO", "comentario": "prueba automatizada"})
            assert r.status_code == 201
            rv = client.get(f"/api/v1/alertas/{it['cuaderno_id']}/{it['fecha_corte']}/revisiones", headers=h).json()
            assert any(x["comentario"] == "prueba automatizada" for x in rv)
        assert client.get("/api/v1/admin/auditoria", headers=h).status_code == 403
    finally:
        uid = db.one("select id from usuario where email = :e", e=email)["id"]
        db.execute("delete from revision_alerta where usuario_id = :u", u=uid)
        db.execute("delete from auditoria where usuario_id = :u", u=uid)
        db.execute("delete from usuario where id = :u", u=uid)
