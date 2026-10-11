"""Los servicios y la api preguntan por un permiso (`tiene_permiso`), nunca por el rol."""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
CARPETAS = [APP / "services", APP / "api"]


def _nombra_un_rol(nodo: ast.AST) -> bool:
    """`x.role`, `role` o `Rol.ADMIN`."""
    if isinstance(nodo, ast.Attribute):
        return nodo.attr == "role" or (isinstance(nodo.value, ast.Name) and nodo.value.id == "Rol")
    return isinstance(nodo, ast.Name) and nodo.id == "role"


def comparaciones_de_rol(codigo: str) -> list[int]:
    """Líneas donde se compara un rol (`==`, `!=`, `in`, `is`) o se hace `match` sobre él."""
    lineas = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Compare):
            operandos = [nodo.left, *nodo.comparators]
        elif isinstance(nodo, ast.Match):
            operandos = [nodo.subject]
        else:
            continue
        if any(_nombra_un_rol(o) for o in operandos):
            lineas.append(nodo.lineno)
    return lineas


def archivos_a_revisar() -> list[Path]:
    return sorted(p for carpeta in CARPETAS for p in carpeta.rglob("*.py"))


@pytest.mark.parametrize(
    "codigo",
    [
        "usuario.role == Rol.ADMIN",
        "Rol.ADMIN == usuario.role",
        "usuario.role != 'ADMIN'",
        "if Rol.ADMIN in roles: pass",
        "usuario.role in (Rol.ADMIN, Rol.ORGANIZER)",
        "role == 'ADMIN'",
        "usuario.role is Rol.ADMIN",
        "match usuario.role:\n    case _: pass",
    ],
)
def test_el_detector_encuentra_una_comparacion_de_rol(codigo):
    assert comparaciones_de_rol(codigo) == [1]


def test_el_detector_no_marca_el_uso_de_tiene_permiso():
    assert comparaciones_de_rol("if tiene_permiso(usuario, Permiso.EVENTO_CREAR): pass") == []


def test_la_lista_de_archivos_que_se_recorre_no_esta_vacia():
    assert archivos_a_revisar()
    assert {c.name for c in CARPETAS} <= {p.parent.name for p in archivos_a_revisar()}


def test_ningun_servicio_ni_endpoint_compara_el_rol():
    violaciones = {
        str(p.relative_to(APP)): lineas
        for p in archivos_a_revisar()
        if (lineas := comparaciones_de_rol(p.read_text(encoding="utf-8")))
    }

    assert violaciones == {}, "Usá tiene_permiso(usuario, Permiso.X) en lugar de comparar el rol"
