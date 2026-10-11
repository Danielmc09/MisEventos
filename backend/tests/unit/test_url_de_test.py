import pytest

from tests.integration.infraestructura import url_de_test

DESARROLLO = "postgresql+psycopg://miseventos:clave@db:5432/miseventos"


def test_test_database_url_tiene_prioridad():
    url = url_de_test(
        {
            "TEST_DATABASE_URL": "postgresql+psycopg://t:c@ci:5433/otra_test",
            "DATABASE_URL": DESARROLLO,
        }
    )

    assert (url.host, url.port, url.database) == ("ci", 5433, "otra_test")


def test_sin_test_database_url_se_deriva_de_database_url_cambiando_solo_la_base():
    url = url_de_test({"DATABASE_URL": DESARROLLO})

    assert url.database == "miseventos_test"
    assert (url.username, url.password, url.host, url.port) == ("miseventos", "clave", "db", 5432)
    assert url.drivername == "postgresql+psycopg"


def test_sin_ninguna_de_las_dos_falla_nombrandolas():
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL.*DATABASE_URL"):
        url_de_test({})


def test_se_niega_a_usar_una_base_que_no_termina_en_test():
    with pytest.raises(RuntimeError, match="_test"):
        url_de_test({"TEST_DATABASE_URL": DESARROLLO})
