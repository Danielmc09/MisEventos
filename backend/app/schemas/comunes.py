from datetime import datetime
from typing import Self

from pydantic import BaseModel

FechaUTC = datetime


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def crear(cls, items: list[T], total: int, page: int, page_size: int) -> Self:
        return cls(items=items, total=total, page=page, page_size=page_size, pages=0)
