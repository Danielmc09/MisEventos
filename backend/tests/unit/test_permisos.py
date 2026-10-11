from types import SimpleNamespace

import pytest

from app.core.permisos import PERMISOS_POR_ROL, Permiso, Rol, tiene_permiso

ESPERADO = {
    Rol.ATTENDEE: set(),
    Rol.ORGANIZER: {Permiso.EVENTO_CREAR},
    Rol.ADMIN: {
        Permiso.EVENTO_CREAR,
        Permiso.EVENTO_GESTIONAR_TODOS,
        Permiso.USUARIOS_GESTIONAR,
        Permiso.AUDITORIA_VER,
    },
}


def test_los_permisos_tienen_los_identificadores_de_la_tabla():
    assert {p.value for p in Permiso} == {
        "evento:crear",
        "evento:gestionar_todos",
        "usuarios:gestionar",
        "auditoria:ver",
    }


def test_el_mapa_da_a_cada_rol_exactamente_sus_permisos():
    assert {rol: set(permisos) for rol, permisos in PERMISOS_POR_ROL.items()} == ESPERADO


@pytest.mark.parametrize("rol", list(Rol))
@pytest.mark.parametrize("permiso", list(Permiso))
def test_tiene_permiso_responde_segun_el_mapa(rol, permiso):
    usuario = SimpleNamespace(role=rol)

    assert tiene_permiso(usuario, permiso) is (permiso in ESPERADO[rol])
