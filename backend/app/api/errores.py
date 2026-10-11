from typing import Any

from fastapi import FastAPI


def registrar_manejadores(app: FastAPI) -> None:
    pass


def respuestas_de_error(*codigos: int) -> dict[int | str, dict[str, Any]]:
    return {}
