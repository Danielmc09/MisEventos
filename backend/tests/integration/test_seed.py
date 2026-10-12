import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.scripts.seed import CredencialesDemo, sembrar

pytestmark = pytest.mark.integration

DEMO = CredencialesDemo(
    admin_email="admin@miseventos.local",
    admin_password="Admin-Test-2026",
    demo_password="Demo-Test-2026",
)
ROLES = {
    "admin@miseventos.local": "ADMIN",
    "organizador@miseventos.local": "ORGANIZER",
    "asistente@miseventos.local": "ATTENDEE",
}
CONTRASENAS = {
    "admin@miseventos.local": "Admin-Test-2026",
    "organizador@miseventos.local": "Demo-Test-2026",
    "asistente@miseventos.local": "Demo-Test-2026",
}


def correr_seed(conexion) -> None:
    """Como el script: una transacción con commit, que acá queda en un savepoint del test."""
    with Session(bind=conexion, join_transaction_mode="create_savepoint") as session:
        sembrar(session, DEMO)
        session.commit()


def usuarios_demo(conexion) -> list[tuple[str, str]]:
    return conexion.execute(
        text("SELECT lower(email), role FROM users WHERE lower(email) = ANY(:emails)"),
        {"emails": list(ROLES)},
    ).all()


def login(cliente, email: str, password: str):
    return cliente.post("/auth/login", data={"username": email, "password": password})


def test_correr_el_seed_dos_veces_deja_exactamente_los_tres_usuarios_demo(conexion):
    correr_seed(conexion)
    correr_seed(conexion)

    filas = usuarios_demo(conexion)
    assert len(filas) == 3
    assert {email: str(rol) for email, rol in filas} == ROLES


def test_los_usuarios_demo_hacen_login_sin_cambio_obligatorio(cliente_db, conexion):
    correr_seed(conexion)

    for email, password in CONTRASENAS.items():
        respuesta = login(cliente_db, email, password)
        assert respuesta.status_code == 200, email
        token = respuesta.json()["access_token"]
        perfil = cliente_db.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert perfil.status_code == 200, email
        assert perfil.json()["role"] == ROLES[email]
        assert perfil.json()["must_change_password"] is False
        assert perfil.json()["is_active"] is True


def test_cada_usuario_demo_ve_su_nombre_en_el_perfil(cliente_db, conexion):
    correr_seed(conexion)

    nombres = {}
    for email, password in CONTRASENAS.items():
        token = login(cliente_db, email, password).json()["access_token"]
        perfil = cliente_db.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        nombres[email] = perfil.json()["full_name"]

    assert nombres == {
        "admin@miseventos.local": "Ana Administradora",
        "organizador@miseventos.local": "Oscar Organizador",
        "asistente@miseventos.local": "Andrea Asistente",
    }


def test_completa_el_nombre_del_demo_que_existe_sin_nombre_y_respeta_el_que_tiene(conexion):
    # SQL directo: usuarios demo de antes de que el seed les pusiera nombre.
    for email, rol, nombre in [
        ("admin@miseventos.local", "ADMIN", None),
        ("organizador@miseventos.local", "ORGANIZER", "Otro Nombre"),
    ]:
        conexion.execute(
            text(
                "INSERT INTO users (email, password_hash, role, full_name)"
                " VALUES (:email, '$argon2id$x', :rol, :nombre)"
            ),
            {"email": email, "rol": rol, "nombre": nombre},
        )

    correr_seed(conexion)

    filas = conexion.execute(
        text(
            "SELECT lower(email), full_name, password_hash FROM users"
            " WHERE lower(email) = ANY(:emails)"
        ),
        {"emails": list(ROLES)},
    ).all()
    por_email = {email: (nombre, hash_) for email, nombre, hash_ in filas}
    assert por_email["admin@miseventos.local"] == ("Ana Administradora", "$argon2id$x")
    assert por_email["organizador@miseventos.local"] == ("Otro Nombre", "$argon2id$x")
    assert por_email["asistente@miseventos.local"][0] == "Andrea Asistente"


def test_el_seed_no_restaura_la_contrasena_que_un_usuario_demo_cambio(cliente_db, conexion):
    correr_seed(conexion)
    email, vieja, nueva = "asistente@miseventos.local", "Demo-Test-2026", "Clave-Propia-77"
    primer_login = login(cliente_db, email, vieja)
    assert primer_login.status_code == 200
    token = primer_login.json()["access_token"]
    cambio = cliente_db.patch(
        "/auth/me/password",
        json={"current_password": vieja, "new_password": nueva},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cambio.status_code == 200

    correr_seed(conexion)

    assert login(cliente_db, email, nueva).status_code == 200
    assert login(cliente_db, email, vieja).status_code == 401
    assert len(usuarios_demo(conexion)) == 3


def eventos_demo(conexion) -> list[tuple[str, str]]:
    return conexion.execute(
        text(
            "SELECT e.id, e.name FROM events e JOIN users u ON u.id = e.organizer_id"
            " WHERE lower(u.email) = 'organizador@miseventos.local'"
        )
    ).all()


def test_correr_el_seed_dos_veces_deja_los_mismos_seis_eventos_demo(conexion):
    correr_seed(conexion)
    primera = sorted(eventos_demo(conexion))

    correr_seed(conexion)

    assert len(primera) == 6
    assert sorted(eventos_demo(conexion)) == primera
    assert len(usuarios_demo(conexion)) == 3


def test_los_eventos_demo_se_buscan_y_un_anonimo_no_ve_el_borrador(cliente_db, conexion):
    correr_seed(conexion)

    python = cliente_db.get("/events", params={"q": "python", "page_size": 100})
    borradores = cliente_db.get("/events", params={"status": "DRAFT", "page_size": 100})
    pasados = cliente_db.get("/events", params={"when": "past", "page_size": 100})

    assert python.status_code == borradores.status_code == pasados.status_code == 200
    demo = {nombre for _, nombre in eventos_demo(conexion)}
    assert len([e for e in python.json()["items"] if e["name"] in demo]) >= 2
    assert borradores.json()["total"] == 0
    assert len([e for e in pasados.json()["items"] if e["name"] in demo]) == 1


def sesiones_y_ponentes_demo(conexion) -> tuple[list, list, list]:
    ponentes = conexion.execute(
        text(
            "SELECT s.id FROM speakers s JOIN users u ON u.id = s.created_by"
            " WHERE lower(u.email) = 'organizador@miseventos.local'"
        )
    ).all()
    sesiones = conexion.execute(
        text(
            "SELECT se.id FROM sessions se JOIN events e ON e.id = se.event_id"
            " JOIN users u ON u.id = e.organizer_id"
            " WHERE lower(u.email) = 'organizador@miseventos.local'"
        )
    ).all()
    vinculos = conexion.execute(
        text(
            "SELECT ss.session_id, ss.speaker_id FROM session_speakers ss"
            " JOIN sessions se ON se.id = ss.session_id JOIN events e ON e.id = se.event_id"
            " JOIN users u ON u.id = e.organizer_id"
            " WHERE lower(u.email) = 'organizador@miseventos.local'"
        )
    ).all()
    return sorted(ponentes), sorted(sesiones), sorted(vinculos)


def test_correr_el_seed_dos_veces_no_duplica_ponentes_sesiones_ni_asignaciones(conexion):
    correr_seed(conexion)
    primera = sesiones_y_ponentes_demo(conexion)

    correr_seed(conexion)

    ponentes, sesiones, vinculos = primera
    assert len(ponentes) >= 3 and len(sesiones) >= 3 and len(vinculos) >= 4
    assert sesiones_y_ponentes_demo(conexion) == primera


def test_un_anonimo_ve_las_sesiones_demo_de_python_day_con_sus_ponentes_sin_email(
    cliente_db, conexion
):
    correr_seed(conexion)
    (id_evento,) = conexion.execute(
        text(
            "SELECT e.id FROM events e JOIN users u ON u.id = e.organizer_id"
            " WHERE e.name = :nombre AND lower(u.email) = 'organizador@miseventos.local'"
        ),
        {"nombre": "Python Day Medellín"},
    ).one()

    respuesta = cliente_db.get(f"/events/{id_evento}/sessions")

    assert respuesta.status_code == 200
    sesiones = respuesta.json()
    assert len(sesiones) >= 3
    assert any(len(s["speakers"]) == 2 for s in sesiones)
    assert all("email" not in p for s in sesiones for p in s["speakers"])
    salas = {s["room"] for s in sesiones if s["room"]}
    assert len(salas) >= 2
