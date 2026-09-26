"""API REST de SATO.

    uvicorn sato.api.main:app --host 0.0.0.0 --port 8000

Lectura publica (datos abiertos de origen), escritura (revisiones) solo para
usuarios autenticados con rol. Controles: CORS restringido, limite de tasa,
cabeceras de seguridad, validacion de entrada (pydantic), consultas
parametrizadas, auditoria y registro con request-id.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text

from sato import __version__
from sato.api.db import engine
from sato.api.routes import alertas, auth, cartera, estadisticas, informe, obras, radar, sistema
from sato.api.settings import get_settings

log = logging.getLogger("sato.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(
    title="SATO API",
    version=__version__,
    description="Deteccion temprana de riesgo de atraso significativo en obras publicas de Arequipa (datos abiertos OECE, MEF, Contraloria).",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if not request.url.path.startswith(("/api/docs", "/api/v1/suscripciones")):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    log.info("%s %s %s %.1fms rid=%s", request.method, request.url.path, response.status_code, ms, rid)
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("error no controlado en %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/api/health", tags=["salud"])
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/ready", tags=["salud"])
def ready():
    try:
        with engine().connect() as c:
            c.execute(text("select 1"))
            m = c.execute(text("select version from sato.modelo where activo")).first()
        return {"status": "ready", "modelo": m[0] if m else None}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "not_ready", "detail": type(e).__name__})


for r in (radar.router, cartera.router, informe.router, sistema.router, obras.router, alertas.router, estadisticas.router, auth.router):
    app.include_router(r, prefix="/api/v1")
