"""Los mensajes que llevan una cantidad hablan en singular con 1 y en plural con cualquier otra."""

import pytest

from app.core.textos import plural


@pytest.mark.parametrize(
    ("cantidad", "esperado"),
    [(0, "0 personas"), (1, "1 persona"), (2, "2 personas")],
)
def test_plural_usa_el_singular_solo_con_uno(cantidad, esperado):
    assert plural(cantidad, "persona", "personas") == esperado
