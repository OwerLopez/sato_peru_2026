from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from sato.api import db
from sato.api.security import audit, client_ip, create_token, current_user, intentos_fallidos, verify_password
from sato.api.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request):
    s = get_settings()
    email = body.email.strip()
    por_cuenta, por_ip = intentos_fallidos(email, client_ip(request), s.login_ventana_min)
    if por_cuenta >= s.login_max_fallos or por_ip >= 4 * s.login_max_fallos:
        audit(request, "LOGIN_BLOQUEADO", None, "auth", {"email": email})
        raise HTTPException(429, f"Demasiados intentos fallidos. Intente de nuevo en {s.login_ventana_min} minutos.",
                            headers={"Retry-After": str(60 * s.login_ventana_min)})
    u = db.one("select id, email, nombre, rol, password_hash, activo from usuario where lower(email) = lower(:e)", e=email)
    # se verifica siempre una contrasena (aunque la cuenta no exista) para no revelar por tiempo que correos estan registrados
    ok = verify_password(body.password, u["password_hash"] if u else None)
    if not u or not u["activo"] or not ok:
        audit(request, "LOGIN_FALLIDO", None, "auth", {"email": email})
        raise HTTPException(401, "Credenciales invalidas")
    audit(request, "LOGIN", u["id"], "auth")
    return {"access_token": create_token(u), "token_type": "bearer", "expira_en_min": s.jwt_minutes,
            "usuario": {k: u[k] for k in ("id", "email", "nombre", "rol")}}


@router.get("/me")
def me(u: dict = Depends(current_user)):
    return {k: u[k] for k in ("id", "email", "nombre", "rol")}
