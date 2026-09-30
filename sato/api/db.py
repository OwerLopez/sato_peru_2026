"""Acceso a datos: SQLAlchemy Core con parametros enlazados (sin concatenar entrada del usuario)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ResourceClosedError

from sato.api.settings import get_settings


@lru_cache
def engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # statement_timeout: ninguna consulta ocupa una conexion mas de 20 s (proteccion ante consultas costosas);
    # lock_timeout: si una tabla esta bloqueada (mantenimiento manual), la solicitud falla en 5 s con 503 en vez de quedar colgada
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800,
                         connect_args={"options": "-c search_path=sato,public -c statement_timeout=20000 -c lock_timeout=5000",
                                       "connect_timeout": 10})


def rows(sql: str, **params: Any) -> list[dict]:
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params)]


def one(sql: str, **params: Any) -> dict | None:
    r = rows(sql, **params)
    return r[0] if r else None


def execute(sql: str, **params: Any) -> dict | None:
    with engine().begin() as c:
        res = c.execute(text(sql), params)
        try:
            r = res.first()
            return dict(r._mapping) if r else None
        except ResourceClosedError:  # sentencia sin filas de retorno
            return None


def patron(q: str | None) -> str | None:
    """Patron ILIKE literal: escapa los comodines % y _ escritos por el usuario (usar con `escape '!'` en SQL)."""
    if q is None or not q.strip():
        return None
    q = q.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{q}%"
