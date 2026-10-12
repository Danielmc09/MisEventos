"""Las capas importan solo hacia abajo: router → servicio → repositorio.

- Un servicio no sabe de HTTP: no importa `fastapi`, `starlette` ni nada de `app.api`.
- Un repositorio no conoce las reglas ni HTTP: no importa `fastapi`, `starlette`, `app.services`
  ni `app.api`.
- Un router no toca los datos directo: no importa `app.repositories`, `app.core.db`, `sqlmodel`
  ni `sqlalchemy`, salvo `app/api/dependencias.py`, que es donde se arman las dependencias que se
  inyectan.
- En ninguna capa se importa de forma dinámica (`importlib.import_module`, `__import__`): el
  detector no puede ver qué módulo cargan.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"

REGLAS: dict[str, tuple[str, ...]] = {
    "services": ("fastapi", "starlette", "app.api"),
    "repositories": ("fastapi", "starlette", "app.services", "app.api"),
    "api": ("app.repositories", "app.core.db", "sqlmodel", "sqlalchemy"),
}
IMPORTS_DINAMICOS = {"import_module", "__import__"}
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


def imports_dinamicos_de(codigo: str) -> list[tuple[int, str]]:
    """Cada llamada a `importlib.import_module` o `__import__`: el AST no ve qué importan."""
    encontrados = []
    for nodo in ast.walk(ast.parse(codigo)):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        nombre = (
            funcion.attr
            if isinstance(funcion, ast.Attribute)
            else funcion.id
            if isinstance(funcion, ast.Name)
            else None
        )
        if nombre in IMPORTS_DINAMICOS:
            encontrados.append((nodo.lineno, nombre))
    return encontrados


def _cae_en(nombre: str, prefijos: tuple[str, ...]) -> bool:
    return any(nombre == p or nombre.startswith(p + ".") for p in prefijos)


def violaciones_de(archivo: Path, raiz: Path, prohibidos: tuple[str, ...]) -> list[str]:
    modulo = nombre_de_modulo(archivo, raiz)
    es_paquete = archivo.name == "__init__.py"
    relativo = archivo.relative_to(raiz.parent)
    codigo = archivo.read_text(encoding="utf-8")
    violaciones = []
    for linea, candidatos in imports_de(codigo, modulo, es_paquete):
        prohibido = next((c for c in candidatos if _cae_en(c, prohibidos)), None)
        if prohibido:
            violaciones.append(f"{relativo}:{linea} → {prohibido}")
    for linea, nombre in imports_dinamicos_de(codigo):
        violaciones.append(f"{relativo}:{linea} → import dinámico: {nombre}")
    return violaciones


def archivos_de(raiz: Path, carpeta: str) -> list[Path]:
    return sorted((raiz / carpeta).rglob("*.py"))


def violaciones_en(raiz: Path) -> tuple[int, list[str]]:
    """Recorre las capas bajo `raiz` y devuelve `(archivos revisados, violaciones)`."""
    revisados = 0
    violaciones = []
    for carpeta, prohibidos in REGLAS.items():
        for archivo in archivos_de(raiz, carpeta):
            revisados += 1
            if str(archivo.relative_to(raiz)) in EXCEPCIONES:
                continue
            violaciones.extend(violaciones_de(archivo, raiz, prohibidos))
    return revisados, violaciones


def _arbol(raiz: Path, archivos: dict[str, str]) -> Path:
    app = raiz / "app"
    for ruta, codigo in archivos.items():
        destino = app / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(codigo, encoding="utf-8")
    return app


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


def test_el_recorrido_reporta_cada_violacion_de_un_servicio_con_su_linea(tmp_path):
    app = _arbol(
        tmp_path,
        {
            "services/__init__.py": "from .. import api\n",
            "services/x.py": "import os\nfrom fastapi import Request\n",
            "services/dinamico.py": (
                "import importlib\n"
                "\n"
                "modulo = importlib.import_module('app.api.errores')\n"
                "otro = __import__('fastapi')\n"
            ),
            "services/limpio.py": "from app.repositories import eventos\n",
        },
    )

    revisados, violaciones = violaciones_en(app)

    assert revisados == 4
    assert sorted(violaciones) == sorted(
        [
            "app/services/__init__.py:1 → app.api",
            "app/services/x.py:2 → fastapi",
            "app/services/dinamico.py:3 → import dinámico: import_module",
            "app/services/dinamico.py:4 → import dinámico: __import__",
        ]
    )


def test_un_repositorio_no_importa_http(tmp_path):
    app = _arbol(
        tmp_path,
        {
            "repositories/x.py": "from fastapi import HTTPException\n",
            "repositories/y.py": "\nimport starlette.status\n",
        },
    )

    _, violaciones = violaciones_en(app)

    assert sorted(violaciones) == [
        "app/repositories/x.py:1 → fastapi",
        "app/repositories/y.py:2 → starlette.status",
    ]


def test_un_router_no_toca_la_base_salvo_las_dependencias(tmp_path):
    app = _arbol(
        tmp_path,
        {
            "api/rutas.py": (
                "from app.core.db import SesionDB\nfrom sqlmodel import select\nimport sqlalchemy\n"
            ),
            "api/otra.py": "from app.core import db\n",
            "api/dependencias.py": (
                "from app.core.db import SesionDB\nfrom sqlmodel import Session\n"
            ),
        },
    )

    _, violaciones = violaciones_en(app)

    assert sorted(violaciones) == [
        "app/api/otra.py:1 → app.core.db",
        "app/api/rutas.py:1 → app.core.db",
        "app/api/rutas.py:2 → sqlmodel",
        "app/api/rutas.py:3 → sqlalchemy",
    ]


def test_ninguna_capa_importa_de_una_superior():
    revisados, violaciones = violaciones_en(APP)

    assert revisados, "No se recorrió ningún archivo"
    assert violaciones == [], "Imports que cruzan capas:\n" + "\n".join(violaciones)
