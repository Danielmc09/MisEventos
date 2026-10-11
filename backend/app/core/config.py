from typing import Annotated, Literal, Self

from pydantic import AliasGenerator, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

# Valores de demostración publicados en .env.example. Sirven en desarrollo y se rechazan en
# producción, para que las credenciales de demo no lleguen ahí por descuido.
VALORES_DE_DEMO = {
    "JWT_SECRET": "demo-local-jwt-secret-solo-para-desarrollo-0001",
    "ADMIN_PASSWORD": "Admin-Demo-2026",
    "DEMO_PASSWORD": "Demo-Local-2026",
    "DATABASE_URL": "demo_local_db",  # se compara contra la contraseña de la URL
}


class Settings(BaseSettings):
    # Los errores nombran la variable de entorno tal como se escribe: DATABASE_URL, no database_url.
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        alias_generator=AliasGenerator(validation_alias=str.upper),
    )

    env: Literal["development", "production"] = "development"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = Field(default=60, ge=5, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    cors_origins: Annotated[list[str], NoDecode] = []
    seed_demo: bool = False
    admin_email: str | None = None
    admin_password: str | None = None
    demo_password: str | None = None
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def nivel_en_mayusculas(cls, valor: object) -> object:
        return valor.upper() if isinstance(valor, str) else valor

    @field_validator("cors_origins", mode="before")
    @classmethod
    def separar_origenes(cls, valor: str | list[str]) -> list[str]:
        if isinstance(valor, list):  # el valor por defecto también pasa por acá
            return valor
        origenes = [origen.strip() for origen in valor.split(",") if origen.strip()]
        if "*" in origenes:
            raise ValueError("'*' no se acepta: listá los orígenes permitidos")
        return origenes

    @model_validator(mode="after")
    def bloquear_valores_de_demo_en_produccion(self) -> Self:
        if self.env != "production":
            return self
        actuales = {
            "JWT_SECRET": self.jwt_secret,
            "ADMIN_PASSWORD": self.admin_password,
            "DEMO_PASSWORD": self.demo_password,
            "DATABASE_URL": make_url(self.database_url).password,
        }
        prohibidas = [
            nombre for nombre, demo in VALORES_DE_DEMO.items() if actuales[nombre] == demo
        ]
        if self.seed_demo:
            prohibidas.append("SEED_DEMO")
        if prohibidas:
            raise ValueError(
                "con ENV=production no se aceptan los valores de demostración de .env.example: "
                + ", ".join(prohibidas)
            )
        return self
