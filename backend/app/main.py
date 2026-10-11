from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.errores import registrar_manejadores
from app.api.middleware import HEADER_TRACE, trazabilidad
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # la cookie del refresh token lo necesita
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[HEADER_TRACE],
    )
    # El último en registrarse es el más externo: el trace_id cubre también CORS y los 500.
    app.middleware("http")(trazabilidad)
    return app
