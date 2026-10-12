import math
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, field_validator

# Postgres no guarda el carácter nulo en un text, y el driver lo rechaza en cualquier parámetro
# de texto con un error que terminaría en 500. Se corta en la entrada, con 422 en el campo.
CARACTER_NULO = "\x00"
MENSAJE_CARACTER_NULO = "No puede contener el carácter nulo"


def _a_utc(fecha: datetime) -> datetime:
    return fecha.astimezone(UTC)


def tiene_caracter_nulo(valor: object) -> bool:
    """Busca el nulo en un texto o en cualquier texto anidado: listas, tuplas, conjuntos,
    claves y valores de diccionarios, y campos de submodelos."""
    if isinstance(valor, str):
        return CARACTER_NULO in valor
    if isinstance(valor, BaseModel):
        return any(tiene_caracter_nulo(getattr(valor, campo)) for campo in type(valor).model_fields)
    if isinstance(valor, dict):
        return any(tiene_caracter_nulo(k) or tiene_caracter_nulo(v) for k, v in valor.items())
    if isinstance(valor, list | tuple | set | frozenset):
        return any(tiene_caracter_nulo(elemento) for elemento in valor)
    return False


class EntradaBase(BaseModel):
    """Base de todo esquema de entrada: ningún texto del modelo puede traer el carácter nulo."""

    # mode="after": corre cuando el campo ya pasó su propia validación, así que min_length y
    # max_length miden el texto ya recortado y el error de largo sale primero.
    @field_validator("*")
    @classmethod
    def _sin_caracter_nulo(cls, valor: object) -> object:
        if tiene_caracter_nulo(valor):
            raise ValueError(MENSAJE_CARACTER_NULO)
        return valor


# Fecha ISO 8601 con zona obligatoria (sin zona → 422). Se guarda y se responde en UTC, con Z.
FechaUTC = Annotated[AwareDatetime, AfterValidator(_a_utc)]


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def crear(cls, items: list[T], total: int, page: int, page_size: int) -> Self:
        pages = math.ceil(total / page_size)
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
