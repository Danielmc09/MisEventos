"""Reglas de horario que no dependen de la base."""

from datetime import datetime


def se_cruzan(a_inicio: datetime, a_fin: datetime, b_inicio: datetime, b_fin: datetime) -> bool:
    """Intervalos semiabiertos `[inicio, fin)`: terminar a las 10 y empezar a las 10 no es cruce."""
    return a_inicio < b_fin and b_inicio < a_fin
