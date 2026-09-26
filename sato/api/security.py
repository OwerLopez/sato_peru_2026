from __future__ import annotations

import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sato.api import db
from sato.api.settings import get_settings

bearer = HTTPBearer(auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: dict) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user["id"]), "rol": user["rol"], "iat": now, "exp": now + dt.timedelta(minutes=s.jwt_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticacion requerida", headers={"WWW-Authenticate": "Bearer"})
    try:
        data = jwt.decode(cred.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido o expirado", headers={"WWW-Authenticate": "Bearer"})
    u = db.one("select id, email, nombre, rol, activo from usuario where id = :id", id=int(data["sub"]))
    if not u or not u["activo"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo")
    return u


def require_role(*roles: str):
    def dep(u: dict = Depends(current_user)) -> dict:
        if u["rol"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
        return u

    return dep


def audit(request: Request, accion: str, usuario_id: int | None = None, recurso: str | None = None, detalle: dict | None = None) -> None:
    import ipaddress
    import json

    ip = request.client.host if request.client else None
    try:
        ip = str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:  # p.ej. nombre de host de un proxy o cliente de pruebas
        ip = None
    db.execute("insert into auditoria (usuario_id, accion, recurso, detalle, ip) values (:u, :a, :r, cast(:d as jsonb), cast(:ip as inet))",
               u=usuario_id, a=accion, r=recurso, d=json.dumps(detalle or {}, default=str), ip=ip)
