# Decisiones de arquitectura

Cada archivo es una decisión: el contexto, lo que se decidió, las alternativas descartadas y sus
consecuencias. Se leen por separado, sin depender de otro documento. Los números que faltan son
decisiones que no tienen ADR propio: algunas están implementadas y explicadas en los README; las que
todavía no lo están se listan en el [README raíz](../../README.md#límites-conocidos-y-extensiones).

| # | Decisión | ADR |
|---|---|---|
| 0001 | Capas routers → servicios → repositorios, con la regla de dependencias verificada por un test | [0001](0001-capas-routers-servicios-repositorios.md) |
| 0003 | Errores con RFC 9457 (problem+json), `type` corto, `title` en español y `trace_id` | [0003](0003-errores-rfc-9457.md) |
| 0004 | Contraseñas con Argon2id, nunca con un hash rápido | [0004](0004-contrasenas-con-argon2id.md) |
| 0005 | Consultas con parámetros ligados y escape de comodines en la búsqueda | [0005](0005-parametros-ligados-y-escape-de-comodines.md) |
| 0008 | Concurrencia con `SELECT … FOR UPDATE` en orden fijo e índices únicos parciales | [0008](0008-concurrencia-for-update-en-orden-fijo.md) |
| 0012 | El registro crea `ATTENDEE`; los organizadores los asigna un admin | [0012](0012-el-registro-crea-attendee.md) |
| 0013 | Tests de integración contra PostgreSQL real; qué va en unitarios y qué en integración | [0013](0013-integracion-contra-postgres-real.md) |
| 0016 | Un rol por persona y permisos derivados del rol en el código | [0016](0016-un-rol-por-persona-y-permisos-en-el-codigo.md) |
