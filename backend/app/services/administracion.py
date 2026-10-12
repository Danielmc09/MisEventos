"""Gestión de usuarios por el administrador: crearlos, listarlos y cambiarles el nombre, el
email, el rol o el estado.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.contrasenas import generar_contrasena_temporal, hashear
from app.core.excepciones import Conflict, Forbidden, NotFound
from app.core.permisos import PERMISOS_POR_ROL, Permiso, Rol, tiene_permiso
from app.models.usuario import User
from app.schemas.administracion import FiltrosUsuarios, UsuarioAlta, UsuarioEdicion

# Lo que no puede quedarse sin nadie: alguien activo que gestione usuarios.
PERMISO_DE_ADMIN = Permiso.USUARIOS_GESTIONAR
ROLES_ADMIN = frozenset(
    r for r, permisos in PERMISOS_POR_ROL.items() if PERMISO_DE_ADMIN in permisos
)


class Usuarios(Protocol):
    def buscar(
        self, filtros: FiltrosUsuarios, offset: int, limite: int
    ) -> tuple[list[User], int]: ...
    def inscripciones_activas(self, ids_usuario: list[UUID]) -> dict[UUID, int]: ...
    def activos_para_escribir(self, roles: Collection[Rol]) -> list[User]: ...
    def por_id_para_escribir(self, id_usuario: UUID) -> User | None: ...
    def guardar(self, usuario: User) -> User | None: ...


@dataclass(frozen=True)
class ConInscripciones:
    """Un usuario con sus inscripciones activas."""

    usuario: User
    inscripciones_activas: int


def _exigir_permiso(actor: User) -> None:
    if not tiene_permiso(actor, PERMISO_DE_ADMIN):
        raise Forbidden()


def listar(
    repo: Usuarios, actor: User, filtros: FiltrosUsuarios, offset: int, limite: int
) -> tuple[list[ConInscripciones], int]:
    """Una página de usuarios con el total. Las inscripciones de toda la página salen de una
    sola consulta, no de una por usuario."""
    _exigir_permiso(actor)
    usuarios, total = repo.buscar(filtros, offset, limite)
    activas = repo.inscripciones_activas([u.id for u in usuarios])
    return [ConInscripciones(u, activas[u.id]) for u in usuarios], total


@dataclass(frozen=True)
class _ConRol:
    role: Rol


def _es_admin_activo(role: Rol, activo: bool) -> bool:
    return activo and tiene_permiso(_ConRol(role), PERMISO_DE_ADMIN)


def cambiar(
    repo: Usuarios, actor: User, id_usuario: UUID, datos: UsuarioEdicion
) -> ConInscripciones:
    """Cambia el nombre, el email, el rol o el estado de un usuario. El propio nombre y el propio
    email sí se los cambia.

    El orden importa: primero el permiso (sin él, 403 aunque el usuario no exista), después que
    no se toque a sí mismo, y recién ahí se bloquean, en orden de id, TODOS los admins activos.
    Con ellos bloqueados se lee el usuario y se cuenta: si dos admins se degradan mutuamente a
    la vez, el segundo espera al primero y ve que ya queda uno solo (`last-admin`).

    El permiso se vuelve a mirar con los admins bloqueados: si mientras esperaba otro admin lo
    degradó o lo desactivó, el actor ya no está entre ellos y no cambia nada (403). El
    `last-admin` va antes, porque es lo que explica por qué no se hizo el cambio.

    Un email que ya usa otro usuario lo rechaza el índice único al guardar (`email-taken`): así
    pierde también el segundo de dos cambios simultáneos al mismo email."""
    _exigir_permiso(actor)
    cambios = datos.model_dump(exclude_unset=True)
    if id_usuario == actor.id and cambios.keys() & {"role", "is_active"}:
        raise Conflict(
            tipo="cannot-modify-self",
            titulo="No podés cambiarte el rol ni desactivarte a vos mismo",
        )
    admins = repo.activos_para_escribir(ROLES_ADMIN)
    usuario = repo.por_id_para_escribir(id_usuario)
    if usuario is not None:
        era_admin = _es_admin_activo(usuario.role, usuario.is_active)
        sera_admin = _es_admin_activo(
            cambios.get("role", usuario.role), cambios.get("is_active", usuario.is_active)
        )
        if era_admin and not sera_admin and not any(a.id != usuario.id for a in admins):
            raise Conflict(
                tipo="last-admin",
                titulo="Tiene que quedar al menos un administrador activo",
            )
    if not any(a.id == actor.id for a in admins):
        raise Forbidden()
    if usuario is None:
        raise NotFound()
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    guardado = repo.guardar(usuario)
    if guardado is None:
        raise _email_tomado()
    usuario = guardado
    return ConInscripciones(usuario, repo.inscripciones_activas([usuario.id])[usuario.id])


@dataclass(frozen=True)
class ConContrasenaTemporal:
    """Un usuario y la contraseña temporal que se le acaba de dar, en claro: solo vive en la
    respuesta, nunca en la base ni en un log."""

    usuario: User
    contrasena_temporal: str


def _email_tomado() -> Conflict:
    return Conflict(tipo="email-taken", titulo="Ese email ya está registrado")


def crear(repo: Usuarios, actor: User, datos: UsuarioAlta) -> ConContrasenaTemporal:
    """Crea un usuario con el rol que indica el admin y una contraseña temporal que genera el
    sistema; en su primer login tiene que cambiarla.

    El email tomado lo decide el índice único al guardar (`email-taken`), así que también pierde
    el segundo de dos altas simultáneas con el mismo email."""
    _exigir_permiso(actor)
    temporal = generar_contrasena_temporal()
    usuario = User(
        email=datos.email,
        full_name=datos.full_name,
        role=datos.role,
        password_hash=hashear(temporal),
        must_change_password=True,
    )
    guardado = repo.guardar(usuario)
    if guardado is None:
        raise _email_tomado()
    return ConContrasenaTemporal(guardado, temporal)


def restablecer_contrasena(repo: Usuarios, actor: User, id_usuario: UUID) -> str:
    return ""
