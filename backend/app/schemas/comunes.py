import math
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel


def _a_utc(fecha: datetime) -> datetime:
    return fecha.astimezone(UTC)


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
