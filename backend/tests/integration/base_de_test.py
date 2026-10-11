from collections.abc import Mapping

from sqlalchemy.engine import URL, make_url


def url_de_test(entorno: Mapping[str, str]) -> URL:
    return make_url(entorno.get("DATABASE_URL") or "postgresql://")
