from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

PAGE_SIZE_MAXIMO = 100


@dataclass(frozen=True)
class ParametrosPagina:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def parametros_pagina(
    page: Annotated[int, Query(ge=1, description="Página, desde 1")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_MAXIMO, description="Elementos por página, hasta 100")
    ] = 12,
) -> ParametrosPagina:
    return ParametrosPagina(page=page, page_size=page_size)
