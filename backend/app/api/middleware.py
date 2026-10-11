from collections.abc import Awaitable, Callable

from fastapi import Request, Response

HEADER_TRACE = "X-Request-ID"


async def trazabilidad(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    return await call_next(request)
