"""Pruebas de integracion de los servicios en segundo plano: resumen semanal por correo y avisos de operacion."""

from __future__ import annotations

import email
import email.policy
import os
import uuid

from tests.conftest import requiere_bd

pytestmark = requiere_bd


def test_resumen_semanal_para_suscriptor_confirmado(bandeja, monkeypatch):
    from sato.api import db
    from sato.services import digest

    monkeypatch.setenv("DATABASE_URL", os.environ["SATO_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
    email_sus = f"digest-{uuid.uuid4().hex[:8]}@sato.test"
    token = uuid.uuid4().hex
    s = db.execute("""insert into suscripcion (email, departamento, token, confirmada, activa) values (:e, 'AREQUIPA', :t, true, true)
                      returning id""", e=email_sus, t=token)
    try:
        # el digest recorre todas las suscripciones confirmadas: se aislan las de esta prueba desactivando temporalmente las demas
        otras = [r["id"] for r in db.rows("select id from suscripcion where confirmada and activa and id <> :i", i=s["id"])]
        if otras:
            db.execute("update suscripcion set activa = false where id = any(:ids)", ids=otras)
        try:
            assert digest.run("https://sato.ejemplo.pe") == 1
        finally:
            if otras:
                db.execute("update suscripcion set activa = true where id = any(:ids)", ids=otras)
        correos = list(bandeja.glob("*.eml"))
        assert len(correos) == 1
        msg = email.message_from_bytes(correos[0].read_bytes(), policy=email.policy.default)
        texto = msg.get_content()
        assert msg["To"] == email_sus
        assert f"https://sato.ejemplo.pe/api/v1/suscripciones/baja?token={token}" in texto
        assert "https://sato.ejemplo.pe/obras/" in texto or "https://sato.ejemplo.pe/cartera/" in texto
        envio = db.one("select modo, obras, destino from envio_correo where suscripcion_id = :i", i=s["id"])
        assert envio["modo"] == "archivo" and envio["obras"] > 0 and envio["destino"] == email_sus
    finally:
        db.execute("delete from suscripcion where id = :i", i=s["id"])  # envio_correo se elimina en cascada


def test_avisos_de_operacion_por_correo(bandeja, monkeypatch):
    from sato import cron_runner

    monkeypatch.setenv("SATO_ALERTAS_EMAIL", "ops1@sato.test, ops2@sato.test")
    cron_runner.notificar("sincronizacion rechazada", "detalle de prueba")
    assert len(list(bandeja.glob("*.eml"))) == 2
    monkeypatch.setenv("SATO_ALERTAS_EMAIL", "no-es-correo")
    cron_runner.notificar("x", "y")  # un destinatario invalido se registra y no detiene el worker
    assert len(list(bandeja.glob("*.eml"))) == 2
