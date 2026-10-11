from fastapi import FastAPI

from app.api import health
from app.api.errores import registrar_manejadores
from app.api.middleware import trazabilidad
from app.core.config import Settings
from app.core.logs import configurar_logs


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configurar_logs(settings.log_level)
    app = FastAPI(
        title="Mis Eventos API",
        version="0.1.0",
        description="Gestión de eventos, sesiones, ponentes e inscripciones.",
    )
    registrar_manejadores(app)
    app.include_router(health.router)
    app.middleware("http")(trazabilidad)
    return app
