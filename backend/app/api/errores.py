from collections.abc import Mapping
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
    extensiones: dict[str, object] | None = None,
) -> JSONResponse:
    tipo_status, titulo_status = POR_STATUS.get(status, GENERICO)
    cuerpo = Problema(
        type=tipo or tipo_status,
        title=titulo or titulo_status,
        status=status,
        detail=detalle,
        trace_id=trace_id,
        errors=errores,
        **(extensiones or {}),
    )
    return JSONResponse(
        # mode="json": las extensiones pueden traer UUID y fechas (las UTC salen con Z).
        cuerpo.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_JSON,
        headers=headers,
    )


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _campo(loc: tuple[int | str, ...]) -> str:
    partes = list(loc[1:] if len(loc) > 1 and loc[0] in UBICACIONES else loc)
    return ".".join(str(parte) for parte in partes)


# Mensajes del 422 por type de error de pydantic; los {campos} salen de su ctx.
FECHA_ISO = "Debe ser una fecha y hora ISO 8601"
MENSAJES_422 = {
    "missing": "Este campo es obligatorio",
    "string_too_short": "Debe tener al menos {min_length} caracteres",
    "string_too_long": "Debe tener como máximo {max_length} caracteres",
    "too_long": "Debe tener como máximo {max_length} elementos",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "greater_than": "Debe ser mayor que {gt}",
    "less_than": "Debe ser menor que {lt}",
    "int_parsing": "Debe ser un número entero",
    "float_parsing": "Debe ser un número",
    "bool_parsing": "Debe ser verdadero o falso",
    "datetime_parsing": FECHA_ISO,
    "datetime_from_date_parsing": FECHA_ISO,
    "timezone_aware": "Debe incluir la zona horaria",
    "uuid_parsing": "Debe ser un UUID válido",
    "enum": "Debe ser uno de: {expected}",
    "literal_error": "Debe ser uno de: {expected}",
    "extra_forbidden": "Este campo no está permitido",
    "json_invalid": "El cuerpo no es un JSON válido",
}
MENSAJE_GENERICO = "Valor inválido"


def _mensaje(error: Mapping[str, Any]) -> str:
    """Traduce un error de pydantic. Nunca devuelve el texto en inglés de pydantic."""
    if error["type"] == "value_error":
        # Lo lanzan nuestros validadores, ya en español; pydantic solo le antepone un prefijo.
        return error["msg"].removeprefix("Value error, ")
    plantilla = MENSAJES_422.get(error["type"], MENSAJE_GENERICO)
    ctx = {k: str(v).replace(" or ", " o ") for k, v in error.get("ctx", {}).items()}
    try:
        return plantilla.format_map(ctx)
    except KeyError:  # un type conocido sin el ctx que su mensaje necesita
        return MENSAJE_GENERICO


async def _dominio(request: Request, exc: DomainError) -> JSONResponse:
    return problema(
        _trace_id(request),
        exc.status,
        tipo=exc.tipo,
        titulo=exc.titulo,
        detalle=exc.detalle,
        errores=[ErrorDeCampo(field=c, message=m) for c, m in (exc.errores or {}).items()] or None,
        headers=exc.headers,
        extensiones=exc.extensiones,
    )


async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problema(_trace_id(request), exc.status_code, headers=exc.headers)


async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [
        ErrorDeCampo(field=_campo(tuple(e["loc"])), message=_mensaje(e)) for e in exc.errors()
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
