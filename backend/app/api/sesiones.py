from uuid import UUID

from fastapi import APIRouter, Response

router = APIRouter(tags=["sesiones"])


@router.get("/events/{id_evento}/sessions")
def listar(id_evento: UUID) -> Response:
    return Response(status_code=501)


@router.post("/events/{id_evento}/sessions")
def crear(id_evento: UUID) -> Response:
    return Response(status_code=501)


@router.patch("/sessions/{id_sesion}")
def editar(id_sesion: UUID) -> Response:
    return Response(status_code=501)


@router.delete("/sessions/{id_sesion}")
def eliminar(id_sesion: UUID) -> Response:
    return Response(status_code=501)
