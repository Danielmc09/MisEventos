# 0016 · Un rol por persona y permisos derivados del rol en el código

**Estado:** aceptada

## Contexto

Hay tres perfiles y están anidados: el organizador puede todo lo del asistente y el admin todo lo del
organizador. Los servicios preguntan muchas veces "¿puede esta persona hacer esto?". Si cada uno
compara el rol (`usuario.role == Rol.ADMIN`), la política queda repartida en decenas de lugares, y
agregar un rol o mover un permiso obliga a encontrarlos todos.

## Decisión

- **Un rol por persona:** la columna `users.role`, un enum de Postgres (`user_role`) con `ATTENDEE`,
  `ORGANIZER` y `ADMIN` (`backend/app/models/usuario.py`).
- **Los permisos se derivan del rol en el código**, en un solo mapa (`backend/app/core/permisos.py`):

  | Rol | Permisos |
  |---|---|
  | `ATTENDEE` | ninguno extra: ve, se inscribe y reserva |
  | `ORGANIZER` | `evento:crear`, `ponente:gestionar` (sobre lo propio) |
  | `ADMIN` | todos, incluidos `evento:gestionar_todos`, `ponente:gestionar_todos` y `usuarios:gestionar` |

- **El código pregunta por el permiso, nunca por el rol:** `tiene_permiso(usuario, Permiso.X)`.
  `backend/tests/unit/test_arquitectura_permisos.py` falla si un servicio o un router compara el rol
  (`==`, `!=`, `in`, `is` o `match`).
- `GET /auth/me` devuelve los permisos del usuario, para que el frontend no repita el mapa.
- Hasta los roles con poder de administrar salen del mapa: `ROLES_ADMIN` en
  `backend/app/services/administracion.py` son los roles que tienen `usuarios:gestionar`.

## Alternativas descartadas

- **Varios roles por persona** (tabla `user_roles`). No hay un caso que lo necesite: los roles están
  anidados.
- **Roles y permisos en tablas de la base.** Permite cambiarlos sin desplegar, pero suma tres tablas,
  una pantalla para gestionarlas y una lectura más por request, y cada permiso igual está atado al
  código que lo verifica.
- **Comparar el rol donde haga falta.** Es lo que este diseño evita.

## Consecuencias

- Cambiar los permisos de un rol es un cambio de código y un despliegue. Un rol nuevo es un valor
  más del enum (una migración) y una fila más del mapa.
- **Cuándo convendría pasarlos a la base:** cuando un admin necesite crear roles o ajustar permisos
  sin desplegar; cuando haya varias organizaciones con sus propios roles; o cuando los permisos
  dependan del recurso (co-organizador de un evento puntual). Ese día, `PERMISOS_POR_ROL` pasa a ser
  una consulta (con caché), y `tiene_permiso()` mantiene su firma: los servicios no cambian.
