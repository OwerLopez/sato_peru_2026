"""Estado operativo de la plataforma, auditoria de calidad, monitoreo del modelo y suscripciones a alertas."""

from __future__ import annotations

import datetime as dt
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sato.api import db
from sato.api.cache import cacheado
from sato.api.security import audit, require_role
from sato.api.settings import get_settings

router = APIRouter(tags=["sistema"])

FUENTES = {
    "OECE - Cuaderno de obra digital (wiki de datos abiertos)": "https://osce-gob-pe.atlassian.net/wiki/rest/api/content/106889263",
    "MEF - Datos abiertos (Invierte.pe / SIAF)": "https://fs.datosabiertos.mef.gob.pe/datastorefiles/F12B_Diccionario.csv",
    "Contraloria - INFOBRAS": "https://infobras.contraloria.gob.pe/InfobrasWeb/DataSets",
    "OECE - CONOSCE": "https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/Diccionario.xlsx",
}
_cache: dict = {"t": 0.0, "v": None}
TOKEN_RX = re.compile(r"[A-Za-z0-9_-]{16,64}")
# umbrales de operacion (dias): los datos se actualizan mensualmente y el SIAF llega con un mes de rezago
DIAS_DATOS_VIGENTES = 75
HORAS_LATIDO_WORKER = 3


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


@router.get("/sistema/monitoreo")
def monitoreo():
    """Monitoreo del modelo de alerta: deriva de variables (PSI), desempeno realizado por corte, anomalia en la proporcion
    de obras en nivel alto y cobertura mensual de la fuente. Lo genera el paso `monitor` del pipeline en cada actualizacion."""
    r = db.one("select valor from configuracion where clave = 'monitoreo_modelo'")
    return r["valor"] if r else None


@router.get("/sistema/cargas")
def cargas(limite: int = Query(12, ge=1, le=100)):
    """Historial de cargas de datos: conteos, conciliacion de registros (origen, cargados, descartados y motivo) y compuerta."""
    items = db.rows("""select id, inicio, fin, estado, conteos, conciliacion, validacion,
                              case when estado = 'RECHAZADA' then mensaje end mensaje
                       from carga_datos order by inicio desc limit :l""", l=limite)
    return {"items": items}


def _estado() -> dict:
    """Semaforo operativo calculado con el estado real de cada componente (sin valores fijos)."""
    motivos: list[dict] = []
    t0 = time.perf_counter()
    db.one("select 1 x")
    bd_ms = round(1000 * (time.perf_counter() - t0), 1)
    corte = db.one("select fecha_corte, generado_en from corte_datos order by id desc limit 1")
    modelo = db.one("select version, entrenado_hasta, horizonte_dias from modelo where activo")
    carga_ok = db.one("select id, fin from carga_datos where estado = 'OK' order by inicio desc limit 1")
    carga_ult = db.one("select id, inicio, fin, estado, validacion from carga_datos order by inicio desc limit 1")
    sync = db.one("select inicio, fin, estado from sincronizacion order by inicio desc limit 1")
    latido = db.one("select ts, detalle from servicio_latido where servicio = 'worker'")
    cal = (db.one("select valor from configuracion where clave = 'calidad_datos'") or {}).get("valor") or {}
    mon = (db.one("select valor from configuracion where clave = 'monitoreo_modelo'") or {}).get("valor") or {}
    hoy = dt.date.today()

    if not modelo:
        motivos.append({"nivel": "CRITICO", "componente": "modelo", "texto": "No hay un modelo activo: la base no tiene datos cargados."})
    dias = (hoy - corte["fecha_corte"]).days if corte else None
    if dias is not None and dias > DIAS_DATOS_VIGENTES:
        motivos.append({"nivel": "AVISO", "componente": "datos", "texto": f"Los datos tienen {dias} días desde el último corte; corresponde una actualización."})
    if carga_ult and carga_ult["estado"] in ("RECHAZADA", "ERROR") and (not carga_ok or carga_ult["id"] > carga_ok["id"]):
        motivos.append({"nivel": "AVISO", "componente": "carga",
                        "texto": "La última actualización de datos no se aplicó (" + ("rechazada por la compuerta de integridad" if carga_ult["estado"] == "RECHAZADA"
                                 else "error durante la carga") + "); se siguen mostrando los datos del corte anterior."})
    if sync and sync["estado"] == "ERROR":
        motivos.append({"nivel": "AVISO", "componente": "sincronizacion", "texto": "La última sincronización automática con las fuentes terminó con error."})
    if not latido:
        motivos.append({"nivel": "INFO", "componente": "worker", "texto": "La sincronización automática (worker) no está en ejecución en este despliegue; las actualizaciones se hacen manualmente."})
    elif (dt.datetime.now(dt.UTC) - latido["ts"]).total_seconds() > HORAS_LATIDO_WORKER * 3600:
        motivos.append({"nivel": "AVISO", "componente": "worker", "texto": f"El worker de sincronización no reporta actividad hace más de {HORAS_LATIDO_WORKER} horas."})
    n_crit = (cal.get("resumen") or {}).get("CRITICO", 0)
    if n_crit:
        motivos.append({"nivel": "CRITICO", "componente": "calidad", "texto": f"{n_crit} chequeos críticos de integridad con hallazgos."})
    psi_altos = [k for k, v in (mon.get("psi_ultimo_corte") or {}).items() if v is not None and v > 0.25]
    if psi_altos:
        motivos.append({"nivel": "AVISO", "componente": "modelo",
                        "texto": f"{len(psi_altos)} variables del modelo cambiaron de distribución respecto del entrenamiento (PSI > 0,25): conviene evaluar un reentrenamiento."})
    anom = mon.get("anomalia_nivel_alto") or {}
    if anom.get("anomala"):
        motivos.append({"nivel": "AVISO", "componente": "modelo", "texto": "La proporción de obras en nivel alto del corte vigente es atípica frente a su historial."})

    niveles = {m["nivel"] for m in motivos}
    estado = "DEGRADADO" if "CRITICO" in niveles else ("CON_AVISOS" if "AVISO" in niveles else "OPERATIVO")
    realizado = (mon.get("desempeno_realizado") or [])[-6:]
    return {
        "estado": estado, "motivos": motivos, "verificado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "base_datos": {"ok": True, "latencia_ms": bd_ms},
        "datos": {"fecha_corte": corte["fecha_corte"] if corte else None, "dias_desde_corte": dias, "frescura": cal.get("frescura")},
        "carga": {"ultima": {k: carga_ult[k] for k in ("inicio", "fin", "estado")} if carga_ult else None,
                  "ultima_ok": carga_ok["fin"] if carga_ok else None},
        "calidad": cal.get("resumen"),
        "modelo": {"version": modelo["version"], "entrenado_hasta": modelo["entrenado_hasta"], "horizonte_dias": modelo["horizonte_dias"],
                   "variables_con_deriva": len(psi_altos), "anomalia_nivel_alto": anom.get("anomala"),
                   "desempeno_realizado": realizado} if modelo else None,
        "sincronizacion": {k: sync[k] for k in ("inicio", "fin", "estado")} if sync else None,
        "worker": {"ultimo_latido": latido["ts"], "detalle": latido["detalle"]} if latido else None,
    }


@router.get("/sistema/estado")
def estado():
    """Semaforo operativo: OPERATIVO, CON_AVISOS o DEGRADADO, con los motivos en lenguaje claro."""
    return _estado()


@router.get("/admin/sincronizaciones")
def sincronizaciones(limite: int = Query(20, ge=1, le=200), _u: dict = Depends(require_role("admin"))):
    """Historial completo de sincronizaciones y cargas con sus mensajes de error (solo administradores)."""
    return {"sincronizaciones": db.rows("select id, inicio, fin, estado, pasos, mensaje, corte_datos from sincronizacion order by inicio desc limit :l", l=limite),
            "cargas": db.rows("select id, inicio, fin, estado, validacion, mensaje from carga_datos order by inicio desc limit :l", l=limite)}


@cacheado
def _ambitos_validos() -> dict[str, set]:
    rows = db.rows("""select departamento, provincia from obra where departamento is not null
                      union select departamento, provincia from cartera_obra where departamento is not null""")
    out: dict[str, set] = {}
    for r in rows:
        out.setdefault(r["departamento"], set()).add(r["provincia"])
    return out


class SuscripcionIn(BaseModel):
    email: str = Field(..., min_length=6, max_length=254)
    departamento: str | None = Field(None, max_length=40)
    provincia: str | None = Field(None, max_length=60)


@router.post("/suscripciones", status_code=202)
def suscribir(body: SuscripcionIn, request: Request):
    """Alta de suscripcion con doble confirmacion. La respuesta es la misma exista o no el correo (no revela suscriptores)."""
    from sato.services.mailer import EMAIL_RX, enviar

    email = body.email.strip().lower()
    dep = (body.departamento or "").strip().upper() or None
    prov = (body.provincia or "").strip().upper() or None
    if not EMAIL_RX.match(email):
        raise HTTPException(422, "Correo invalido")
    validos = _ambitos_validos()
    if (dep and dep not in validos) or (prov and (not dep or prov not in validos[dep])):
        raise HTTPException(422, "Ambito no reconocido en los datos cargados")
    s = get_settings()
    actual = db.one("""select id, confirmada, activa from suscripcion
                       where email = :e and departamento is not distinct from :d and provincia is not distinct from :p""", e=email, d=dep, p=prov)
    modo = None
    if not (actual and actual["confirmada"] and actual["activa"]):  # ya confirmada y activa: no se reenvia nada
        token = secrets.token_urlsafe(24)
        r = db.execute("""insert into suscripcion (email, departamento, provincia, token, token_creado_en) values (:e, :d, :p, :t, now())
                          on conflict on constraint suscripcion_ambito_unico do update
                            set token = excluded.token, token_creado_en = now(), activa = true,
                                confirmada = suscripcion.confirmada and suscripcion.activa
                          returning id""", e=email, d=dep, p=prov, t=token)
        ambito = " / ".join(x for x in (dep, prov) if x) or "Todo el Peru"
        modo = enviar(email, "SATO - Confirme su suscripcion",
                      f"Solicito recibir el resumen semanal de alertas de obras publicas ({ambito}).\n"
                      f"Confirme aqui (valido por {s.suscripcion_token_dias} dias): {s.base_url.rstrip('/')}/api/v1/suscripciones/confirmar?token={token}\n"
                      "Si no lo solicito, ignore este mensaje.")
        audit(request, "SUSCRIPCION", None, f"suscripcion:{r['id']}", {"ambito": ambito, "modo_correo": modo})
    from sato.services.mailer import smtp_configurado

    envio = "smtp" if smtp_configurado() else "archivo"
    return {"estado": "pendiente_confirmacion", "modo_envio": envio,
            "mensaje": ("Si el correo es válido, recibirá un mensaje para confirmar la suscripción." if envio == "smtp" else
                        "SMTP no configurado en este servidor: el mensaje de confirmación quedó en la bandeja local (artifacts/outbox).")}


def _html(t: str) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>SATO</title></head>"
                        f"<body style='font-family:sans-serif;padding:2rem'><h3>SATO</h3><p>{t}</p><a href='/'>Volver</a></body></html>",
                        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
                                 "Cache-Control": "no-store"})


@router.get("/suscripciones/confirmar", response_class=HTMLResponse)
def confirmar(token: str = Query(..., max_length=64)):
    dias = get_settings().suscripcion_token_dias
    if not TOKEN_RX.fullmatch(token) or not db.execute(
            """update suscripcion set confirmada = true where token = :t and activa
                 and token_creado_en > now() - make_interval(days => :d) returning id""", t=token, d=dias):
        return _html("Enlace inválido o vencido. Vuelva a suscribirse para recibir un enlace nuevo.")
    return _html("Suscripción confirmada. Recibirá el resumen semanal de alertas.")


@router.get("/suscripciones/baja", response_class=HTMLResponse)
def baja(token: str = Query(..., max_length=64)):
    # la baja no vence: siempre debe poder cancelarse desde cualquier correo recibido
    if not TOKEN_RX.fullmatch(token) or not db.execute("update suscripcion set activa = false where token = :t returning id", t=token):
        return _html("Enlace inválido.")
    return _html("Suscripción cancelada.")
