import pytest

from app.repositories.eventos import escapar_like


@pytest.mark.parametrize(
    ("texto", "escapado"),
    [
        ("100%", "100\\%"),
        ("mi_evento", "mi\\_evento"),
        ("a\\b", "a\\\\b"),
        ("%_\\", "\\%\\_\\\\"),
        ("' OR 1=1 --", "' OR 1=1 --"),
        ("PyCon Bogotá", "PyCon Bogotá"),
    ],
)
def test_el_escape_vuelve_literales_los_comodines_y_la_barra(texto, escapado):
    assert escapar_like(texto) == escapado
