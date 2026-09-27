from __future__ import annotations

import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sato.api import db
from sato.api.security import audit

router = APIRouter(tags=["sistema"])

FUENTES = {
    "OECE - Cuaderno de obra digital (wiki de datos abiertos)": "https://osce-gob-pe.atlassian.net/wiki/rest/api/content/106889263",
    "MEF - Datos abiertos (Invierte.pe / SIAF)": "https://fs.datosabiertos.mef.gob.pe/datastorefiles/F12B_Diccionario.csv",
    "Contraloria - INFOBRAS": "https://infobras.contraloria.gob.pe/InfobrasWeb/DataSets",
    "OECE - CONOSCE": "https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/Diccionario.xlsx",
}
_cache: dict = {"t": 0.0, "v": None}


def _check(nombre_url):
    nombre, url = nombre_url
    t0 = time.perf_counter()
    try:
        r = httpx.head(url, timeout=8, follow_redirects=True, headers={"User-Agent": "SATO-monitor"})
        ok = r.status_code < 400
        return {"fuente": nombre, "estado": "EN_LINEA" if ok else f"HTTP {r.status_code}", "ms": round(1000 * (time.perf_counter() - t0))}
    except Exception as e:  # noqa: BLE001
        return {"fuente": nombre, "estado": "SIN_RESPUESTA", "detalle": type(e).__name__, "ms": round(1000 * (time.perf_counter() - t0))}


@router.get("/sistema/sincronizacion")
def sincronizacion():
    from sato.services.schedule import proxima_sync

    if time.time() - _cache["t"] > 600:  # verificacion real cada 10 minutos
        with ThreadPoolExecutor(4) as ex:
            _cache["v"] = list(ex.map(_check, FUENTES.items()))
        _cache["t"] = time.time()
    return {
        "corte": db.one("select fecha_corte, generado_en, descripcion from corte_datos order by id desc limit 1"),
        "ultima_sincronizacion": db.one("select inicio, fin, estado, corte_datos, pasos from sincronizacion order by inicio desc limit 1"),
        "proxima_sincronizacion": str(proxima_sync()),
        "fuentes": _cache["v"], "verificado_hace_s": round(time.time() - _cache["t"]),
    }


@router.get("/sistema/calidad")
def calidad():
    """Auditoria de calidad de los datos cargados (cobertura, nulos, duplicados, consistencia, relaciones y frescura)."""
    r = db.one("select valor from configuracion where clave = 'calidad_datos'")
    return r["valor"] if r else None


class SuscripcionIn(BaseModel):
    email: str = Field(..., max_length=254)
    departamento: str | None = Field(None, max_length=40)
    provincia: str | None = Field(None, max_length=60)


@router.post("/suscripciones", status_code=201)
def suscribir(body: SuscripcionIn, request: Request):
    from sato.services.mailer import EMAIL_RX, enviar

    email = body.email.strip().lower()
    if not EMAIL_RX.match(email):
        raise HTTPException(422, "Correo invalido")
    token = secrets.token_urlsafe(24)
    r = db.execute("""insert into suscripcion (email, departamento, provincia, token) values (:e, :d, :p, :t)
                      on conflict (email, departamento, provincia) do update set activa = true, token = excluded.token returning id, confirmada""",
                   e=email, d=body.departamento, p=body.provincia, t=token)
    base = os.environ.get("SATO_BASE_URL", str(request.base_url).rstrip("/"))
    ambito = " / ".join(x for x in (body.departamento, body.provincia) if x) or "Todo el Peru"
    modo = enviar(email, "SATO - Confirme su suscripcion",
                  f"Solicito recibir el resumen semanal de alertas de obras publicas ({ambito}).\n"
                  f"Confirme aqui: {base}/api/v1/suscripciones/confirmar?token={token}\nSi no lo solicito, ignore este mensaje.")
    audit(request, "SUSCRIPCION", None, f"suscripcion:{r['id']}", {"ambito": ambito, "modo_correo": modo})
    return {"id": r["id"], "estado": "confirmada" if r["confirmada"] else "pendiente_confirmacion", "modo_envio": modo,
            "mensaje": "Se envio un correo de confirmacion." if modo == "smtp" else
            "SMTP no configurado en este servidor: el correo de confirmacion quedo en la bandeja local (artifacts/outbox)."}


def _html(t):
    return HTMLResponse(f"<html><body style='font-family:sans-serif;padding:2rem'><h3>SATO</h3><p>{t}</p><a href='/'>Volver</a></body></html>")


@router.get("/suscripciones/confirmar", response_class=HTMLResponse)
def confirmar(token: str = Query(..., max_length=64)):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token) or not db.execute("update suscripcion set confirmada = true where token = :t returning id", t=token):
        return _html("Enlace invalido o expirado.")
    return _html("Suscripcion confirmada. Recibira el resumen semanal de alertas.")


@router.get("/suscripciones/baja", response_class=HTMLResponse)
def baja(token: str = Query(..., max_length=64)):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token) or not db.execute("update suscripcion set activa = false where token = :t returning id", t=token):
        return _html("Enlace invalido.")
    return _html("Suscripcion cancelada.")
