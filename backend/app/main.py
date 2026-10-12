from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, eventos, health, ponentes, sesiones
from app.api.dependencias import sin_caracter_nulo
from app.api.errores import registrar_manejadores
from app.api.middleware import HEADER_TRACE, errores_no_esperados, trazabilidad
from app.core.config import Settings
from app.core.db import crear_fabrica_de_sesiones
from app.core.logs import configurar_logs


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configurar_logs(settings.log_level)
    app = FastAPI(
        title="Mis Eventos API",
        version="0.1.0",
        description="Gestión de eventos, sesiones, ponentes e inscripciones.",
        dependencies=[Depends(sin_caracter_nulo)],
    )
    # El engine no se conecta hasta la primera consulta: crear la app no necesita la base.
    app.state.settings = settings
    app.state.sesiones = crear_fabrica_de_sesiones(settings.database_url)
    registrar_manejadores(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(eventos.router)
    app.include_router(ponentes.router)
    app.include_router(sesiones.router)
    # El último en registrarse es el más externo. Orden de afuera hacia adentro: trazabilidad
    # (trace_id y log de todo request, incluso el preflight), CORS, y la captura del 500, que
    # queda por dentro de CORS para que el 500 también lleve Access-Control-Allow-Origin.
    app.middleware("http")(errores_no_esperados)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # la cookie del refresh token lo necesita
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[HEADER_TRACE],
    )
    app.middleware("http")(trazabilidad)
    return app
