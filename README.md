# Mis Eventos

Plataforma web para organizar eventos: los organizadores publican eventos con sesiones y ponentes, y
los asistentes se inscriben y reservan lugar en las sesiones, sin pasarse del cupo ni cruzar horarios.
API en FastAPI y PostgreSQL, interfaz en React.

## Arranque rápido

Con Docker y Docker Compose, desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose up --build
```

| Qué | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API, documentación Swagger | http://localhost:8000/docs |

El backend aplica las migraciones y carga los datos de demostración al arrancar. Configuración,
ejecución sin Docker y API: [backend/README.md](backend/README.md). Estructura, rutas y componentes
del frontend: [frontend/README.md](frontend/README.md).

## Usuarios de demostración

| Email | Rol | Contraseña | Qué conviene probar |
|---|---|---|---|
| `admin@miseventos.local` (el valor de `ADMIN_EMAIL`, se puede cambiar en `.env`) | Administrador (`ADMIN`) | `ADMIN_PASSWORD` (`Admin-Demo-2026`) | Administración de usuarios: rol, estado y datos; crear un usuario y restablecer una contraseña. Ver y gestionar cualquier evento, incluidos los borradores |
| `organizador@miseventos.local` | Organizador (`ORGANIZER`) | `DEMO_PASSWORD` (`Demo-Local-2026`) | Crear, publicar, editar y cancelar eventos; sesiones con ponentes; el panel de inscritos |
| `asistente@miseventos.local` | Asistente (`ATTENDEE`) | `DEMO_PASSWORD` (`Demo-Local-2026`) | Inscribirse, reservar sesiones (en "Python Day Medellín" hay una que se cruza y un taller con un solo lugar) y revisar "Mi perfil" |

Son credenciales públicas, solo para desarrollo local. Con `ENV=production` la API no arranca si
encuentra estas contraseñas, el secreto JWT de `.env.example` o `SEED_DEMO=true`.

## Qué incluye

**Funcionalidades**

- Registro, login, perfil con mis inscripciones y cambio de contraseña, con contraseñas en Argon2id
  ([ADR 0004](docs/adr/0004-contrasenas-con-argon2id.md)). El registro crea siempre un asistente
  ([ADR 0012](docs/adr/0012-el-registro-crea-attendee.md)).
- Eventos en borrador, publicados o cancelados (en curso y finalizado salen de las fechas), con
  búsqueda y paginación. La búsqueda usa parámetros ligados ([ADR 0005](docs/adr/0005-parametros-ligados-y-escape-de-comodines.md)).
- Sesiones dentro del evento y ponentes, sin cruces de sala ni de ponente.
- Inscripciones con control de cupo y reservas de lugar en sesiones, a salvo de la concurrencia
  ([ADR 0008](docs/adr/0008-concurrencia-for-update-en-orden-fijo.md)).
- Administración de usuarios, con permisos derivados del rol
  ([ADR 0016](docs/adr/0016-un-rol-por-persona-y-permisos-en-el-codigo.md)).
- Alta de usuarios por el admin y restablecimiento de contraseña: el sistema genera una contraseña
  temporal, que se muestra una sola vez, y el usuario tiene que cambiarla en su primer ingreso antes
  de poder hacer cualquier otra cosa.
- Errores en formato problem+json con `trace_id` ([ADR 0003](docs/adr/0003-errores-rfc-9457.md)) y
  documentación OpenAPI en `/docs`.
- Docker Compose con la base, la API y el frontend; contenedores sin root y la API con
  healthcheck.

**Bonus**

- Portada del inicio en WebP, a tres anchos con `srcset` ([frontend/README.md](frontend/README.md#rendimiento)).
- CI en GitHub Actions: lint, tipos, tests con cobertura publicada como artefacto, auditoría de
  dependencias y escaneo de las imágenes ([ci.yml](.github/workflows/ci.yml)).
- pre-commit con detección de secretos (gitleaks y claves privadas), ruff, ESLint, Prettier y tests
  antes del push ([.pre-commit-config.yaml](.pre-commit-config.yaml)).

## Cómo probar

| Lado | Comando | Cobertura actual |
|---|---|---|
| Backend, unitarios | `cd backend && poetry install && poetry run pytest -m "not integration"` | — |
| Backend, completo (necesita PostgreSQL) | `docker compose up -d db`, exportar `TEST_DATABASE_URL` y `cd backend && poetry run pytest` | 99,58 % |
| Frontend | `cd frontend && npm ci && npm run test:cov` | 97,87 % de líneas |

Las dos suites fallan por debajo del 80 % y dejan un reporte HTML (`backend/htmlcov/`,
`frontend/coverage/`). El detalle, con la URL de la base de tests, está en
[backend/README.md](backend/README.md#probar) y [frontend/README.md](frontend/README.md#probar-y-lint).

## Decisiones principales

| ADR | Decisión |
|---|---|
| [0001](docs/adr/0001-capas-routers-servicios-repositorios.md) | Capas routers → servicios → repositorios, verificadas por un test |
| [0003](docs/adr/0003-errores-rfc-9457.md) | Errores con RFC 9457 (problem+json) |
| [0004](docs/adr/0004-contrasenas-con-argon2id.md) | Contraseñas con Argon2id |
| [0005](docs/adr/0005-parametros-ligados-y-escape-de-comodines.md) | Parámetros ligados y escape de comodines en la búsqueda |
| [0008](docs/adr/0008-concurrencia-for-update-en-orden-fijo.md) | Concurrencia con `SELECT … FOR UPDATE` en orden fijo e índices únicos parciales |
| [0012](docs/adr/0012-el-registro-crea-attendee.md) | El registro crea asistentes; los organizadores los asigna un admin |
| [0013](docs/adr/0013-integracion-contra-postgres-real.md) | Tests de integración contra PostgreSQL real |
| [0016](docs/adr/0016-un-rol-por-persona-y-permisos-en-el-codigo.md) | Un rol por persona y permisos en el código |

Índice completo: [docs/adr/](docs/adr/README.md).

## Cómo trabajé

Cada funcionalidad empezó como una especificación con criterios que se pueden probar. Después vino un
test en rojo, después el código que lo pone en verde, y una revisión antes de integrar. Usé
asistentes de IA dentro de ese proceso; cada decisión está documentada en los ADR y la defiendo.

## Límites conocidos y extensiones

Diseñado y no implementado, con cómo se haría:

| Qué falta | Cómo se haría |
|---|---|
| Auditoría de cambios | Un trigger por tabla que escribe en una tabla de auditoría, con el usuario que la app pasa en una variable de la transacción |
| Refresh token | Access token corto y refresh token en cookie `HttpOnly`, guardado como hash SHA-256, rotado en cada uso; si se reusa uno ya rotado, se revoca toda la familia |
| Avisos de seguridad | Avisar al dueño de la cuenta cuando alguien intenta registrarse con su email, y avisar por correo de un cambio de contraseña o email |
| Aviso de cruce entre eventos | Al inscribirse, buscar inscripciones activas en eventos que se superponen y avisar sin bloquear |
| Cierre de sesión por inactividad | Un temporizador en el frontend que cierra la sesión tras un tiempo sin actividad |
| Verificación por correo | La cuenta nace inactiva y se activa con un link firmado de un solo uso |
| Lista de espera | Una cola por evento; al liberarse un cupo, se ofrece al primero, con el mismo bloqueo que la inscripción |
| Límite de intentos de login | Un contador por IP y por cuenta, con espera creciente |
| Redis | Hoy el listado se cachea 60 segundos en el frontend; con varias instancias de la API, Redis para la caché y el límite de intentos |
| Inscripción por día en eventos largos | Una inscripción por día del evento, con su propio cupo |

Límites del token, hoy:

- El logout no revoca el token: sigue sirviendo hasta que vence, a los 60 minutos.
- Después de cambiar la contraseña o el email, el token anterior también sirve hasta que vence.
- Los permisos viajan con el usuario: el frontend los refresca con `/auth/me` al cargar la app.
  Desactivar a alguien o cambiarle el rol, en cambio, rige en el acto en la API.
