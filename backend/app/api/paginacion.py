from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

PAGE_SIZE_MAXIMO = 100
PAGE_MAXIMO = 10_000  # más allá, el OFFSET se vuelve un problema para la base


@dataclass(frozen=True)
class ParametrosPagina:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def parametros_pagina(
    page: Annotated[
        int, Query(ge=1, le=PAGE_MAXIMO, description="Página, desde 1 hasta 10000")
    ] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_MAXIMO, description="Elementos por página, hasta 100")
    ] = 12,
) -> ParametrosPagina:
    return ParametrosPagina(page=page, page_size=page_size)
