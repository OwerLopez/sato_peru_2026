from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SATO_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sato:sato@127.0.0.1:5432/sato"
    jwt_secret: str = ""  # obligatorio en produccion (se valida al iniciar)
    jwt_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    rate_limit: str = "120/minute"
    env: str = "dev"  # dev | prod

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "prod" and len(s.jwt_secret) < 32:
        raise RuntimeError("SATO_JWT_SECRET debe tener al menos 32 caracteres en produccion")
    if not s.jwt_secret:
        import secrets

        s.jwt_secret = secrets.token_urlsafe(48)  # dev: secreto efimero por proceso
    return s
