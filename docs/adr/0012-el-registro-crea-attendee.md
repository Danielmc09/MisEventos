# 0012 · El registro crea `ATTENDEE`; los organizadores los asigna un admin

**Estado:** aceptada

## Contexto

Mis Eventos es una sola empresa organizadora que gestiona sus propios eventos. El público se registra
para asistir; los organizadores son personal de la empresa. Hay tres roles: `ATTENDEE` (asistente),
`ORGANIZER` (crea y gestiona sus eventos y ponentes) y `ADMIN` (gestiona todo, incluidos los usuarios).
Si el registro aceptara el rol en el cuerpo, cualquiera podría darse de alta como organizador o como
administrador: una escalada de privilegios (OWASP A01).

## Decisión

- `POST /auth/register` crea siempre un `ATTENDEE` activo (`registrar()` en
  `backend/app/services/autenticacion.py`).
- El esquema de entrada (`RegistroEntrada` en `backend/app/schemas/auth.py`) tiene `extra="forbid"`:
  un cuerpo con `role`, o con cualquier campo que no sea `email`, `password` o `full_name`, responde
  `422`. No se ignora en silencio: quien lo manda se entera.
- Solo un admin cambia el rol de otro usuario, con `PATCH /admin/users/{id}`
  (`backend/app/services/administracion.py`). No puede cambiarse el rol ni desactivarse a sí mismo
  (`cannot-modify-self`), y siempre queda al menos un admin activo (`last-admin`).
- El admin también puede crear un usuario con cualquier rol, con `POST /admin/users`. La contraseña
  no la elige nadie: el sistema genera una temporal, que se muestra una sola vez, y el usuario tiene
  que cambiarla antes de hacer cualquier otra cosa.
- El seed crea un organizador de demostración, para probar la app sin pasar por el admin.

## Alternativas descartadas

- **Elegir el rol al registrarse.** Es la escalada que esta decisión evita.
- **Registro como organizador con aprobación.** Agrega un estado pendiente y un flujo de aprobación
  que ningún requisito pide.
- **Todos pueden organizar.** Para una sola empresa no tiene sentido que el público cree eventos a
  su nombre.

## Consecuencias

- Un organizador nuevo necesita a un admin: que le cambie el rol a su cuenta, o que se la cree ya
  como organizador.
- El cambio de rol rige desde el request siguiente: el token no lleva el rol, y el usuario se lee de
  la base en cada request (`backend/app/core/tokens.py`, `usuario_actual()` en
  `backend/app/api/dependencias.py`). Lo mismo con una desactivación.
- Si la app pasara a tener varias empresas organizadoras, esto se revisa junto con el ADR 0016.
