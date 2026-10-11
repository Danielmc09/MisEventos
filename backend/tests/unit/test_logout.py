from uuid import uuid4

import pytest

from app.core.tokens import crear_access_token
from tests.unit.dobles import RepositorioUsuariosFalso


@pytest.mark.parametrize("token", ["valido", "invalido", None])
def test_logout_responde_204_con_token_o_sin_el(con_repo, cliente, settings, token):
    con_repo(RepositorioUsuariosFalso())
    tokens = {"valido": crear_access_token(uuid4(), settings.jwt_secret, 5), "invalido": "x.y.z"}
    headers = {"Authorization": f"Bearer {tokens[token]}"} if token else {}

    respuesta = cliente.post("/auth/logout", headers=headers)

    assert respuesta.status_code == 204
    assert respuesta.content == b""
