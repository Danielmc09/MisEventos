import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

HEADER_TRACE = "X-Request-ID"

logger = logging.getLogger("miseventos.acceso")


def _trace_id(recibido: str | None) -> str:
    """Respeta el X-Request-ID del cliente solo si es un UUID; si no, genera uno."""
    if recibido:
        try:
            return str(uuid.UUID(recibido))
        except ValueError:
            pass
    return str(uuid.uuid4())


def _nivel(status: int) -> int:
    if status in (401, 403):
        return logging.WARNING
    if status >= 500:
        return logging.ERROR
    return logging.INFO


async def trazabilidad(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    trace_id = _trace_id(request.headers.get(HEADER_TRACE))
    request.state.trace_id = trace_id
    inicio = time.perf_counter()

    response = await call_next(request)

    response.headers[HEADER_TRACE] = trace_id
    # Nunca cuerpos ni headers: ahí viajan contraseñas y tokens.
    campos = {
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round((time.perf_counter() - inicio) * 1000, 2),
    }
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        campos["user_id"] = str(user_id)
    logger.log(_nivel(response.status_code), "request", extra={"campos": campos})
    return response
