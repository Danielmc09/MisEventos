"""Excepciones de dominio. Los servicios las lanzan sin saber nada de HTTP; un único handler
de la capa api las traduce a problem+json según `status`, `tipo` y `titulo`."""


class DomainError(Exception):
    status: int = 400
    tipo: str = "bad-request"
    titulo: str = "La solicitud no es válida"

    def __init__(
        self, detalle: str | None = None, *, tipo: str | None = None, titulo: str | None = None
    ) -> None:
        super().__init__(detalle or self.titulo)
        self.detalle = detalle
        if tipo:
            self.tipo = tipo
        if titulo:
            self.titulo = titulo


class Unauthorized(DomainError):
    status = 401
    tipo = "unauthorized"
    titulo = "Necesitás iniciar sesión"


class Forbidden(DomainError):
    status = 403
    tipo = "forbidden"
    titulo = "No tenés permiso para hacer esto"


class NotFound(DomainError):
    status = 404
    tipo = "not-found"
    titulo = "No encontramos lo que buscás"


class Conflict(DomainError):
    status = 409
    tipo = "conflict"
    titulo = "La operación choca con el estado actual"


class ServiceUnavailable(DomainError):
    status = 503
    tipo = "service-unavailable"
    titulo = "El servicio no está disponible en este momento"
