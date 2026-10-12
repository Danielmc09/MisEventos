import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.contrasenas import hashear, verificar
from app.core.permisos import Rol
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion
from app.models.usuario import User
from app.scripts import seed
from app.scripts.seed import (
    CredencialesDemo,
    credenciales_demo,
    sembrar_eventos,
    sembrar_inscripciones,
    sembrar_ponentes,
    sembrar_sesiones,
    sembrar_usuarios,
)
from tests.unit.dobles import (
    RepositorioEventosFalso,
    RepositorioInscripcionesFalso,
    RepositorioPonentesFalso,
    RepositorioSesionesFalso,
    RepositorioUsuariosFalso,
)

CREDENCIALES = {
    "ADMIN_EMAIL": "admin@miseventos.local",
    "ADMIN_PASSWORD": "Admin-Demo-2026",
    "DEMO_PASSWORD": "Demo-Local-2026",
}
BASE = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/x",
    "JWT_SECRET": "s" * 32,
}


def settings(**valores: str) -> Settings:
    return Settings(_env_file=None, **BASE, **valores)


def test_con_las_tres_variables_devuelve_las_credenciales():
    assert credenciales_demo(settings(**CREDENCIALES)) == CredencialesDemo(
        admin_email="admin@miseventos.local",
        admin_password="Admin-Demo-2026",
        demo_password="Demo-Local-2026",
    )


@pytest.mark.parametrize("falta", sorted(CREDENCIALES))
def test_sin_una_variable_el_seed_falla_nombrandola(falta):
    valores = {k: v for k, v in CREDENCIALES.items() if k != falta}

    with pytest.raises(RuntimeError, match=falta):
        credenciales_demo(settings(**valores))


def test_un_valor_vacio_cuenta_como_faltante():
    with pytest.raises(RuntimeError, match="DEMO_PASSWORD"):
        credenciales_demo(settings(**{**CREDENCIALES, "DEMO_PASSWORD": ""}))


def test_si_faltan_varias_las_nombra_a_todas():
    with pytest.raises(RuntimeError) as error:
        credenciales_demo(settings(ADMIN_EMAIL="admin@miseventos.local"))

    assert "ADMIN_PASSWORD" in str(error.value)
    assert "DEMO_PASSWORD" in str(error.value)


class SesionDoble:
    def __init__(self) -> None:
        self.llamadas: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.llamadas.append("close")

    def commit(self):
        self.llamadas.append("commit")

    def rollback(self):
        self.llamadas.append("rollback")


@pytest.fixture
def entorno(monkeypatch):
    for clave in [*CREDENCIALES, *BASE, "SEED_DEMO", "ENV"]:
        monkeypatch.delenv(clave, raising=False)
    monkeypatch.chdir("/")  # sin .env alrededor

    def armar(**valores: str) -> None:
        for clave, valor in {**BASE, **valores}.items():
            monkeypatch.setenv(clave, valor)

    return armar


@pytest.fixture
def base_doble(monkeypatch):
    """Reemplaza la conexión real; registra qué sesiones se pidieron y qué se sembró."""
    registro = {"sesiones": [], "sembrado": []}

    def fabrica(url):
        def nueva():
            sesion = SesionDoble()
            registro["sesiones"].append(sesion)
            return sesion

        return nueva

    monkeypatch.setattr(seed, "crear_fabrica_de_sesiones", fabrica, raising=False)
    monkeypatch.setattr(seed, "sembrar", lambda s, c: registro["sembrado"].append(c))
    return registro


def test_main_siembra_en_una_transaccion_y_la_confirma(entorno, base_doble):
    entorno(**CREDENCIALES)

    seed.main([])

    assert [c.admin_email for c in base_doble["sembrado"]] == ["admin@miseventos.local"]
    assert [s.llamadas for s in base_doble["sesiones"]] == [["commit", "close"]]


def test_main_sin_credenciales_termina_con_un_mensaje_que_nombra_la_variable(entorno, base_doble):
    entorno(ADMIN_EMAIL="admin@miseventos.local", ADMIN_PASSWORD="x")

    with pytest.raises(SystemExit) as salida:
        seed.main([])

    assert "DEMO_PASSWORD" in str(salida.value.code)
    assert base_doble["sesiones"] == []


def test_al_arrancar_sin_seed_demo_no_hace_nada_ni_pide_credenciales(entorno, base_doble):
    entorno(SEED_DEMO="false")

    seed.main(["--solo-si-seed-demo"])

    assert base_doble["sesiones"] == []


def test_al_arrancar_con_seed_demo_siembra(entorno, base_doble):
    entorno(SEED_DEMO="true", **CREDENCIALES)

    seed.main(["--solo-si-seed-demo"])

    assert len(base_doble["sembrado"]) == 1


# --- Usuarios demo -------------------------------------------------------------------------

DEMO = CredencialesDemo(
    admin_email="Admin@MisEventos.local",
    admin_password="Admin-Test-2026",
    demo_password="Demo-Test-2026",
)


def test_crea_el_admin_y_los_dos_usuarios_demo_con_sus_roles():
    repo = RepositorioUsuariosFalso()

    sembrar_usuarios(repo, DEMO)

    assert len(repo.creados) == 3
    por_email = {u.email: u for u in repo.creados}
    assert {email: u.role for email, u in por_email.items()} == {
        "admin@miseventos.local": Rol.ADMIN,
        "organizador@miseventos.local": Rol.ORGANIZER,
        "asistente@miseventos.local": Rol.ATTENDEE,
    }
    assert all(u.is_active and not u.must_change_password for u in repo.creados)
    assert verificar(por_email["admin@miseventos.local"].password_hash, "Admin-Test-2026")
    assert verificar(por_email["organizador@miseventos.local"].password_hash, "Demo-Test-2026")
    assert verificar(por_email["asistente@miseventos.local"].password_hash, "Demo-Test-2026")


def test_crea_a_cada_usuario_demo_con_su_nombre():
    repo = RepositorioUsuariosFalso()

    sembrar_usuarios(repo, DEMO)

    assert {u.email: u.full_name for u in repo.creados} == {
        "admin@miseventos.local": "Ana Administradora",
        "organizador@miseventos.local": "Oscar Organizador",
        "asistente@miseventos.local": "Andrea Asistente",
    }


def test_no_toca_un_usuario_que_ya_existe_aunque_cambio_su_contrasena():
    hash_propio = hashear("Clave-Propia-1")
    admin = User(email="admin@miseventos.local", password_hash=hash_propio, role=Rol.ADMIN)
    asistente = User(
        email="asistente@miseventos.local",
        password_hash=hash_propio,
        role=Rol.ATTENDEE,
        full_name="Nombre que puso la persona",
    )
    repo = RepositorioUsuariosFalso(admin, asistente)

    sembrar_usuarios(repo, DEMO)

    assert [u.email for u in repo.creados] == ["organizador@miseventos.local"]
    assert admin.password_hash == asistente.password_hash == hash_propio
    assert asistente.full_name == "Nombre que puso la persona"
    assert len(repo.usuarios) == 3


@pytest.mark.parametrize("sin_nombre", [None, ""])
def test_completa_el_nombre_de_un_usuario_demo_que_existe_sin_nombre(sin_nombre):
    hash_propio = hashear("Clave-Propia-1")
    admin = User(
        email="admin@miseventos.local",
        password_hash=hash_propio,
        role=Rol.ADMIN,
        full_name=sin_nombre,
    )
    organizador = User(
        email="organizador@miseventos.local",
        password_hash=hash_propio,
        role=Rol.ORGANIZER,
        full_name="Otro Nombre",
    )
    repo = RepositorioUsuariosFalso(admin, organizador)

    sembrar_usuarios(repo, DEMO)

    assert admin.full_name == "Ana Administradora"
    assert organizador.full_name == "Otro Nombre"
    assert admin.password_hash == organizador.password_hash == hash_propio
    assert (admin.email, admin.role) == ("admin@miseventos.local", Rol.ADMIN)
    assert [u.email for u in repo.creados] == ["asistente@miseventos.local"]


def test_correrlo_dos_veces_no_crea_nada_la_segunda():
    repo = RepositorioUsuariosFalso()
    sembrar_usuarios(repo, DEMO)

    sembrar_usuarios(repo, DEMO)

    assert len(repo.creados) == 3


# --- Eventos demo --------------------------------------------------------------------------

ORGANIZADOR_DEMO = User(
    email="organizador@miseventos.local", password_hash="$argon2id$x", role=Rol.ORGANIZER
)
ORGANIZADOR_AJENO = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)


def test_crea_los_seis_eventos_demo_a_nombre_del_organizador():
    eventos = RepositorioEventosFalso()
    ahora = datetime.now(UTC)

    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), eventos)

    demo = list(eventos.eventos.values())
    assert len(demo) == 6
    assert len({e.name for e in demo}) == 6
    assert all(e.organizer_id == ORGANIZADOR_DEMO.id for e in demo)
    assert all(e.end_at > e.start_at for e in demo)
    terminados = [e for e in demo if e.end_at < ahora]
    vigentes = [e for e in demo if e.end_at >= ahora]
    assert len(terminados) == 1
    assert all(e.start_at > ahora for e in vigentes)
    estados = sorted(e.status for e in vigentes)
    assert estados == sorted(
        [EstadoEvento.PUBLISHED] * 3 + [EstadoEvento.DRAFT, EstadoEvento.CANCELLED]
    )
    casi_lleno = [e for e in vigentes if e.status == EstadoEvento.PUBLISHED and e.capacity == 10]
    assert len(casi_lleno) == 1


def test_al_menos_dos_eventos_demo_dicen_python_con_distintas_mayusculas():
    eventos = RepositorioEventosFalso()

    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), eventos)

    con_python = [e.name for e in eventos.eventos.values() if "python" in e.name.lower()]
    assert len(con_python) >= 2
    escrituras = {n[n.lower().index("python") :][:6] for n in con_python}
    assert len(escrituras) >= 2


def test_no_toca_un_evento_demo_que_ya_existe_y_crea_los_que_faltan():
    eventos = RepositorioEventosFalso()
    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), eventos)
    assert len(eventos.eventos) == 6
    editado = next(iter(eventos.eventos.values()))
    editado.capacity = 999
    borrado = list(eventos.eventos.values())[-1]
    eventos.eliminar(borrado)

    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), eventos)

    assert len(eventos.eventos) == 6
    assert eventos.eventos[editado.id].capacity == 999
    assert borrado.name in {e.name for e in eventos.eventos.values()}


def test_correrlo_dos_veces_deja_los_mismos_seis_eventos():
    eventos = RepositorioEventosFalso()
    usuarios = RepositorioUsuariosFalso(ORGANIZADOR_DEMO)
    sembrar_eventos(usuarios, eventos)
    ids = set(eventos.eventos)

    sembrar_eventos(usuarios, eventos)

    assert len(ids) == 6
    assert set(eventos.eventos) == ids


def test_un_evento_de_otro_organizador_con_el_mismo_nombre_no_cuenta_como_demo():
    eventos = RepositorioEventosFalso()
    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), eventos)
    nombres = [e.name for e in eventos.eventos.values()]
    otro = RepositorioEventosFalso()
    inicio = datetime.now(UTC) + timedelta(days=5)
    for nombre in nombres:
        otro.crear(
            Event(
                name=nombre,
                start_at=inicio,
                end_at=inicio + timedelta(hours=1),
                capacity=5,
                organizer_id=ORGANIZADOR_AJENO.id,
            )
        )

    sembrar_eventos(RepositorioUsuariosFalso(ORGANIZADOR_DEMO), otro)

    assert len(otro.eventos) == 12


def test_sin_el_organizador_demo_falla_nombrandolo():
    with pytest.raises(RuntimeError, match="organizador@miseventos.local"):
        sembrar_eventos(RepositorioUsuariosFalso(), RepositorioEventosFalso())


# --- Ponentes y sesiones demo --------------------------------------------------------------


class Demo:
    """Los dobles de una base con lo que el seed deja: usuarios, eventos, ponentes y sesiones."""

    def __init__(self) -> None:
        self.usuarios = RepositorioUsuariosFalso(ORGANIZADOR_DEMO)
        self.eventos = RepositorioEventosFalso()
        self.ponentes = RepositorioPonentesFalso()
        self.sesiones = RepositorioSesionesFalso(self.eventos, self.ponentes)
        sembrar_eventos(self.usuarios, self.eventos)

    def sembrar(self) -> None:
        sembrar_ponentes(self.usuarios, self.ponentes)
        sembrar_sesiones(self.usuarios, self.eventos, self.sesiones, self.ponentes)

    def evento(self, nombre: str) -> Event:
        return next(e for e in self.eventos.eventos.values() if e.name == nombre)

    def sesiones_de(self, nombre: str):
        return self.eventos.sesiones_de(self.evento(nombre).id)

    def vinculos(self) -> set[tuple]:
        return {(s, p) for s, ps in self.sesiones.vinculos.items() for p in ps}


@pytest.fixture
def demo() -> Demo:
    base = Demo()
    base.sembrar()
    return base


def test_crea_ponentes_demo_con_email_a_nombre_del_organizador(demo):
    ponentes = list(demo.ponentes.ponentes.values())

    assert len(ponentes) >= 3
    assert all(p.created_by == ORGANIZADOR_DEMO.id for p in ponentes)
    assert all(p.email and "@" in p.email for p in ponentes)
    assert len({p.email.lower() for p in ponentes}) == len(ponentes)


def test_python_day_tiene_dos_sesiones_paralelas_en_salas_distintas(demo):
    sesiones = demo.sesiones_de("Python Day Medellín")

    paralelas = [
        (a, b)
        for i, a in enumerate(sesiones)
        for b in sesiones[i + 1 :]
        if a.start_at < b.end_at and b.start_at < a.end_at
    ]
    assert paralelas
    assert all(a.room and b.room for a, b in paralelas)
    assert all(a.room.strip().lower() != b.room.strip().lower() for a, b in paralelas)


def test_python_day_tiene_una_sesion_con_dos_ponentes(demo):
    sesiones = demo.sesiones_de("Python Day Medellín")

    cuantos = [len(demo.sesiones.vinculos.get(s.id, [])) for s in sesiones]
    assert 2 in cuantos


def test_un_ponente_participa_en_dos_eventos_demo(demo):
    eventos_de: dict = {}
    for id_sesion, ids in demo.sesiones.vinculos.items():
        evento = demo.eventos.sesiones[id_sesion].event_id
        for id_ponente in ids:
            eventos_de.setdefault(id_ponente, set()).add(evento)

    assert any(len(eventos) >= 2 for eventos in eventos_de.values())


def test_las_sesiones_demo_respetan_las_reglas_de_horario(demo):
    sesiones = list(demo.eventos.sesiones.values())
    assert sesiones
    for s in sesiones:
        evento = demo.eventos.eventos[s.event_id]
        assert evento.start_at <= s.start_at < s.end_at <= evento.end_at, s.title
        assert s.capacity is None or s.capacity <= evento.capacity, s.title

    def cruzan(a, b):
        return a.start_at < b.end_at and b.start_at < a.end_at

    pares = [(a, b) for i, a in enumerate(sesiones) for b in sesiones[i + 1 :] if cruzan(a, b)]
    for a, b in pares:
        ponentes_a = set(demo.sesiones.vinculos.get(a.id, []))
        assert not ponentes_a & set(demo.sesiones.vinculos.get(b.id, [])), (a.title, b.title)
        if a.event_id == b.event_id and a.room and b.room:
            assert a.room.strip().lower() != b.room.strip().lower(), (a.title, b.title)


def test_no_agrega_sesiones_al_taller_ni_toca_las_fechas_o_la_capacidad_de_los_eventos():
    base = Demo()
    antes = {
        e.id: (e.start_at, e.end_at, e.capacity, e.status) for e in base.eventos.eventos.values()
    }

    base.sembrar()

    despues = {
        e.id: (e.start_at, e.end_at, e.capacity, e.status) for e in base.eventos.eventos.values()
    }
    assert despues == antes
    assert base.sesiones_de("Taller de python para principiantes") == []
    assert base.eventos.sesiones


def test_correrlo_dos_veces_no_duplica_ponentes_sesiones_ni_asignaciones(demo):
    ponentes = set(demo.ponentes.ponentes)
    sesiones = set(demo.eventos.sesiones)
    vinculos = demo.vinculos()
    assert ponentes and sesiones and vinculos

    demo.sembrar()

    assert set(demo.ponentes.ponentes) == ponentes
    assert set(demo.eventos.sesiones) == sesiones
    assert demo.vinculos() == vinculos


def test_no_pisa_un_ponente_ni_una_sesion_que_alguien_cambio_y_recrea_lo_borrado(demo):
    assert demo.ponentes.ponentes and demo.eventos.sesiones
    ponente = next(iter(demo.ponentes.ponentes.values()))
    ponente.bio = "Bio que escribió el organizador"
    con_dos = next(s for s, ps in demo.sesiones.vinculos.items() if len(ps) == 2)
    demo.sesiones.vinculos[con_dos] = demo.sesiones.vinculos[con_dos][:1]
    demo.eventos.sesiones[con_dos].room = "Sala que eligió el organizador"
    borrada = next(s for s in demo.eventos.sesiones.values() if s.id != con_dos)
    demo.sesiones.eliminar(borrada)
    total = len(demo.eventos.sesiones) + 1

    demo.sembrar()

    assert ponente.bio == "Bio que escribió el organizador"
    assert len(demo.sesiones.vinculos[con_dos]) == 1
    assert demo.eventos.sesiones[con_dos].room == "Sala que eligió el organizador"
    assert len(demo.eventos.sesiones) == total
    assert borrada.title in {s.title for s in demo.eventos.sesiones.values()}


def test_una_sesion_demo_que_el_organizador_movio_y_dejo_sin_ponentes_no_se_vuelve_a_crear(demo):
    titulos = [s.title for s in demo.sesiones_de("Python Day Medellín")]
    assert titulos
    movida = demo.sesiones_de("Python Day Medellín")[0]
    movida.start_at += timedelta(hours=6)
    movida.end_at += timedelta(hours=6)
    movida.room = None
    demo.sesiones.vinculos[movida.id] = []

    demo.sembrar()

    assert sorted(s.title for s in demo.sesiones_de("Python Day Medellín")) == sorted(titulos)


def test_una_sesion_que_ya_no_entra_en_su_evento_se_saltea_sin_frenar_el_resto():
    base = Demo()
    python_day = base.evento("Python Day Medellín")
    python_day.end_at = python_day.start_at + timedelta(minutes=30)

    base.sembrar()

    assert base.sesiones_de("Python Day Medellín") == []
    assert base.sesiones_de("PyCon Bogotá")
    assert python_day.end_at == python_day.start_at + timedelta(minutes=30)


def test_una_sesion_salteada_deja_un_aviso_que_nombra_la_sesion_y_el_evento(caplog):
    base = Demo()
    python_day = base.evento("Python Day Medellín")
    python_day.end_at = python_day.start_at + timedelta(minutes=30)

    with caplog.at_level(logging.WARNING, logger="miseventos.seed"):
        base.sembrar()

    avisos = [
        r.getMessage()
        for r in caplog.records
        if r.name == "miseventos.seed" and r.levelno == logging.WARNING
    ]
    assert any("Testing en Python" in m and "Python Day Medellín" in m for m in avisos), avisos


# --- Inscripciones demo ----------------------------------------------------------------------

ASISTENTE_DEMO = User(
    email="asistente@miseventos.local", password_hash="$argon2id$x", role=Rol.ATTENDEE
)
CASI_LLENO = "Taller de python para principiantes"


class DemoConInscripciones:
    """Los dobles con los usuarios y los eventos demo ya sembrados, listos para inscribir."""

    def __init__(self) -> None:
        self.usuarios = RepositorioUsuariosFalso(ORGANIZADOR_DEMO, ASISTENTE_DEMO)
        self.eventos = RepositorioEventosFalso()
        self.inscripciones = RepositorioInscripcionesFalso(self.eventos, self.usuarios)
        sembrar_eventos(self.usuarios, self.eventos)

    def sembrar(self) -> None:
        sembrar_inscripciones(self.usuarios, self.eventos, self.inscripciones)

    def evento(self, nombre: str) -> Event:
        return next(e for e in self.eventos.eventos.values() if e.name == nombre)

    def de(self, usuario: User) -> list:
        return [i for i in self.eventos.inscripciones.values() if i.user_id == usuario.id]

    def activas_en(self, nombre: str) -> int:
        evento = self.evento(nombre)
        return self.eventos.inscritos([evento.id])[evento.id]

    def foto(self) -> set[tuple]:
        return {(i.user_id, i.event_id, i.status) for i in self.eventos.inscripciones.values()}


@pytest.fixture
def con_inscripciones() -> DemoConInscripciones:
    base = DemoConInscripciones()
    base.sembrar()
    return base


def test_el_asistente_demo_tiene_dos_inscripciones_activas_y_una_cancelada(con_inscripciones):
    propias = con_inscripciones.de(ASISTENTE_DEMO)

    assert sorted(i.status for i in propias) == [
        EstadoInscripcion.ACTIVE,
        EstadoInscripcion.ACTIVE,
        EstadoInscripcion.CANCELLED,
    ]
    assert len({i.event_id for i in propias}) == 3
    [cancelada] = [i for i in propias if i.status == EstadoInscripcion.CANCELLED]
    assert cancelada.cancelled_at is not None


def test_el_asistente_demo_no_esta_en_el_casi_lleno_para_poder_tomar_el_ultimo_cupo(
    con_inscripciones,
):
    casi_lleno = con_inscripciones.evento(CASI_LLENO)
    propias = con_inscripciones.de(ASISTENTE_DEMO)

    assert propias
    assert all(i.event_id != casi_lleno.id for i in propias)


def test_el_casi_lleno_queda_con_un_solo_cupo_libre(con_inscripciones):
    casi_lleno = con_inscripciones.evento(CASI_LLENO)

    assert casi_lleno.capacity == 10
    assert con_inscripciones.activas_en(CASI_LLENO) == 9


def test_los_inscritos_extra_son_asistentes_con_una_contrasena_que_nadie_conoce(
    con_inscripciones,
):
    extra = [
        u
        for u in con_inscripciones.usuarios.usuarios.values()
        if u.id not in {ORGANIZADOR_DEMO.id, ASISTENTE_DEMO.id}
    ]

    assert len(extra) >= 9
    assert all(u.role == Rol.ATTENDEE for u in extra)
    assert all(u.full_name for u in extra)
    assert all(u.password_hash.startswith("$argon2id$") for u in extra)
    assert len({u.password_hash for u in extra}) == len(extra)
    assert len({u.email for u in extra}) == len(extra)


def test_correrlo_dos_veces_no_duplica_inscripciones_ni_usuarios(con_inscripciones):
    inscripciones = con_inscripciones.foto()
    usuarios = set(con_inscripciones.usuarios.usuarios)
    assert inscripciones

    con_inscripciones.sembrar()

    assert con_inscripciones.foto() == inscripciones
    assert set(con_inscripciones.usuarios.usuarios) == usuarios


def test_no_reactiva_una_inscripcion_que_el_asistente_cancelo(con_inscripciones):
    activas = [
        i for i in con_inscripciones.de(ASISTENTE_DEMO) if i.status == EstadoInscripcion.ACTIVE
    ]
    assert activas
    activa = activas[0]
    activa.status = EstadoInscripcion.CANCELLED

    con_inscripciones.sembrar()

    assert activa.status == EstadoInscripcion.CANCELLED
    assert len(con_inscripciones.de(ASISTENTE_DEMO)) == 3


def test_no_inscribe_mas_alla_del_cupo_si_alguien_achico_el_evento():
    base = DemoConInscripciones()
    base.evento(CASI_LLENO).capacity = 4

    base.sembrar()

    assert base.activas_en(CASI_LLENO) == 4
