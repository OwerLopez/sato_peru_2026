"""Despachador de correo.

Configuracion por variables de entorno:
  SATO_SMTP_HOST, SATO_SMTP_PORT (587), SATO_SMTP_USER, SATO_SMTP_PASSWORD, SATO_SMTP_FROM, SATO_SMTP_TLS (true)
Proveedores compatibles: cualquier servidor SMTP (incluido el relay SMTP de SendGrid: host smtp.sendgrid.net,
usuario "apikey", contrasena = API key).
Si no hay SMTP configurado, el mensaje se escribe como archivo .eml en SATO_OUTBOX (por defecto artifacts/outbox)
y se informa el modo "archivo": nunca se reporta un envio que no ocurrio.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger(__name__)
EMAIL_RX = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")


def smtp_configurado() -> bool:
    return bool(os.environ.get("SATO_SMTP_HOST"))


def enviar(destino: str, asunto: str, texto: str, html: str | None = None) -> str:
    """Envia un correo y devuelve el modo usado: 'smtp' o 'archivo'."""
    if not EMAIL_RX.match(destino):
        raise ValueError("correo invalido")
    msg = EmailMessage()
    msg["From"] = os.environ.get("SATO_SMTP_FROM", "sato@localhost")
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    if smtp_configurado():
        host, port = os.environ["SATO_SMTP_HOST"], int(os.environ.get("SATO_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=30) as s:
            if os.environ.get("SATO_SMTP_TLS", "true").lower() == "true":
                s.starttls()
            if os.environ.get("SATO_SMTP_USER"):
                s.login(os.environ["SATO_SMTP_USER"], os.environ.get("SATO_SMTP_PASSWORD", ""))
            s.send_message(msg)
        log.info("correo enviado por SMTP a %s", destino)
        return "smtp"
    outbox = Path(os.environ.get("SATO_OUTBOX", Path(__file__).resolve().parents[2] / "artifacts" / "outbox"))
    outbox.mkdir(parents=True, exist_ok=True)
    f = outbox / f"{dt.datetime.now():%Y%m%d_%H%M%S_%f}_{re.sub(r'[^A-Za-z0-9]', '_', destino)}.eml"
    f.write_bytes(bytes(msg))
    log.info("SMTP no configurado: correo guardado en %s", f)
    return "archivo"
