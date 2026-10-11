from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.excepciones import DomainError
from app.schemas.errores import ErrorDeCampo, Problema

PROBLEM_JSON = "application/problem+json"

# type y title de los errores que no nacen de una excepción de dominio.
POR_STATUS: dict[int, tuple[str, str]] = {
    400: ("bad-request", "La solicitud no es válida"),
    401: ("unauthorized", "Necesitás iniciar sesión"),
    403: ("forbidden", "No tenés permiso para hacer esto"),
    404: ("not-found", "No encontramos lo que buscás"),
    405: ("method-not-allowed", "Ese método no está permitido acá"),
    409: ("conflict", "La operación choca con el estado actual"),
    422: ("validation-error", "Los datos enviados no son válidos"),
    500: ("internal-error", "Ocurrió un error inesperado"),
    503: ("service-unavailable", "El servicio no está disponible en este momento"),
}
GENERICO = ("http-error", "No se pudo completar la solicitud")
UBICACIONES = {"body", "query", "path", "header", "cookie"}


def problema(
    trace_id: str,
    status: int,
    *,
    tipo: str | None = None,
    titulo: str | None = None,
    detalle: str | None = None,
    errores: list[ErrorDeCampo] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    tipo_status, titulo_status = POR_STATUS.get(status, GENERICO)
    cuerpo = Problema(
        type=tipo or tipo_status,
        title=titulo or titulo_status,
        status=status,
        detail=detalle,
        trace_id=trace_id,
        errors=errores,
    )
    return JSONResponse(
        cuerpo.model_dump(exclude_none=True),
        status_code=status,
        media_type=PROBLEM_JSON,
        headers=headers,
    )


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _campo(loc: tuple[int | str, ...]) -> str:
    partes = list(loc[1:] if len(loc) > 1 and loc[0] in UBICACIONES else loc)
    return ".".join(str(parte) for parte in partes)


def _mensaje(msg: str) -> str:
    return msg.removeprefix("Value error, ")


async def _dominio(request: Request, exc: DomainError) -> JSONResponse:
    return problema(
        _trace_id(request), exc.status, tipo=exc.tipo, titulo=exc.titulo, detalle=exc.detalle
    )


async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problema(_trace_id(request), exc.status_code, headers=exc.headers)


async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [
        ErrorDeCampo(field=_campo(tuple(e["loc"])), message=_mensaje(e["msg"]))
        for e in exc.errors()
    ]
    return problema(_trace_id(request), 422, errores=errores)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _dominio)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validacion)


def respuestas_de_error(*codigos: int) -> dict[int | str, dict[str, Any]]:
    """Declara en el OpenAPI de un endpoint los errores que puede devolver, como problem+json."""
    return {
        codigo: {
            "model": Problema,
            "description": POR_STATUS.get(codigo, GENERICO)[1],
            "content": {PROBLEM_JSON: {"schema": {"$ref": "#/components/schemas/Problema"}}},
        }
        for codigo in codigos
    }
