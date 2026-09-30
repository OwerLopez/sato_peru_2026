"""Pruebas de seguridad (caja negra sobre la API real y caja blanca de sus controles).

Cubren autenticacion y sesiones (JWT), autorizacion por rol y por recurso, limite de intentos de ingreso,
enumeracion de cuentas y suscriptores, inyeccion (SQL, cabeceras, Host), validacion de entradas, cabeceras de
seguridad y cache, CORS y fuga de informacion en errores.
"""

from __future__ import annotations

import datetime as dt
import statistics
import time
import uuid

import jwt
import pytest
from sqlalchemy.exc import OperationalError

from tests.conftest import requiere_bd, token_de

pytestmark = requiere_bd


def _db():
    from sato.api import db

    return db


def _secreto():
    from sato.api.settings import get_settings

    return get_settings().jwt_secret


def _token(payload: dict, secreto: str | None = None, alg: str = "HS256") -> dict:
    return {"Authorization": f"Bearer {jwt.encode(payload, secreto or _secreto(), algorithm=alg)}"}


# ---------------------------------------------------------------- sesiones (JWT)


def test_token_alterado_expirado_o_de_otro_emisor(api_client, crear_usuario):
    u = crear_usuario()
    ahora = dt.datetime.now(dt.UTC)
    base = {"sub": str(u["id"]), "rol": "analista", "iss": "sato-api", "iat": ahora, "exp": ahora + dt.timedelta(minutes=5)}
    assert api_client.get("/api/v1/auth/me", headers=_token(base)).status_code == 200
    casos = {
        "firma de otra clave": _token(base, secreto="x" * 48),
        "expirado": _token({**base, "iat": ahora - dt.timedelta(hours=2), "exp": ahora - dt.timedelta(hours=1)}),
        "otro emisor": _token({**base, "iss": "otro"}),
        "sin exp": _token({k: v for k, v in base.items() if k != "exp"}),
        "sub no numerico": _token({**base, "sub": "admin"}),
        "algoritmo none": {"Authorization": "Bearer " + jwt.encode(base, key=None, algorithm="none")},
        "basura": {"Authorization": "Bearer no.es.un.token"},
    }
    for nombre, h in casos.items():
        r = api_client.get("/api/v1/auth/me", headers=h)
        assert r.status_code == 401, nombre
        assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_rol_escalado_en_el_token_no_otorga_permisos(api_client, crear_usuario):
    # el rol efectivo es el de la base: un token firmado con rol admin para un analista no abre rutas de administracion
    u = crear_usuario("analista")
    ahora = dt.datetime.now(dt.UTC)
    h = _token({"sub": str(u["id"]), "rol": "admin", "iss": "sato-api", "iat": ahora, "exp": ahora + dt.timedelta(minutes=5)})
    assert api_client.get("/api/v1/admin/auditoria", headers=h).status_code == 403


def test_usuario_desactivado_pierde_acceso(api_client, crear_usuario):
    u = crear_usuario()
    h = token_de(api_client, u)
    _db().execute("update usuario set activo = false where id = :u", u=u["id"])
    assert api_client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_me_no_expone_el_hash(api_client, crear_usuario):
    j = api_client.get("/api/v1/auth/me", headers=token_de(api_client, crear_usuario())).json()
    assert set(j) == {"id", "email", "nombre", "rol"}


# ---------------------------------------------------------------- autorizacion por rol y recurso


def test_rutas_de_administracion_solo_para_admin(api_client, crear_usuario):
    analista = token_de(api_client, crear_usuario("analista"))
    admin = token_de(api_client, crear_usuario("admin"))
    for ruta in ("/api/v1/admin/auditoria", "/api/v1/admin/sincronizaciones"):
        assert api_client.get(ruta).status_code == 401
        assert api_client.get(ruta, headers=analista).status_code == 403
        assert api_client.get(ruta, headers=admin).status_code == 200


def test_revision_sobre_obra_sin_prediccion_es_404(api_client, crear_usuario):
    h = token_de(api_client, crear_usuario())
    r = api_client.post(f"/api/v1/alertas/{uuid.uuid4()}/2026-08-31/revisiones", headers=h, json={"decision": "CONFIRMADA"})
    assert r.status_code == 404


def test_revision_valida_decision_y_longitud(api_client, crear_usuario):
    h = token_de(api_client, crear_usuario())
    url = f"/api/v1/alertas/{uuid.uuid4()}/2026-08-31/revisiones"
    assert api_client.post(url, headers=h, json={"decision": "BORRAR"}).status_code == 422
    assert api_client.post(url, headers=h, json={"decision": "CONFIRMADA", "comentario": "x" * 2001}).status_code == 422


# ---------------------------------------------------------------- ingreso: fuerza bruta y enumeracion


def test_bloqueo_tras_intentos_fallidos(api_client, crear_usuario):
    from sato.api.settings import get_settings

    u = crear_usuario()
    for _ in range(get_settings().login_max_fallos):
        assert api_client.post("/api/v1/auth/login", json={"email": u["email"], "password": "incorrecta"}).status_code == 401
    r = api_client.post("/api/v1/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0  # bloqueado aun con la contrasena correcta
    _db().execute("delete from auditoria where lower(detalle->>'email') = lower(:e)", e=u["email"])
    assert api_client.post("/api/v1/auth/login", json={"email": u["email"], "password": u["password"]}).status_code == 200


def test_respuesta_de_ingreso_no_revela_si_la_cuenta_existe(api_client, crear_usuario):
    u = crear_usuario()
    inexistente = f"nadie-{uuid.uuid4().hex[:8]}@sato.test"
    a = api_client.post("/api/v1/auth/login", json={"email": u["email"], "password": "mala"})
    b = api_client.post("/api/v1/auth/login", json={"email": inexistente, "password": "mala"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    # tiempo: ambos casos verifican un hash bcrypt (sin atajo para cuentas inexistentes)
    t_ex, t_no = [], []
    for _ in range(3):
        t0 = time.perf_counter()
        api_client.post("/api/v1/auth/login", json={"email": u["email"] + "x", "password": "mala"})
        t_no.append(time.perf_counter() - t0)
        _db().execute("delete from auditoria where lower(detalle->>'email') like 'prueba-%' or lower(detalle->>'email') like 'nadie-%'")
        t0 = time.perf_counter()
        api_client.post("/api/v1/auth/login", json={"email": u["email"], "password": "mala"})
        t_ex.append(time.perf_counter() - t0)
    assert statistics.median(t_no) > 0.3 * statistics.median(t_ex)
    _db().execute("delete from auditoria where lower(detalle->>'email') like :e", e=inexistente)


# ---------------------------------------------------------------- suscripciones


def _suscribir(client, email, **kw):
    return client.post("/api/v1/suscripciones", json={"email": email, **kw})


def test_suscripcion_no_revela_suscriptores_y_no_reenvia(api_client, bandeja, limpiar_suscripciones):
    email = f"sus-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(email)
    r1 = _suscribir(api_client, email)
    assert r1.status_code == 202 and len(list(bandeja.glob("*.eml"))) == 1
    _db().execute("update suscripcion set confirmada = true where email = :e", e=email)
    r2 = _suscribir(api_client, email)
    otro = f"sus-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(otro)
    r3 = _suscribir(api_client, otro)
    assert r1.json() == r2.json() == r3.json()  # misma respuesta para nuevo, confirmado y otro correo
    assert len(list(bandeja.glob("*.eml"))) == 2  # al confirmado no se le reenvia nada
    assert "id" not in r1.json()


def test_suscripcion_todo_el_peru_no_se_duplica(api_client, bandeja, limpiar_suscripciones):
    email = f"sus-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(email)
    for _ in range(3):
        assert _suscribir(api_client, email).status_code == 202
    assert _db().one("select count(*) n from suscripcion where email = :e", e=email)["n"] == 1


def test_suscripcion_valida_el_ambito_contra_los_datos(api_client, bandeja):
    assert _suscribir(api_client, "a@sato.test", departamento="ATLANTIDA").status_code == 422
    assert _suscribir(api_client, "a@sato.test", provincia="AREQUIPA").status_code == 422  # provincia sin departamento
    assert _suscribir(api_client, "a@sato.test", departamento="AREQUIPA", provincia="CUSCO").status_code == 422


def test_enlace_de_confirmacion_vence_y_la_baja_exige_reconfirmar(api_client, bandeja, limpiar_suscripciones):
    email = f"sus-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(email)
    _suscribir(api_client, email, departamento="AREQUIPA")
    tok = _db().one("select token from suscripcion where email = :e", e=email)["token"]
    _db().execute("update suscripcion set token_creado_en = now() - interval '8 days' where email = :e", e=email)
    assert "vencido" in api_client.get("/api/v1/suscripciones/confirmar", params={"token": tok}).text
    _db().execute("update suscripcion set token_creado_en = now() where email = :e", e=email)
    assert "confirmada" in api_client.get("/api/v1/suscripciones/confirmar", params={"token": tok}).text
    assert "cancelada" in api_client.get("/api/v1/suscripciones/baja", params={"token": tok}).text
    _suscribir(api_client, email, departamento="AREQUIPA")  # reactivar exige confirmar de nuevo
    s = _db().one("select activa, confirmada from suscripcion where email = :e", e=email)
    assert s["activa"] and not s["confirmada"]


def test_enlace_del_correo_no_usa_la_cabecera_host(api_client, bandeja, limpiar_suscripciones):
    from sato.api.settings import get_settings

    email = f"sus-{uuid.uuid4().hex[:8]}@sato.test"
    limpiar_suscripciones.append(email)
    api_client.post("/api/v1/suscripciones", json={"email": email}, headers={"Host": "atacante.example"})
    contenido = "".join(f.read_text(encoding="utf-8", errors="ignore") for f in bandeja.glob("*.eml"))
    assert "atacante.example" not in contenido and get_settings().base_url.rstrip("/") in contenido


# ---------------------------------------------------------------- inyeccion y validacion de entradas


@pytest.mark.parametrize("params", [
    {"departamento": "' or 1=1 --"}, {"sector": "x'); drop table sato.obra; --"}, {"q": "1' union select password_hash from sato.usuario --"},
    {"provincia": "%' and pg_sleep(5) --"},
])
def test_inyeccion_sql_en_filtros(api_client, params):
    t0 = time.perf_counter()
    r = api_client.get("/api/v1/obras", params={**params, "tamanio": 5})
    assert r.status_code == 200 and r.json()["total"] == 0 and time.perf_counter() - t0 < 4
    assert "password" not in r.text


@pytest.mark.parametrize("ruta", [
    "/api/v1/obras?orden=score;drop", "/api/v1/obras?pagina=0", "/api/v1/obras?tamanio=101", "/api/v1/cartera?estado=TODAS",
    "/api/v1/obras?q=" + "a" * 121, "/api/v1/cartera/" + "9" * 21, "/api/v1/obras/../../etc/passwd", "/api/v1/comparador?por=entidad",
    "/api/v1/alertas?limite=0", "/api/v1/obras/00000000-0000-0000-0000-00000000000g",
])
def test_parametros_invalidos_se_rechazan(api_client, ruta):
    assert api_client.get(ruta).status_code in (404, 422)


def test_request_id_no_permite_inyectar_en_registros(api_client):
    assert api_client.get("/api/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"
    r = api_client.get("/api/health", headers={"X-Request-ID": "x\" rid=falso otra=cosa"})
    assert r.headers["X-Request-ID"] != "x\" rid=falso otra=cosa" and len(r.headers["X-Request-ID"]) == 16


def test_comentario_con_html_se_devuelve_como_dato(api_client, crear_usuario):
    h = token_de(api_client, crear_usuario())
    a = api_client.get("/api/v1/alertas", params={"limite": 1}).json()["items"]
    if not a:
        pytest.skip("sin alertas vigentes")
    url = f"/api/v1/alertas/{a[0]['cuaderno_id']}/{a[0]['fecha_corte']}/revisiones"
    carga = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    assert api_client.post(url, headers=h, json={"decision": "EN_SEGUIMIENTO", "comentario": carga}).status_code == 201
    r = api_client.get(url, headers=h)
    assert r.headers["content-type"].startswith("application/json") and any(x["comentario"] == carga for x in r.json())


# ---------------------------------------------------------------- cabeceras, cache, CORS y errores


def test_cabeceras_de_seguridad_y_cache(api_client, crear_usuario):
    r = api_client.get("/api/v1/obras", params={"tamanio": 1})
    for h, v in {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                 "Cross-Origin-Resource-Policy": "same-origin"}.items():
        assert r.headers[h] == v
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "public, max-age=60"
    h = token_de(api_client, crear_usuario())
    assert api_client.get("/api/v1/auth/me", headers=h).headers["Cache-Control"] == "no-store"
    assert api_client.post("/api/v1/auth/login", json={"email": "a@b.pe", "password": "x"}).headers["Cache-Control"] == "no-store"


def test_cors_solo_para_origenes_permitidos(api_client):
    from sato.api.settings import get_settings

    permitido = get_settings().cors_list[0]
    ok = api_client.get("/api/v1/ambitos", headers={"Origin": permitido})
    assert ok.headers.get("access-control-allow-origin") == permitido
    malo = api_client.get("/api/v1/ambitos", headers={"Origin": "https://atacante.example"})
    assert "access-control-allow-origin" not in malo.headers
    pre = api_client.options("/api/v1/auth/login", headers={"Origin": "https://atacante.example", "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 400


def test_base_caida_responde_503_sin_detalles_internos(api_client, monkeypatch):
    from sato.api import db

    def caida(*a, **k):
        raise OperationalError("select ...", {}, Exception("could not connect to server: password=secreta host=db"))

    monkeypatch.setattr(db, "rows", caida)
    r = api_client.get("/api/v1/obras/mapa", params={"departamento": f"X{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 503 and r.headers["Retry-After"] == "30"
    assert "secreta" not in r.text and "select" not in r.text


def test_error_no_controlado_no_expone_traza(api_client, monkeypatch):
    from sato.api import db

    monkeypatch.setattr(db, "rows", lambda *a, **k: 1 / 0)
    from fastapi.testclient import TestClient

    from sato.api.main import app

    r = TestClient(app, raise_server_exceptions=False).get("/api/v1/obras/mapa", params={"departamento": f"Y{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 500 and r.json() == {"detail": "Error interno del servidor"}


def test_informe_pdf_como_adjunto(api_client):
    o = api_client.get("/api/v1/obras", params={"solo_vigentes": True, "tamanio": 1}).json()["items"][0]
    r = api_client.get(f"/api/v1/obras/{o['cuaderno_id']}/informe-pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("attachment;") and r.content[:5] == b"%PDF-"
