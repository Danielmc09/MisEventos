"""Reglas de horario que no dependen de la base."""

from datetime import datetime


def se_cruzan(a_inicio: datetime, a_fin: datetime, b_inicio: datetime, b_fin: datetime) -> bool:
    return False
