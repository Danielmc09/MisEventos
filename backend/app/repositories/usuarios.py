from collections.abc import Collection
from uuid import UUID

from sqlalchemy import ColumnElement, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, or_, select

from app.core.permisos import Rol
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.usuario import User
from app.repositories.eventos import escapar_like
from app.schemas.administracion import FiltrosUsuarios

INDICE_EMAIL = "uq_users_email"


class RepositorioUsuarios:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_email(self, email: str) -> User | None:
        # lower(email) usa el índice único uq_users_email.
        consulta = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.session.exec(consulta).first()

    def por_id(self, id_usuario: UUID) -> User | None:
        return self.session.get(User, id_usuario)

    def buscar(self, filtros: FiltrosUsuarios, offset: int, limite: int) -> tuple[list[User], int]:
        """Una página, por email, y el total. Todo valor del usuario viaja como parámetro ligado."""
        condiciones: list[ColumnElement[bool]] = []
        if filtros.q:
            patron = f"%{escapar_like(filtros.q)}%"
            condiciones.append(
                or_(
                    col(User.email).ilike(patron, escape="\\"),
                    col(User.full_name).ilike(patron, escape="\\"),
                )
            )
        if filtros.rol:
            condiciones.append(col(User.role).in_(sorted(filtros.rol)))
        if filtros.activo is not None:
            condiciones.append(col(User.is_active) == filtros.activo)

        total = self.session.exec(select(func.count()).select_from(User).where(*condiciones)).one()
        consulta = (
            select(User)
            .where(*condiciones)
            .order_by(col(User.email), col(User.id))  # el id desempata: páginas estables
            .offset(offset)
            .limit(limite)
        )
        return list(self.session.exec(consulta).all()), total

    def inscripciones_activas(self, ids_usuario: list[UUID]) -> dict[UUID, int]:
        """Las inscripciones activas de cada usuario, en una sola consulta para todos."""
        por_usuario = dict.fromkeys(ids_usuario, 0)
        if not ids_usuario:
            return por_usuario
        consulta = (
            select(Registration.user_id, func.count())
            .where(
                col(Registration.user_id).in_(ids_usuario),
                Registration.status == EstadoInscripcion.ACTIVE,
            )
            .group_by(col(Registration.user_id))
        )
        for id_usuario, cantidad in self.session.exec(consulta).all():
            por_usuario[id_usuario] = cantidad
        return por_usuario

    def activos_para_escribir(self, roles: Collection[Rol]) -> list[User]:
        """Bloquea, en orden de id, a todos los usuarios activos con esos roles y los relee. El
        orden fijo hace que dos transacciones que bloquean al mismo grupo no se traben entre sí."""
        consulta = (
            select(User)
            .where(col(User.role).in_(list(roles)), col(User.is_active).is_(True))
            .order_by(col(User.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(self.session.exec(consulta).all())

    def por_id_para_escribir(self, id_usuario: UUID) -> User | None:
        """Bloquea la fila y la relee: lo leído antes del bloqueo pudo haber cambiado."""
        consulta = (
            select(User)
            .where(User.id == id_usuario)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.exec(consulta).first()

    def guardar(self, usuario: User) -> User | None:
        """None si el email ya lo usa otro usuario: lo decide el índice único, así que también
        pierde quien llegó segundo en una carrera. El savepoint deja la sesión usable."""
        try:
            with self.session.begin_nested():
                self.session.add(usuario)
                self.session.flush()
        except IntegrityError as error:
            if INDICE_EMAIL not in str(error.orig):
                raise
            return None
        self.session.refresh(usuario)  # updated_at lo pone el trigger
        return usuario

    def crear(self, usuario: User) -> bool:
        """False si el email ya existía: otro registro ganó la carrera contra el índice único."""
        try:
            with self.session.begin_nested():
                self.session.add(usuario)
        except IntegrityError as error:
            if INDICE_EMAIL not in str(error.orig):
                raise
            return False
        return True
