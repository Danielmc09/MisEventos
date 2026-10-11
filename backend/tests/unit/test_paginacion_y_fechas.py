from typing import Annotated

import pytest
from fastapi import Depends
from pydantic import BaseModel

from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.schemas.comunes import FechaUTC, Pagina


class ConFecha(BaseModel):
    inicio: FechaUTC


@pytest.fixture
def rutas(app):
    @app.post("/con-fecha")
    def con_fecha(datos: ConFecha) -> ConFecha:
        return datos

    @app.get("/listado")
    def listado(
        pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    ) -> dict[str, int]:
        return {"page": pagina.page, "page_size": pagina.page_size, "offset": pagina.offset}

    return app


def campos_con_error(respuesta) -> set[str]:
    assert respuesta.status_code == 422
    return {error["field"] for error in respuesta.json()["errors"]}


@pytest.mark.parametrize("sin_zona", ["2026-10-13T10:00:00", "2026-10-13 10:00"])
def test_una_fecha_sin_zona_horaria_responde_422(rutas, cliente, sin_zona):
    respuesta = cliente.post("/con-fecha", json={"inicio": sin_zona})

    assert campos_con_error(respuesta) == {"inicio"}


def test_una_fecha_con_zona_se_devuelve_en_utc_con_z(rutas, cliente):
    respuesta = cliente.post("/con-fecha", json={"inicio": "2026-10-13T10:00:00-05:00"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"inicio": "2026-10-13T15:00:00Z"}


def test_paginacion_por_defecto_es_pagina_1_de_12(rutas, cliente):
    respuesta = cliente.get("/listado")

    assert respuesta.json() == {"page": 1, "page_size": 12, "offset": 0}


def test_page_size_100_y_page_3_se_aceptan(rutas, cliente):
    respuesta = cliente.get("/listado", params={"page": 3, "page_size": 100})

    assert respuesta.json() == {"page": 3, "page_size": 100, "offset": 200}


def test_page_10000_es_la_ultima_pagina_aceptada(rutas, cliente):
    respuesta = cliente.get("/listado", params={"page": 10000})

    assert respuesta.status_code == 200
    assert respuesta.json()["page"] == 10000


@pytest.mark.parametrize(
    ("params", "campo"),
    [
        ({"page_size": 101}, "page_size"),
        ({"page_size": 0}, "page_size"),
        ({"page": 0}, "page"),
        ({"page": 10001}, "page"),
    ],
)
def test_paginacion_fuera_de_rango_responde_422(rutas, cliente, params, campo):
    assert campos_con_error(cliente.get("/listado", params=params)) == {campo}


@pytest.mark.parametrize(
    ("total", "page_size", "pages"),
    [(42, 12, 4), (48, 12, 4), (49, 12, 5), (0, 12, 0), (1, 100, 1)],
)
def test_pagina_calcula_la_cantidad_de_paginas(total, page_size, pages):
    pagina = Pagina[int].crear([], total=total, page=1, page_size=page_size)

    assert pagina.model_dump() == {
        "items": [],
        "total": total,
        "page": 1,
        "page_size": page_size,
        "pages": pages,
    }
