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
    # URL publica con la que se arman los enlaces de los correos (nunca se toma de la cabecera Host de la solicitud)
    base_url: str = "http://localhost:8080"
    # ingresos fallidos admitidos por cuenta dentro de la ventana (por IP se admite el cuadruple)
    login_max_fallos: int = 5
    login_ventana_min: int = 15
    # dias de validez del enlace de confirmacion de una suscripcion
    suscripcion_token_dias: int = 7
    # segundos que se reutiliza una respuesta agregada mientras los datos cargados no cambien
    cache_segundos: int = 300

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "prod":
        if len(s.jwt_secret) < 32:
            raise RuntimeError("SATO_JWT_SECRET debe tener al menos 32 caracteres en produccion")
        if "*" in s.cors_list:
            raise RuntimeError("SATO_CORS_ORIGINS no puede ser '*' en produccion")
    if not s.jwt_secret:
        import secrets

        s.jwt_secret = secrets.token_urlsafe(48)  # dev: secreto efimero por proceso
    return s
