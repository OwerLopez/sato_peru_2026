from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from sato.api import db
from sato.api.security import audit, create_token, current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request):
    u = db.one("select id, email, nombre, rol, password_hash, activo from usuario where lower(email) = lower(:e)", e=body.email)
    if not u or not u["activo"] or not verify_password(body.password, u["password_hash"]):
        audit(request, "LOGIN_FALLIDO", None, "auth", {"email": body.email})
        raise HTTPException(401, "Credenciales invalidas")
    audit(request, "LOGIN", u["id"], "auth")
    return {"access_token": create_token(u), "token_type": "bearer", "usuario": {k: u[k] for k in ("id", "email", "nombre", "rol")}}


@router.get("/me")
def me(u: dict = Depends(current_user)):
    return u
