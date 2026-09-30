from __future__ import annotations

import datetime as dt
import ipaddress
import json

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sato.api import db
from sato.api.settings import get_settings

bearer = HTTPBearer(auto_error=False)
EMISOR = "sato-api"
# hash de referencia para comparar cuando el correo no existe: el tiempo de respuesta no revela si la cuenta existe
_HASH_FICTICIO = bcrypt.hashpw(b"sato-sin-cuenta", bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str | None) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), (hashed or _HASH_FICTICIO).encode()) and hashed is not None
    except ValueError:
        return False


def create_token(user: dict) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": str(user["id"]), "rol": user["rol"], "iss": EMISOR, "iat": now, "nbf": now, "exp": now + dt.timedelta(minutes=s.jwt_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"})


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise _no_autorizado("Autenticacion requerida")
    try:
        data = jwt.decode(cred.credentials, get_settings().jwt_secret, algorithms=["HS256"], issuer=EMISOR,
                          options={"require": ["exp", "iat", "sub", "iss"]})
        uid = int(data["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise _no_autorizado("Token invalido o expirado") from None
    u = db.one("select id, email, nombre, rol, activo from usuario where id = :id", id=uid)
    if not u or not u["activo"]:
        raise _no_autorizado("Usuario inactivo")
    # el rol vigente es el de la base: un cambio de rol surte efecto sin esperar a que expire el token
    return u


def require_role(*roles: str):
    def dep(u: dict = Depends(current_user)) -> dict:
        if u["rol"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
        return u

    return dep


def client_ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:  # p.ej. nombre de host de un proxy o cliente de pruebas
        return None


def intentos_fallidos(email: str, ip: str | None, minutos: int) -> tuple[int, int]:
    """Ingresos fallidos recientes por cuenta y por IP (defensa propia de la API, adicional al limite de nginx)."""
    r = db.one(
        """select count(*) filter (where lower(detalle->>'email') = lower(:e)) cuenta,
                  count(*) filter (where cast(:ip as inet) is not null and ip = cast(:ip as inet)) origen
           from auditoria where accion = 'LOGIN_FALLIDO' and ts > now() - make_interval(mins => :m)""",
        e=email, ip=ip, m=minutos)
    return int(r["cuenta"]), int(r["origen"])


def audit(request: Request, accion: str, usuario_id: int | None = None, recurso: str | None = None, detalle: dict | None = None) -> None:
    db.execute("insert into auditoria (usuario_id, accion, recurso, detalle, ip) values (:u, :a, :r, cast(:d as jsonb), cast(:ip as inet))",
               u=usuario_id, a=accion, r=recurso, d=json.dumps(detalle or {}, default=str), ip=client_ip(request))
