from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "production"] = "development"
    database_url: str = ""
    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cors_origins: str = ""
    seed_demo: bool = False
    admin_email: str | None = None
    admin_password: str | None = None
    demo_password: str | None = None
    log_level: str = "INFO"
