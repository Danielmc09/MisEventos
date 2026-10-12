# 0008 · Concurrencia con `SELECT … FOR UPDATE` en orden fijo e índices únicos parciales

**Estado:** aceptada

## Contexto

Varias reglas son del tipo "contar y después escribir": queda un cupo en el evento, queda un lugar en
la sesión, la persona no tiene otra reserva que se cruce, queda otro admin activo. Con el aislamiento
por defecto de Postgres (`READ COMMITTED`), dos transacciones simultáneas leen el mismo conteo, las
dos pasan la regla y las dos escriben: se vende el último cupo dos veces, o dos admins se degradan
mutuamente y no queda ninguno.

## Decisión

1. **Bloquear la fila padre antes de contar.** Cada operación que cuenta toma con
   `SELECT … FOR UPDATE` la fila de la que cuelga lo que cuenta: el evento para inscribirse, la
   sesión para reservar. La segunda transacción espera a que la primera termine y cuenta ya con su
   escritura. Los métodos se llaman `por_id_para_escribir` (por ejemplo, en
   `backend/app/repositories/eventos.py`) y releen la fila al bloquearla (`populate_existing`).
2. **Un solo orden de bloqueo en todo el sistema**, documentado en `backend/app/services/reservas.py`:

   ```
   evento → inscripción → sesión → ponentes (ordenados por id)
   ```

   Todo camino que toma más de una de esas filas las toma en ese orden. Si dos transacciones
   bloquearan en órdenes distintos, cada una podría quedar esperando a la otra (deadlock).
3. **Administración:** para cambiar el rol o el estado de un usuario se bloquean primero todos los
   admins activos, en orden de id, y después el usuario (`backend/app/services/administracion.py`).
   Así, de dos admins que se degradan a la vez, el segundo ve que ya queda uno solo (`last-admin`).
4. **Índices únicos parciales como última defensa**, en las migraciones 0005 y 0006 de
   `backend/alembic/versions/`:
   `uq_registrations_activa (user_id, event_id) WHERE status = 'ACTIVE'` y
   `uq_session_registrations_activa (user_id, session_id) WHERE status = 'ACTIVE'`. Aunque el servicio
   fallara, no entra una segunda inscripción o reserva activa de la misma persona; las canceladas no
   cuentan, así que se puede volver a inscribir.
5. El email es único sin distinguir mayúsculas (`uq_users_email` sobre `lower(email)`). Si dos
   registros del mismo email chocan, el repositorio atrapa el error del índice dentro de un savepoint.

## Alternativas descartadas

- **Aislamiento `SERIALIZABLE`.** Correcto, pero cada endpoint tendría que reintentar ante un error
  de serialización.
- **Contador en la fila del evento** (`UPDATE … SET inscritos = inscritos + 1 WHERE inscritos < capacidad`).
  Rápido para el cupo, pero duplica un dato que ya está en las inscripciones y no resuelve los cruces.
- **Advisory locks.** No se ven en el esquema y es fácil olvidarse de uno.
- **Solo el índice único.** Evita duplicados, no la sobreventa: el cupo no es una regla de unicidad.

## Consecuencias

- Las escrituras sobre un mismo evento se hacen de a una. Para el volumen de una empresa
  organizadora es aceptable.
- Un camino nuevo que bloquee fuera de orden puede provocar un deadlock. Postgres lo detecta y aborta
  una de las dos transacciones; esa recibe un `500`.
- Lo prueban los tests `backend/tests/integration/test_concurrencia_*.py`: frenan varios requests en
  el bloqueo, lo sueltan y verifican que entra uno solo.
