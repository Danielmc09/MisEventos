"""Gestión de usuarios contra PostgreSQL: listado con filtros, cambio de rol y de estado, y las
protecciones para no quedarse sin admin."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import CLAVE, auth, cuerpo_valido, id_de, usuario_con_rol
from tests.integration.test_inscripciones import cancelar, crear_evento, inscribirse

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "ad" + uuid4().hex[:8]


@pytest.fixture
def tokens(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre. El email es `<prefijo><nombre>@mail.com`."""
    roles = {"admin": "ADMIN", "orga": "ORGANIZER", "ana": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def email(prefijo: str, nombre: str) -> str:
    return f"{prefijo}{nombre}@mail.com"


def cambiar(cliente, token: str, id_usuario: str, cuerpo: dict):
    return cliente.patch(f"/admin/users/{id_usuario}", json=cuerpo, headers=auth(token))


def listar(cliente, token: str, **params):
    return cliente.get("/admin/users", params=params, headers=auth(token))


def en_la_base(conexion, id_usuario: str) -> tuple:
    return tuple(
        conexion.execute(
            text("SELECT role, is_active FROM users WHERE id = :id"), {"id": id_usuario}
        ).one()
    )


# --- Permisos ----------------------------------------------------------------------------------


@pytest.mark.parametrize("quien", ["orga", "ana"])
def test_un_organizador_y_un_asistente_reciben_403_en_los_dos_endpoints(
    cliente_db, conexion, tokens, prefijo, quien
):
    id_ana = id_de(conexion, email(prefijo, "ana"))

    listado = listar(cliente_db, tokens[quien])
    cambio = cambiar(cliente_db, tokens[quien], id_ana, {"role": "ADMIN"})

    assert listado.status_code == 403, listado.text
    assert cambio.status_code == 403, cambio.text
    assert en_la_base(conexion, id_ana) == ("ATTENDEE", True)


# --- Listado -----------------------------------------------------------------------------------


def test_el_listado_busca_por_nombre_o_email_y_filtra_por_rol_y_estado(
    cliente_db, conexion, tokens, prefijo
):
    conexion.execute(
        text("UPDATE users SET full_name = :n WHERE email = :e"),
        {"n": f"Beatriz {prefijo} Gómez", "e": email(prefijo, "orga")},
    )
    conexion.execute(
        text("UPDATE users SET is_active = false WHERE email = :e"),
        {"e": email(prefijo, "ana")},
    )
    admin = tokens["admin"]

    def emails(**params) -> list[str]:
        respuesta = listar(cliente_db, admin, **params)
        assert respuesta.status_code == 200, respuesta.text
        return sorted(u["email"] for u in respuesta.json()["items"])

    # Por email (sin distinguir mayúsculas) y por nombre.
    assert emails(q=prefijo.upper()) == sorted(email(prefijo, n) for n in ("admin", "orga", "ana"))
    assert emails(q=f"beatriz {prefijo}") == [email(prefijo, "orga")]
    # Por rol y por estado.
    assert emails(q=prefijo, role="ORGANIZER") == [email(prefijo, "orga")]
    assert emails(q=prefijo, is_active="false") == [email(prefijo, "ana")]
    assert emails(q=prefijo, is_active="true", role="ATTENDEE") == []
    # Los comodines se buscan literalmente.
    assert emails(q=f"{prefijo}%") == []
    assert emails(q=f"{prefijo[:-1]}_") == []


def test_cada_usuario_del_listado_trae_sus_inscripciones_activas(
    cliente_db, conexion, tokens, prefijo
):
    uno = crear_evento(cliente_db, tokens["orga"])
    otro = crear_evento(cliente_db, tokens["orga"])
    assert inscribirse(cliente_db, tokens["ana"], uno).status_code == 201
    assert inscribirse(cliente_db, tokens["ana"], otro).status_code == 201
    assert cancelar(cliente_db, tokens["ana"], otro).status_code == 204

    respuesta = listar(cliente_db, tokens["admin"], q=prefijo)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 3
    por_email = {u["email"]: u for u in cuerpo["items"]}
    assert por_email[email(prefijo, "ana")]["active_registrations"] == 1
    assert por_email[email(prefijo, "orga")]["active_registrations"] == 0
    ana = por_email[email(prefijo, "ana")]
    assert set(ana) == {
        "id",
        "email",
        "full_name",
        "role",
        "is_active",
        "must_change_password",
        "created_at",
        "updated_at",
        "active_registrations",
    }
    assert ana["created_at"].endswith("Z")


# --- Cambiar el rol y el estado -----------------------------------------------------------


def test_un_organizador_pasado_a_asistente_ya_no_crea_eventos_en_su_siguiente_request(
    cliente_db, conexion, tokens, prefijo
):
    id_orga = id_de(conexion, email(prefijo, "orga"))
    antes = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(tokens["orga"]))
    assert antes.status_code == 201, antes.text

    cambio = cambiar(cliente_db, tokens["admin"], id_orga, {"role": "ATTENDEE"})

    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["role"] == "ATTENDEE"
    despues = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(tokens["orga"]))
    assert despues.status_code == 403, despues.text
    assert en_la_base(conexion, id_orga) == ("ATTENDEE", True)


def test_desactivar_corta_el_token_vigente_y_reactivar_deja_volver_a_entrar(
    cliente_db, conexion, tokens, prefijo
):
    id_ana = id_de(conexion, email(prefijo, "ana"))
    assert cliente_db.get("/auth/me", headers=auth(tokens["ana"])).status_code == 200

    desactivado = cambiar(cliente_db, tokens["admin"], id_ana, {"is_active": False})

    assert desactivado.status_code == 200, desactivado.text
    assert en_la_base(conexion, id_ana) == ("ATTENDEE", False)
    assert cliente_db.get("/auth/me", headers=auth(tokens["ana"])).status_code == 401
    login = {"username": email(prefijo, "ana"), "password": CLAVE}
    assert cliente_db.post("/auth/login", data=login).status_code == 401

    reactivado = cambiar(cliente_db, tokens["admin"], id_ana, {"is_active": True})

    assert reactivado.status_code == 200, reactivado.text
    otra_vez = cliente_db.post("/auth/login", data=login)
    assert otra_vez.status_code == 200, otra_vez.text
    nuevo_token = otra_vez.json()["access_token"]
    assert cliente_db.get("/auth/me", headers=auth(nuevo_token)).status_code == 200


def test_cambiar_el_nombre_de_un_usuario_se_ve_en_el_listado(cliente_db, conexion, tokens, prefijo):
    id_ana = id_de(conexion, email(prefijo, "ana"))
    nombre = f"Ana {prefijo} Pérez"

    cambio = cambiar(cliente_db, tokens["admin"], id_ana, {"full_name": nombre})

    assert cambio.status_code == 200, cambio.text
    respuesta = listar(cliente_db, tokens["admin"], q=nombre)
    assert respuesta.status_code == 200, respuesta.text
    [ana] = respuesta.json()["items"]
    assert (ana["id"], ana["full_name"]) == (id_ana, nombre)


@pytest.mark.parametrize("ruta", ["/auth/me", "/me/registrations"])
def test_desactivado_por_el_admin_su_token_vigente_deja_de_servir_en_el_acto(
    cliente_db, conexion, tokens, prefijo, ruta
):
    login = {"username": email(prefijo, "ana"), "password": CLAVE}
    entrada = cliente_db.post("/auth/login", data=login)
    assert entrada.status_code == 200, entrada.text
    token = entrada.json()["access_token"]
    assert cliente_db.get(ruta, headers=auth(token)).status_code == 200

    desactivado = cambiar(
        cliente_db, tokens["admin"], id_de(conexion, email(prefijo, "ana")), {"is_active": False}
    )

    assert desactivado.status_code == 200, desactivado.text
    # El mismo token, todavía vigente: el siguiente request ya no pasa.
    despues = cliente_db.get(ruta, headers=auth(token))
    assert despues.status_code == 401, despues.text
    assert despues.headers["www-authenticate"] == "Bearer"


def test_un_usuario_inexistente_responde_404(cliente_db, tokens):
    respuesta = cambiar(cliente_db, tokens["admin"], str(uuid4()), {"role": "ADMIN"})

    assert respuesta.status_code == 404, respuesta.text


def test_un_patch_con_email_o_contrasena_responde_422_y_no_cambia_nada(
    cliente_db, conexion, tokens, prefijo
):
    id_orga = id_de(conexion, email(prefijo, "orga"))

    for campo, valor in (("email", "otro@mail.com"), ("password", CLAVE)):
        respuesta = cambiar(cliente_db, tokens["admin"], id_orga, {"role": "ADMIN", campo: valor})
        assert respuesta.status_code == 422, respuesta.text

    assert en_la_base(conexion, id_orga) == ("ORGANIZER", True)


# --- Protecciones -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cuerpo",
    [{"role": "ATTENDEE"}, {"role": "ORGANIZER"}, {"is_active": False}],
    ids=["a-asistente", "a-organizador", "desactivarse"],
)
def test_el_admin_no_puede_cambiarse_el_rol_ni_desactivarse(
    cliente_db, conexion, tokens, prefijo, cuerpo
):
    id_admin = id_de(conexion, email(prefijo, "admin"))

    respuesta = cambiar(cliente_db, tokens["admin"], id_admin, cuerpo)

    assert respuesta.status_code == 409, respuesta.text
    problema = respuesta.json()
    assert problema["type"] == "cannot-modify-self"
    assert problema["title"] == "No podés cambiarte el rol ni desactivarte a vos mismo"
    assert en_la_base(conexion, id_admin) == ("ADMIN", True)


def test_con_dos_admins_uno_degrada_al_otro_y_el_que_queda_no_puede_degradarse(
    cliente_db, conexion, tokens, prefijo
):
    otro_token = usuario_con_rol(cliente_db, conexion, email(prefijo, "admin2"), "ADMIN")
    id_admin = id_de(conexion, email(prefijo, "admin"))
    id_otro = id_de(conexion, email(prefijo, "admin2"))

    degradado = cambiar(cliente_db, tokens["admin"], id_otro, {"role": "ORGANIZER"})

    assert degradado.status_code == 200, degradado.text
    assert en_la_base(conexion, id_otro) == ("ORGANIZER", True)
    # El degradado ya no administra.
    assert listar(cliente_db, otro_token).status_code == 403
    a_si_mismo = cambiar(cliente_db, tokens["admin"], id_admin, {"role": "ATTENDEE"})
    assert a_si_mismo.status_code == 409, a_si_mismo.text
    assert a_si_mismo.json()["type"] == "cannot-modify-self"
    assert en_la_base(conexion, id_admin) == ("ADMIN", True)
