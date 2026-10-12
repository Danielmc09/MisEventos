# 0001 · Capas: routers → servicios → repositorios

**Estado:** aceptada

## Contexto

La API tiene reglas que no son triviales: cupos de eventos y de sesiones, cruces de horario de
ponentes y salas, borradores que solo ve su dueño, un último administrador que no se puede degradar.
Si un endpoint mezcla HTTP, reglas y SQL, cada regla solo se puede probar levantando HTTP y una base,
y la misma regla termina escrita dos veces (por ejemplo, en el endpoint y en el script de datos de
demostración).

## Decisión

El backend se separa en tres capas, y ninguna importa de una capa superior:

| Capa | Carpeta | Hace | No hace |
|---|---|---|---|
| Router | `backend/app/api/` | Lee la entrada, llama al servicio, arma la respuesta y el código HTTP | Tocar la base ni decidir reglas |
| Servicio | `backend/app/services/` | Reglas de negocio y permisos. Lanza excepciones de dominio (`backend/app/core/excepciones.py`) | Conocer HTTP (`fastapi`, `starlette`, `HTTPException`) |
| Repositorio | `backend/app/repositories/` | Consultas y escrituras | Decidir permisos ni reglas |

- Cada servicio declara lo que necesita de los datos como un `Protocol` (por ejemplo, `Usuarios` en
  `backend/app/services/autenticacion.py`). El repositorio real lo cumple sin heredarlo.
- Los repositorios se inyectan en los routers desde un solo lugar: `backend/app/api/dependencias.py`.
- Una transacción por request (`backend/app/core/db.py`): commit antes de enviar la respuesta,
  rollback si algo falla.
- Fuera de las capas: `models/` (tablas), `schemas/` (entrada y salida de la API) y `core/`
  (configuración, errores, permisos, contraseñas, tokens, logs).

La regla no depende de la buena voluntad: `backend/tests/unit/test_arquitectura_capas.py` recorre el
AST de cada archivo y falla si un servicio importa HTTP, si un repositorio importa servicios o HTTP,
si un router importa la base (salvo `dependencias.py`) o si alguna capa usa imports dinámicos.

## Alternativas descartadas

- **Endpoints que hacen todo**, como en los ejemplos de FastAPI. Es lo más rápido al principio, pero
  probar una regla obliga a tener una base, y el seed no podría reutilizar las reglas.
- **Hexagonal completa**, con entidades de dominio separadas de las tablas y mapeos entre ellas. Para
  este tamaño duplica cada modelo sin beneficio: los servicios usan los modelos de SQLModel.
- **Unit of Work explícito.** La sesión por request ya es la unidad de trabajo.

## Consecuencias

- Los servicios se prueban sin base, con dobles en memoria (`backend/tests/unit/dobles.py`).
- El seed crea sesiones y reservas a través de los servicios (`backend/app/scripts/seed.py`): valen
  las mismas reglas y los mismos bloqueos que en la API.
- Cada funcionalidad suma tres archivos como mínimo.
- Los servicios conocen los modelos de SQLModel. Es un acoplamiento aceptado: cambiar de ORM tocaría
  también los servicios.
