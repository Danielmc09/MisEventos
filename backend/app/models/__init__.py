from sqlmodel import SQLModel

# Nombres estables para constraints e índices: sin ellos, cada migración inventa los suyos y
# un downgrade no sabe qué borrar. Se aplica antes de que se importe cualquier modelo.
CONVENCION_DE_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

SQLModel.metadata.naming_convention = CONVENCION_DE_NOMBRES

# Los modelos se registran en la metadata después de fijar la convención.
from app.models.evento import Event  # noqa: E402
from app.models.inscripcion import Registration  # noqa: E402
from app.models.ponente import Speaker  # noqa: E402
from app.models.sesion import Session, SessionSpeaker  # noqa: E402
from app.models.usuario import User  # noqa: E402

__all__ = [
    "CONVENCION_DE_NOMBRES",
    "Event",
    "Registration",
    "Session",
    "SessionSpeaker",
    "Speaker",
    "User",
]
