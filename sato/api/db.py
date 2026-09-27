"""Acceso a datos: SQLAlchemy Core con parametros enlazados (sin concatenar entrada del usuario)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sato.api.settings import get_settings


@lru_cache
def engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, connect_args={"options": "-c search_path=sato,public", "connect_timeout": 10})


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
        except Exception:
            return None


def patron(q: str | None) -> str | None:
    """Patron ILIKE literal: escapa los comodines % y _ escritos por el usuario (usar con `escape '!'` en SQL)."""
    if q is None or not q.strip():
        return None
    q = q.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{q}%"
