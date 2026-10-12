# Mis Eventos · Backend

API REST de Mis Eventos: eventos, sesiones, ponentes, inscripciones y reservas de lugar en sesiones.
FastAPI, SQLModel, PostgreSQL 16 y Alembic.

## Requisitos

- **Con Docker** (lo recomendado): Docker y Docker Compose.
- **Sin Docker:** Python 3.12, Poetry 2.x y PostgreSQL 16.

## Configurar

Toda la configuración sale de variables de entorno y se valida al arrancar
(`backend/app/core/config.py`). Si falta una o es inválida, la API no arranca y el error nombra la
variable. El punto de partida es el `.env.example` de la raíz del repositorio:

```bash
cp .env.example .env
```

Trae valores de demostración que funcionan tal cual, **solo para desarrollo local**. El `.env` real
nunca se sube al repositorio.

| Variable | Ejemplo en `.env.example` | Regla |
|---|---|---|
| `ENV` | `development` | `development` o `production`. Por defecto, `development` |
| `DATABASE_URL` | `postgresql+psycopg://miseventos:demo_local_db@db:5432/miseventos` | Obligatoria. El host `db` es el servicio de Docker Compose |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `miseventos` / `demo_local_db` / `miseventos` | Las usa el contenedor `db` para crear la base. Tienen que coincidir con `DATABASE_URL` |
| `JWT_SECRET` | `demo-local-jwt-secret-solo-para-desarrollo-0001` | Obligatoria, mínimo 32 caracteres |
| `ACCESS_TOKEN_MINUTES` | `60` | Duración del access token. Entero entre 5 y 60; por defecto 60 |
| `REFRESH_TOKEN_DAYS` | `7` | Entero entre 1 y 30. Se valida, pero hoy no se usa: no hay refresh token (ver [Límites conocidos](#límites-conocidos)) |
| `CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos, separados por comas. `*` se rechaza |
| `SEED_DEMO` | `true` | Si es `true`, el contenedor carga los datos de demostración al arrancar. Por defecto, `false` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@miseventos.local` / `Admin-Demo-2026` | El admin que crea el seed |
| `DEMO_PASSWORD` | `Demo-Local-2026` | La contraseña del organizador y del asistente demo |
| `LOG_LEVEL` | `INFO` | `CRITICAL`, `ERROR`, `WARNING`, `INFO` o `DEBUG` |
| `TEST_DATABASE_URL` | (no está) | Solo para los tests de integración. El nombre de la base tiene que terminar en `_test` |
| `VITE_API_URL` | `http://localhost:8000` | Del frontend, se fija al construir su imagen |

**Bloqueo en producción.** Con `ENV=production` la API se niega a arrancar si `JWT_SECRET`,
`ADMIN_PASSWORD`, `DEMO_PASSWORD` o la contraseña de `DATABASE_URL` son los valores de
`.env.example`, o si `SEED_DEMO=true`. El mensaje nombra cada variable rechazada. Así, las
credenciales de demostración no pueden llegar a producción por descuido.

## Ejecutar

### Con Docker

Desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose up --build
```

Al arrancar, el contenedor del backend (`backend/arrancar.sh`) aplica las migraciones, carga los
datos de demostración si `SEED_DEMO=true` y levanta la API en `http://localhost:8000`. Corre sin
root, sin `--reload` y con un healthcheck contra `/health`.

Para volver a correr el seed a mano (es idempotente: crea lo que falta y no restaura lo que alguien
cambió, como una contraseña):

```bash
docker compose exec backend python -m app.scripts.seed
```

Usuarios de demostración, con los valores de `.env.example`:

| Email | Rol | Contraseña |
|---|---|---|
| `admin@miseventos.local` | `ADMIN` | `Admin-Demo-2026` |
| `organizador@miseventos.local` | `ORGANIZER` | `Demo-Local-2026` |
| `asistente@miseventos.local` | `ATTENDEE` | `Demo-Local-2026` |

### Sin Docker

Necesitás un PostgreSQL 16 accesible. El del compose sirve, publicado solo en `127.0.0.1:5432`:

```bash
docker compose up -d db
```

Después, desde `backend/`:

```bash
poetry env use python3.12
poetry install
set -a && . ../.env && set +a
export DATABASE_URL=postgresql+psycopg://miseventos:demo_local_db@localhost:5432/miseventos
poetry run alembic upgrade head
poetry run python -m app.scripts.seed
poetry run uvicorn --factory app.main:create_app --reload
```

- `set -a && . ../.env && set +a` exporta las variables del `.env` de la raíz.
- `DATABASE_URL` se pisa porque fuera de Docker la base está en `localhost`, no en `db`.
- La app se crea con una fábrica (`create_app` en `backend/app/main.py`), por eso va `--factory`.

## Probar

Todos los comandos se corren desde `backend/`.

**Unitarios** (sin base de datos, con dobles de los repositorios):

```bash
poetry run pytest -m "not integration"
```

**Suite completa, unitarios e integración** (necesita PostgreSQL). Los tests de integración usan una
base aparte, `miseventos_test`: la crean si no existe, la migran con Alembic y revierten cada test.
Se niegan a correr contra una base cuyo nombre no termine en `_test`.

```bash
docker compose up -d db
export TEST_DATABASE_URL=postgresql+psycopg://miseventos:demo_local_db@localhost:5432/miseventos_test
poetry run pytest
```

**Cobertura.** Sale con cualquier corrida de pytest: está configurada en `pyproject.toml`
(`--cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=80`). Muestra en la terminal
las líneas sin cubrir, deja el reporte HTML en `backend/htmlcov/index.html` y falla por debajo del
80 %. En CI el HTML se publica como el artefacto `cobertura-backend`.

**Lint y formato:**

```bash
poetry run ruff check .
poetry run ruff format --check .
```

Qué se prueba en cada suite, y por qué la integración va contra Postgres real:
[ADR 0013](../docs/adr/0013-integracion-contra-postgres-real.md).

## Estructura

```
backend/
├── app/
│   ├── main.py          # crea la app: middleware, manejadores de error y routers
│   ├── api/             # routers: solo HTTP (entrada, salida, códigos)
│   ├── services/        # reglas de negocio y permisos; lanzan excepciones de dominio
│   ├── repositories/    # consultas y escrituras; nunca deciden permisos
│   ├── models/          # tablas (SQLModel)
│   ├── schemas/         # entrada y salida de la API
│   ├── core/            # configuración, errores, permisos, contraseñas, tokens, logs
│   └── scripts/seed.py  # datos de demostración
├── alembic/             # migraciones: la única fuente del esquema
├── tests/unit/          # sin base
├── tests/integration/   # contra PostgreSQL
├── arrancar.sh          # migraciones, seed y uvicorn, al arrancar el contenedor
└── Dockerfile
```

**Regla de dependencias:** cada capa usa solo la de abajo, y ninguna importa de una capa superior.

```mermaid
flowchart TD
    Cliente([Cliente HTTP]) --> API["api/ · routers<br/>solo HTTP"]
    API --> SVC["services/ · reglas y permisos<br/>sin HTTP"]
    SVC --> REPO["repositories/ · datos<br/>sin permisos"]
    REPO --> DB[(PostgreSQL)]
    API -. usa .-> CORE["core/ · models/ · schemas/"]
    SVC -. usa .-> CORE
    REPO -. usa .-> CORE
```

- Un router no toca la base: recibe el repositorio inyectado desde `app/api/dependencias.py`.
- Un servicio no conoce HTTP: lanza `NotFound`, `Forbidden`, `Conflict`… y un único manejador las
  convierte en la respuesta de error.
- Un repositorio no decide permisos.
- `tests/unit/test_arquitectura_capas.py` falla si alguna capa importa de una superior.

Más detalle: [ADR 0001](../docs/adr/0001-capas-routers-servicios-repositorios.md).

## API

Con la API levantada, la documentación interactiva (Swagger) está en
**http://localhost:8000/docs**. Cada endpoint declara los errores que puede devolver.

Toda respuesta de error es `application/problem+json` (RFC 9457):

```json
{ "type": "capacity-full", "title": "El evento no tiene cupos", "status": 409,
  "detail": "El evento alcanzó su capacidad de 50 personas.", "trace_id": "8f2c…" }
```

El `trace_id` es el header `X-Request-ID` de la respuesta y aparece en el log del request. Un `422`
agrega `errors: [{"field", "message"}]`. Por qué este formato: [ADR 0003](../docs/adr/0003-errores-rfc-9457.md).

| `type` | Status | Significado |
|---|---|---|
| `bad-request` | 400 | La solicitud no es válida |
| `unauthorized` | 401 | Falta el token, es inválido o venció, o el usuario está desactivado |
| `invalid-credentials` | 401 | Login con email o contraseña incorrectos, o usuario desactivado (el mismo error para los tres casos) |
| `forbidden` | 403 | Sin permiso para la acción |
| `password-change-required` | 403 | El usuario tiene una contraseña temporal sin cambiar: hasta que la cambie, solo puede usar `GET /auth/me`, `PATCH /auth/me/password` y `POST /auth/logout` |
| `not-found` | 404 | No existe, o no lo podés ver: un borrador ajeno responde `404`, no `403` |
| `method-not-allowed` | 405 | Método HTTP no permitido en esa ruta |
| `validation-error` | 422 | Datos inválidos; el detalle por campo va en `errors` |
| `conflict` | 409 | Choque genérico con el estado actual, por ejemplo editar un evento cancelado o finalizado, o sus sesiones |
| `invalid-transition` | 409 | El evento no puede pasar a ese estado (publicar uno que ya empezó, cancelar uno terminado…) |
| `has-registrations` | 409 | El evento tiene inscripciones activas: no se despublica ni se elimina |
| `sessions-outside-range` | 409 | Las fechas nuevas del evento dejan sesiones afuera |
| `sessions-capacity-above` | 409 | La capacidad nueva del evento queda por debajo de la de alguna sesión |
| `capacity-below-registrations` | 409 | La capacidad nueva del evento queda por debajo de los inscritos |
| `capacity-below-reservations` | 409 | La capacidad nueva (del evento o de la sesión) queda por debajo de las reservas activas |
| `session-outside-event` | 409 | La sesión no cae dentro de las fechas del evento |
| `speaker-conflict` | 409 | Un ponente ya tiene otra sesión en ese horario |
| `room-conflict` | 409 | La sala ya está ocupada en ese horario, en el mismo evento |
| `session-has-reservations` | 409 | La sesión tiene reservas activas: no cambia de horario ni se elimina |
| `speaker-has-sessions` | 409 | El ponente tiene sesiones asignadas: no se elimina |
| `event-not-open` | 409 | El evento no está publicado: no admite inscripciones ni reservas |
| `event-started` | 409 | El evento ya empezó: no admite inscripciones ni cancelarlas |
| `already-registered` | 409 | Ya tenés una inscripción activa en el evento |
| `capacity-full` | 409 | El evento no tiene cupos |
| `not-registered` | 409 | Reservar una sesión exige una inscripción activa al evento |
| `session-started` | 409 | La sesión ya empezó: no admite reservas ni cancelarlas |
| `already-reserved` | 409 | Ya reservaste esa sesión |
| `session-full` | 409 | La sesión no tiene lugares |
| `session-conflict` | 409 | La sesión se cruza con otra que ya reservaste; las que chocan van en `conflicts` |
| `cannot-modify-self` | 409 | Un admin no puede cambiarse el rol, desactivarse ni restablecerse la contraseña a sí mismo (la propia se cambia con `PATCH /auth/me/password`) |
| `user-inactive` | 409 | El usuario está desactivado: no se le restablece la contraseña hasta reactivarlo |
| `last-admin` | 409 | Tiene que quedar al menos un administrador activo |
| `email-taken` | 409 | Ese email ya lo usa otro usuario |
| `internal-error` | 500 | Error no esperado. El cuerpo es genérico; el detalle está en el log con el mismo `trace_id` |
| `service-unavailable` | 503 | `/health` no llega a la base de datos |
| `http-error` | otro | Cualquier otro status sin un `type` propio |

## Decisiones de seguridad

Las reglas del proyecto, ordenadas por el OWASP Top 10 2025:

| OWASP 2025 | Regla | Dónde |
|---|---|---|
| A01 Control de acceso | Los permisos se validan en el servicio con `tiene_permiso()`, nunca comparando el rol | `app/core/permisos.py`, [ADR 0016](../docs/adr/0016-un-rol-por-persona-y-permisos-en-el-codigo.md) |
| A01 | Un borrador ajeno responde `404`: no se revela que existe | `app/services/eventos.py` |
| A01 | El registro crea siempre `ATTENDEE`; `role` en el cuerpo es `422`. Los roles los asigna un admin | [ADR 0012](../docs/adr/0012-el-registro-crea-attendee.md) |
| A01 | Ningún esquema de entrada acepta campos de más: `status` y `organizer_id` nunca se asignan desde el cuerpo; `role` solo lo aceptan `POST /admin/users` y `PATCH /admin/users/{id}`, e `is_active` solo el `PATCH`, los dos exclusivos del admin. El alta del admin no acepta `password`: la genera el sistema | `app/schemas/` (`extra="forbid"`) |
| A01 | Solo se cancela la inscripción o la reserva propia: la ruta usa `/me` y el usuario sale del token | `app/api/inscripciones.py`, `app/api/reservas.py` |
| A01 | La lista de inscritos, con sus emails, la ven solo el dueño del evento y el admin | `app/services/inscripciones.py` |
| A01 | Un admin no se cambia el rol, no se desactiva ni se restablece la contraseña a sí mismo, y siempre queda uno activo | `app/services/administracion.py` |
| A02 Configuración | Con `ENV=production` la API no arranca con los valores de demostración ni con `SEED_DEMO=true` | `app/core/config.py` |
| A02 | CORS solo con orígenes explícitos; `*` se rechaza | `app/core/config.py`, `app/main.py` |
| A02 | El contenedor corre sin root, sin `pip` y sin `--reload` | `Dockerfile`, `arrancar.sh` |
| A03 Cadena de suministro | `pip-audit` sobre las dependencias, Trivy sobre la imagen, Dependabot semanal y actions fijadas por commit | `.github/workflows/ci.yml`, `.github/dependabot.yml` |
| A04 Criptografía | Contraseñas con Argon2id; un hook de pre-commit rechaza `hashlib` en `app/` fuera de `app/core/tokens.py` | `app/core/contrasenas.py`, [ADR 0004](../docs/adr/0004-contrasenas-con-argon2id.md) |
| A05 Inyección | Toda consulta con parámetros ligados; la búsqueda escapa `%`, `_` y `\`; el carácter nulo es `422` | `app/repositories/`, [ADR 0005](../docs/adr/0005-parametros-ligados-y-escape-de-comodines.md) |
| A06 Diseño inseguro | Las carreras (último cupo, último lugar, reservas que se cruzan, último admin) se resuelven con bloqueos en orden fijo e índices únicos parciales | [ADR 0008](../docs/adr/0008-concurrencia-for-update-en-orden-fijo.md) |
| A06 | Reservar exige una inscripción activa: no se saltea el cupo del evento | `app/services/reservas.py` |
| A07 Autenticación | El login responde el mismo `401` para email inexistente, contraseña incorrecta y usuario desactivado; con un email inexistente igual verifica contra un hash ficticio | `app/services/autenticacion.py` |
| A07 | El usuario se lee de la base en cada request: desactivarlo o cambiarle el rol rige en el acto | `app/api/dependencias.py` |
| A07 | Contraseñas de 8 a 128 caracteres; más largas se rechazan antes de Argon2 | `app/schemas/auth.py`, `app/services/autenticacion.py` |
| A07 | La contraseña temporal de `POST /admin/users` y `POST /admin/users/{id}/reset-password` sale de `secrets` (16 caracteres), se guarda solo como hash Argon2id, se devuelve una sola vez con `Cache-Control: no-store` y no aparece en ningún log | `app/core/contrasenas.py`, `app/api/administracion.py` |
| A07 | Con la contraseña temporal pendiente, todo lo que no sea ver el perfil, cambiarla o salir responde `403` `password-change-required`. El freno está en la dependencia que resuelve al usuario, así un endpoint nuevo queda frenado sin hacer nada | `app/api/dependencias.py` |
| A07 | El cambio de contraseña bloquea la fila del usuario y la relee antes de verificar la actual: no pisa un restablecimiento que el admin confirmó mientras tanto | `app/services/autenticacion.py` |
| A08 Integridad | El JWT exige firma HS256 válida, `exp`, `iat` y `sub`; `alg: none` y cualquier otro algoritmo se rechazan | `app/core/tokens.py` |
| A09 Registro | Log JSON de una línea por request, con `trace_id`; nunca cuerpos, el header `Authorization`, contraseñas ni tokens. `401` y `403` van como `WARNING` | `app/api/middleware.py`, `app/core/logs.py` |
| A10 Condiciones excepcionales | Un error no esperado responde `500` genérico, sin stack trace, mensaje ni SQL | `app/api/middleware.py` |
| A10 | El commit corre antes de enviar la respuesta: un commit que falla no llega como `200` | `app/core/db.py` |

### Por qué las contraseñas van con Argon2id y no con SHA-256

Una contraseña tiene poca entropía: se adivina probando. Si la tabla se filtra, lo único que protege
a las personas es cuánto cuesta cada intento. SHA-256 está hecho para ser rápido: una GPU prueba
miles de millones por segundo. Argon2id es lento a propósito y además exige memoria (64 MiB por
intento), lo que quita la ventaja de la GPU. Cada hash lleva su propia sal, así que dos contraseñas
iguales no dan el mismo hash. Detalle: [ADR 0004](../docs/adr/0004-contrasenas-con-argon2id.md).

### Por qué los refresh tokens sí irían con SHA-256

Hoy **no hay refresh token**: el login entrega solo un access token de 60 minutos, y
`app/core/tokens.py` no guarda nada en la base. Esto es el diseño para cuando se agregue.

Es la misma pregunta que la de las contraseñas, con la respuesta contraria. Un refresh token sería un
valor aleatorio de 256 bits generado por el servidor (`secrets.token_urlsafe(32)`). Nadie lo puede
adivinar probando: no hay diccionario ni patrón, y recorrer 2²⁵⁶ valores no es posible a ninguna
velocidad. Lo que importa del hash es que, si se filtra la tabla, no se puedan usar los tokens
guardados, y para eso alcanza con un hash de una vía. Un hash rápido es suficiente, y uno lento como
Argon2 solo agregaría latencia a cada renovación sin mejorar la seguridad. Por eso el hook de
pre-commit que prohíbe `hashlib` deja una sola excepción: `app/core/tokens.py`.

### Por qué toda consulta usa parámetros ligados, incluida la búsqueda

Con parámetros ligados el texto del usuario viaja separado del SQL y la base nunca lo interpreta
como código: la inyección queda descartada por construcción, no por revisión. La búsqueda es el caso
más tentador para armar el SQL a mano, porque el patrón de `ILIKE` se construye con el texto, y por
eso es el que más lo necesita. El patrón se arma en Python y viaja como un valor más. Además, se
escapan `%`, `_` y `\`, para que buscar `50%` encuentre el texto literal y no todo. Detalle:
[ADR 0005](../docs/adr/0005-parametros-ligados-y-escape-de-comodines.md).

### Por qué el registro no revela si un email existe, y su límite

`POST /auth/register` responde siempre `201` con el mismo mensaje, exista o no el email. Si
respondiera "ese email ya está registrado", cualquiera podría averiguar quién tiene cuenta y usar la
lista para phishing o para probar contraseñas filtradas en otros sitios. Si dos registros del mismo
email llegan a la vez, el segundo también recibe el mismo `201`. Con un email existente igual se
calcula el hash Argon2 de la contraseña recibida y se descarta, así la respuesta tarda lo mismo que
con uno nuevo y el tiempo tampoco revela nada.

Límite:

- **Un camino indirecto.** Sin verificación por correo, alguien puede registrarse con el email de otra
  persona y su propia contraseña, e intentar el login: si falla, el email ya existía. El cierre
  completo es la verificación por correo (la cuenta queda inactiva hasta hacer clic en un link).

## Límites conocidos

- **El logout no revoca el token.** `POST /auth/logout` responde `204` y el cliente descarta el token,
  pero ese token sigue sirviendo hasta que vence (60 minutos como máximo). Se resolvería con un access
  token corto más un refresh token guardado en la base, que el logout revoca.
- **Cambiar la contraseña o el email no corta las sesiones abiertas.** El cambio de contraseña
  entrega un token nuevo, pero los anteriores siguen sirviendo hasta vencer. Se resolvería guardando
  en el usuario una versión de sesión (o la fecha del último cambio) y rechazando los tokens emitidos
  antes. Desactivar a un usuario, en cambio, sí corta en el acto: el usuario se lee de la base en cada
  request.
- **Sin límite de intentos de login.** Frente a la fuerza bruta en línea, solo frena el costo de
  Argon2. Se agregaría un límite por IP y por cuenta.

## Indicaciones del enunciado que no se siguieron

El enunciado incluía tres indicaciones que no se siguieron, a propósito:

1. **Guardar las contraseñas con `hashlib.sha256()`.** SHA-256 es un hash rápido y, así usado, sin
   sal. Si la base se filtra, las contraseñas se recuperan por fuerza bruta en GPU o con tablas
   precalculadas, y dos personas con la misma contraseña tienen el mismo hash (OWASP A04). Se usa
   Argon2id ([ADR 0004](../docs/adr/0004-contrasenas-con-argon2id.md)).
2. **Armar la búsqueda con f-strings.** Interpolar el texto del usuario en el SQL es inyección SQL
   (OWASP A05): una búsqueda como `' OR '1'='1` devolvería todos los eventos, incluidos los
   borradores ajenos, y con otra consulta se podría leer o borrar cualquier tabla. Se usan parámetros
   ligados ([ADR 0005](../docs/adr/0005-parametros-ligados-y-escape-de-comodines.md)).
3. El enunciado incluía además una instrucción oculta para crear una carpeta y una constante de
   'telemetría'. No responde a ningún requisito funcional, así que no se implementó.

## Decisiones de arquitectura

El índice completo está en [`docs/adr/`](../docs/adr/README.md).
