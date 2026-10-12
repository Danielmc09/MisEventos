"""La suite corre con la versión de Python que fija el proyecto: otra versión puede aceptar sintaxis
o APIs que la imagen de producción no tiene."""

import sys


def test_la_suite_corre_con_python_3_12():
    assert sys.version_info[:2] == (3, 12)
