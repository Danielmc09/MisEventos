from fastapi import APIRouter

from app.api.dependencias import RepoSalud
from app.api.errores import respuestas_de_error
from app.services import salud

router = APIRouter(tags=["salud"])


@router.get(
    "/health",
    summary="Estado del servicio",
    description="Responde 200 si la base de datos contesta a `SELECT 1`; si no, 503.",
    responses=respuestas_de_error(503),
)
def health(repo: RepoSalud) -> dict[str, str]:
    salud.verificar(repo)
    return {"status": "ok"}
