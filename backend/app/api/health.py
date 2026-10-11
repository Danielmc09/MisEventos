from fastapi import APIRouter

from app.api.errores import respuestas_de_error
from app.core.db import SesionDB
from app.core.excepciones import ServiceUnavailable
from app.repositories.salud import base_responde

router = APIRouter(tags=["salud"])


@router.get(
    "/health",
    summary="Estado del servicio",
    description="Responde 200 si la base de datos contesta a `SELECT 1`; si no, 503.",
    responses=respuestas_de_error(503),
)
def health(session: SesionDB) -> dict[str, str]:
    if not base_responde(session):
        raise ServiceUnavailable("La base de datos no responde.")
    return {"status": "ok"}
