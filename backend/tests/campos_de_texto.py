"""Recorre el OpenAPI de la app y junta cada campo de texto de cada endpoint, con el lugar por
donde llega: el cuerpo JSON, un formulario o la query. Lo usan los tests que mandan el carácter
nulo campo por campo, así un endpoint nuevo queda cubierto sin que nadie se acuerde de él."""

from dataclasses import dataclass
from typing import Any, Literal

Ubicacion = Literal["body", "form", "query"]

# Un tipo de cuerpo que no esté acá hace fallar el recorrido: hay que decidir cómo se prueba.
UBICACION_POR_CONTENIDO: dict[str, Ubicacion] = {
    "application/json": "body",
    "application/x-www-form-urlencoded": "form",
    "multipart/form-data": "form",
}


@dataclass(frozen=True)
class CampoDeTexto:
    metodo: str
    ruta: str
    ubicacion: Ubicacion
    nombre: str
    esquema: str | None = None  # el esquema del cuerpo en components; None en la query

    def __str__(self) -> str:
        return f"{self.metodo.upper()} {self.ruta} [{self.ubicacion}] {self.nombre}"


def _resolver(esquema: dict[str, Any], componentes: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in esquema:
        esquema = componentes[esquema["$ref"].rsplit("/", 1)[-1]]
    return esquema


def _acepta_texto(esquema: dict[str, Any], componentes: dict[str, Any]) -> bool:
    esquema = _resolver(esquema, componentes)
    if esquema.get("type") == "string":
        return True
    if esquema.get("type") == "array":
        return _acepta_texto(esquema.get("items", {}), componentes)
    alternativas = esquema.get("anyOf", []) + esquema.get("oneOf", [])
    return any(_acepta_texto(alternativa, componentes) for alternativa in alternativas)


def campos_de_texto(openapi: dict[str, Any]) -> list[CampoDeTexto]:
    componentes = openapi.get("components", {}).get("schemas", {})
    campos: list[CampoDeTexto] = []
    for ruta, operaciones in openapi["paths"].items():
        for metodo, operacion in operaciones.items():
            for parametro in operacion.get("parameters", []):
                if parametro["in"] == "query" and _acepta_texto(parametro["schema"], componentes):
                    campos.append(CampoDeTexto(metodo, ruta, "query", parametro["name"]))
            contenidos = operacion.get("requestBody", {}).get("content", {})
            for tipo, contenido in contenidos.items():
                ubicacion = UBICACION_POR_CONTENIDO[tipo]
                nombre_esquema = contenido["schema"]["$ref"].rsplit("/", 1)[-1]
                esquema = _resolver(contenido["schema"], componentes)
                for nombre, propiedad in esquema.get("properties", {}).items():
                    if _acepta_texto(propiedad, componentes):
                        campos.append(CampoDeTexto(metodo, ruta, ubicacion, nombre, nombre_esquema))
    return campos
