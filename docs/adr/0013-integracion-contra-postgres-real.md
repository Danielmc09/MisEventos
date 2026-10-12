# 0013 · Tests de integración contra PostgreSQL real

**Estado:** aceptada

## Contexto

Buena parte de lo que hace correcta a esta API vive en la base: los índices únicos parciales, los
bloqueos `FOR UPDATE`, el trigger que mantiene `updated_at`, el email único sin distinguir
mayúsculas, el enum de roles, `timestamptz` y el `ILIKE … ESCAPE`. Nada de eso se puede probar con un
doble en memoria, y SQLite no tiene `FOR UPDATE`, ni los mismos índices parciales, ni `timestamptz`.
Al mismo tiempo, una suite que necesita base para todo es lenta y no corre en cada cambio.

## Decisión

Dos suites, separadas por carpeta y por marca:

| | Unitarios | Integración |
|---|---|---|
| Carpeta | `backend/tests/unit/` | `backend/tests/integration/` |
| Base | Ninguna: dobles en memoria (`backend/tests/unit/dobles.py`) y `dependency_overrides` | PostgreSQL 16 real |
| Qué prueban | Reglas de negocio, orden de los errores, permisos, validación, formato de error, configuración, la regla de capas | Bloqueos y concurrencia, índices, triggers, migraciones, consultas reales, el seed |
| Cuándo corren | En cada push (hook `pre-push`) y en CI | En CI, y a mano con la base levantada |
| Comando | `poetry run pytest -m "not integration"` | `poetry run pytest` (corre las dos) |

Cómo funciona la integración (`backend/tests/integration/conftest.py` e `infraestructura.py`):

- Usa `TEST_DATABASE_URL`, o `DATABASE_URL` con la base cambiada a `miseventos_test`. Se niega a
  correr si el nombre de la base no termina en `_test`: nunca toca la base de desarrollo.
- Crea la base si no existe y la migra **con Alembic**, no con `create_all`: prueba también las
  migraciones.
- Cada test corre en una transacción que se revierte al final; el commit de cada request queda en un
  savepoint dentro de ella.
- Los tests de concurrencia (`test_concurrencia_*.py`) son la excepción: necesitan commits reales
  entre conexiones, así que usan datos propios y los borran al terminar.

La cobertura (mínimo 80 %) se mide sobre la corrida completa en CI, con un servicio de Postgres
(`.github/workflows/ci.yml`).

## Alternativas descartadas

- **SQLite en memoria.** Rápido, pero con otra semántica: los tests pasarían y producción fallaría.
- **Solo unitarios, con el repositorio simulado.** No detectan un error de SQL, un índice que falta
  ni una carrera.
- **Testcontainers.** Levanta Postgres desde pytest, pero suma una dependencia; el proyecto ya tiene
  la base en `docker-compose.yml` y en CI.

## Consecuencias

- La suite unitaria corre sin nada levantado, en poco más de un minuto.
- La de integración necesita Postgres arriba y tarda más.
- Una regla que depende de la base tiene que tener su test de integración: un unitario con un doble
  no la prueba.
