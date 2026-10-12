"""Las capas importan solo hacia abajo: router → servicio → repositorio.

- Un servicio no sabe de HTTP: no importa `fastapi`, `starlette` ni nada de `app.api`.
- Un repositorio no conoce las reglas: no importa de `app.services` ni de `app.api`.
- Un router no toca los datos directo: no importa de `app.repositories`, salvo
  `app/api/dependencias.py`, que es donde se arman las dependencias que se inyectan.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"

REGLAS: dict[str, tuple[str, ...]] = {
    "services": ("fastapi", "starlette", "app.api"),
    "repositories": ("app.services", "app.api"),
    "api": ("app.repositories",),
}
EXCEPCIONES = {"api/dependencias.py"}


def nombre_de_modulo(archivo: Path, raiz: Path) -> str:
    """`app/api/health.py` → `app.api.health`; `app/api/__init__.py` → `app.api`."""
    partes = list(archivo.relative_to(raiz.parent).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


def _base_relativa(modulo: str, es_paquete: bool, nivel: int, destino: str | None) -> str:
    paquete = modulo.split(".") if es_paquete else modulo.split(".")[:-1]
    if nivel > 1:
        paquete = paquete[: -(nivel - 1)]
    return ".".join([*paquete, destino] if destino else paquete)


def imports_de(codigo: str, modulo: str, es_paquete: bool = False) -> list[tuple[int, list[str]]]:
    """Cada import del código, en cualquier lugar (dentro de funciones, de `if TYPE_CHECKING`…).

    Devuelve `(línea, candidatos)`: el módulo importado y, para `from x import y`, también `x.y`
    (por si `y` es un submódulo: `from app import api`). Los relativos se resuelven a absolutos.
    """
    encontrados = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            encontrados.extend((nodo.lineno, [alias.name]) for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = _base_relativa(modulo, es_paquete, nodo.level, nodo.module)
            else:
                base = nodo.module or ""
            submodulos = [f"{base}.{a.name}" for a in nodo.names if a.name != "*"]
            encontrados.append((nodo.lineno, [base, *submodulos]))
    return encontrados


def _cae_en(nombre: str, prefijos: tuple[str, ...]) -> bool:
    return any(nombre == p or nombre.startswith(p + ".") for p in prefijos)


def violaciones_de(archivo: Path, raiz: Path, prohibidos: tuple[str, ...]) -> list[str]:
    modulo = nombre_de_modulo(archivo, raiz)
    es_paquete = archivo.name == "__init__.py"
    relativo = archivo.relative_to(raiz.parent)
    violaciones = []
    for linea, candidatos in imports_de(archivo.read_text(encoding="utf-8"), modulo, es_paquete):
        prohibido = next((c for c in candidatos if _cae_en(c, prohibidos)), None)
        if prohibido:
            violaciones.append(f"{relativo}:{linea} → {prohibido}")
    return violaciones


def archivos_de(raiz: Path, carpeta: str) -> list[Path]:
    return sorted((raiz / carpeta).rglob("*.py"))


# El detector


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("import fastapi", "fastapi"),
        ("import starlette.requests as r", "starlette.requests"),
        ("from fastapi import Depends", "fastapi"),
        ("from app import api", "app.api"),
        ("def f():\n    from app.api import errores", "app.api"),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.api.x import Y",
            "app.api.x",
        ),
        ("from ..api import errores", "app.api"),
        ("from ..api.errores import algo", "app.api.errores"),
        ("from .. import api", "app.api"),
    ],
)
def test_el_detector_encuentra_el_import(codigo, esperado):
    candidatos = [c for _, cs in imports_de(codigo, "app.services.salud") for c in cs]

    assert _cae_en(esperado, ("fastapi", "starlette", "app.api"))
    assert esperado in candidatos


def test_un_import_relativo_desde_un_paquete_se_resuelve_desde_el_paquete():
    [(_, candidatos)] = imports_de("from .salud import x", "app.services", es_paquete=True)

    assert candidatos[0] == "app.services.salud"


def test_el_detector_no_confunde_un_prefijo_parecido():
    assert not _cae_en("app.apis", ("app.api",))
    assert not _cae_en("fastapi_extra", ("fastapi",))


# Las capas


@pytest.mark.parametrize("carpeta", list(REGLAS))
def test_cada_capa_tiene_archivos_para_recorrer(carpeta):
    assert archivos_de(APP, carpeta), f"No hay archivos .py en {APP / carpeta}"


def test_ninguna_capa_importa_de_una_superior():
    revisados = 0
    violaciones = []
    for carpeta, prohibidos in REGLAS.items():
        for archivo in archivos_de(APP, carpeta):
            revisados += 1
            if str(archivo.relative_to(APP)) in EXCEPCIONES:
                continue
            violaciones.extend(violaciones_de(archivo, APP, prohibidos))

    assert revisados, "No se recorrió ningún archivo"
    assert violaciones == [], "Imports que cruzan capas:\n" + "\n".join(violaciones)
