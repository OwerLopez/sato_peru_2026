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


def test_radar_solo_obras_activas(client):
    r = client.get("/api/v1/radar/cuaderno", params={"limite": 20}).json()
    assert r["horizonte_dias"] == 60 and r["items"]
    assert all(0 <= x["score"] <= 1 and x["fecha_corte"] == r["fecha_corte"] for x in r["items"])
    scores = [x["score"] for x in r["items"]]
    assert scores == sorted(scores, reverse=True)
    c = client.get("/api/v1/radar/cartera", params={"limite": 20}).json()["items"]
    assert c and all(x["nivel"] in ("ALTO", "MEDIO", "BAJO") for x in c)


def test_resumen_por_ambito(client):
    nac = client.get("/api/v1/resumen").json()
    aqp = client.get("/api/v1/resumen", params={"departamento": "AREQUIPA"}).json()
    assert nac["cartera"]["activas"] >= aqp["cartera"]["activas"] > 0
    assert nac["cuaderno"]["activas"] >= aqp["cuaderno"]["activas"]
    assert nac["cuaderno"]["alto"] <= nac["cuaderno"]["activas"]


def test_ambitos_y_comparador(client):
    amb = client.get("/api/v1/ambitos").json()
    assert any(a["departamento"] == "AREQUIPA" for a in amb) and len(amb) >= 20
    for por in ("departamento", "sector"):
        c = client.get("/api/v1/comparador", params={"por": por}).json()
        assert c["cartera"] and all(0 <= (x["tasa_retraso_historica"] or 0) <= 1 for x in c["cartera"])
    assert client.get("/api/v1/comparador", params={"por": "x"}).status_code == 422


def test_cartera_listado_y_detalle(client):
    j = client.get("/api/v1/cartera", params={"estado": "ACTIVA", "departamento": "AREQUIPA", "tamanio": 3}).json()
    assert j["total"] > 0 and all(o["departamento"] == "AREQUIPA" and o["estado_operativo"] == "ACTIVA" for o in j["items"])
    d = client.get(f"/api/v1/cartera/{j['items'][0]['codigo_infobras']}")
    assert d.status_code == 200
    assert client.get("/api/v1/cartera/000000000000").status_code == 404


def test_informe_pdf_y_simulacion(client):
    items = client.get("/api/v1/radar/cuaderno", params={"limite": 20}).json()["items"]
    o = items[0]
    r = client.get(f"/api/v1/obras/{o['cuaderno_id']}/informe-pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    # el simulador solo reporta escenarios aplicables (la senal existe y su valor cambia)
    con = [(x, client.get(f"/api/v1/predicciones/{x['prediccion_id']}/simulacion").json()) for x in items]
    con = [(x, s) for x, s in con if s]
    assert con
    for x, s in con:
        assert all(0 <= e["score_escenario"] <= 1 and abs(e["score_base"] - x["score"]) < 1e-6 for e in s)


def test_sincronizacion_y_suscripcion(client):
    s = client.get("/api/v1/sistema/sincronizacion").json()
    assert s["proxima_sincronizacion"] and s["corte"]
    assert client.post("/api/v1/suscripciones", json={"email": "no-es-correo"}).status_code == 422
    assert "invalido" in client.get("/api/v1/suscripciones/confirmar", params={"token": "x" * 30}).text
