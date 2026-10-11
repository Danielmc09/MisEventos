from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True)
class ParametrosPagina:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def parametros_pagina(page: int = Query(1), page_size: int = Query(12)) -> ParametrosPagina:
    return ParametrosPagina(page=page, page_size=page_size)
