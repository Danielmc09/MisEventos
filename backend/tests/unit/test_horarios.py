from datetime import UTC, datetime

import pytest

from app.core.horarios import se_cruzan


def h(hora: int) -> datetime:
    return datetime(2030, 1, 10, hora, tzinfo=UTC)


@pytest.mark.parametrize(
    ("a", "b", "cruzan"),
    [
        ((9, 10), (10, 11), False),
        ((10, 11), (9, 10), False),
        ((9, 10), (11, 12), False),
        ((9, 11), (10, 12), True),
        ((10, 12), (9, 11), True),
        ((9, 12), (10, 11), True),
        ((10, 11), (9, 12), True),
        ((9, 10), (9, 10), True),
    ],
    ids=[
        "termina-cuando-empieza-la-otra",
        "empieza-cuando-termina-la-otra",
        "separadas",
        "se-solapan",
        "se-solapan-al-reves",
        "contiene-a-la-otra",
        "contenida-en-la-otra",
        "iguales",
    ],
)
def test_dos_intervalos_se_cruzan_solo_si_se_solapan(a, b, cruzan):
    assert se_cruzan(h(a[0]), h(a[1]), h(b[0]), h(b[1])) is cruzan
