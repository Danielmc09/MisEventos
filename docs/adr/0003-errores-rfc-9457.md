# 0003 · Errores con RFC 9457 (problem+json)

**Estado:** aceptada

## Contexto

Por defecto FastAPI responde los errores con formatos distintos: `{"detail": "..."}` para un `404`,
una lista de errores de pydantic en inglés para un `422`, y texto plano para un `500`. El frontend
necesita dos cosas de cada error: un identificador estable para decidir qué hacer, y un mensaje en
español para mostrar. Y un error no esperado nunca puede devolver un stack trace, el mensaje de la
excepción ni SQL.

## Decisión

Toda respuesta de error es `application/problem+json` (RFC 9457) con esta forma:

```json
{ "type": "capacity-full", "title": "El evento no tiene cupos", "status": 409,
  "detail": "El evento alcanzó su capacidad de 50 personas.", "trace_id": "8f2c…" }
```

- `type`: identificador corto y estable. El RFC permite una referencia relativa; no hace falta una URL.
- `title`: en español, para mostrárselo a la persona. `detail`: el caso concreto, cuando aporta.
- `trace_id`: el `X-Request-ID` del request. El mismo valor está en el log.
- Un `422` agrega `errors: [{"field": "end_at", "message": "Tiene que ser posterior al inicio"}]`.
- Algunos errores agregan miembros de extensión, como `conflicts` en `session-conflict`.

Cómo se arma:

- Los servicios lanzan excepciones de dominio (`NotFound`, `Forbidden`, `Conflict`, `DatosInvalidos`…)
  de `backend/app/core/excepciones.py`. Cada clase trae su `status`, `type` y `title`, y un caso puede
  pisar `type` y `title` (por ejemplo, `Conflict(tipo="session-full", ...)`).
- Un único handler en `backend/app/api/errores.py` las traduce. El mismo archivo convierte las
  `HTTPException` de Starlette (ruta inexistente, método no permitido) y los errores de validación de
  pydantic, con mensajes traducidos al español.
- Un error no esperado lo atrapa `errores_no_esperados` en `backend/app/api/middleware.py`: responde
  `500` con `type: "internal-error"` y un `title` genérico, y deja el detalle completo en el log con el
  mismo `trace_id`.
- `respuestas_de_error()` declara en el OpenAPI de cada endpoint los errores que puede devolver, así
  Swagger los muestra.

## Alternativas descartadas

- **`HTTPException` lanzada desde los servicios.** Ata las reglas a HTTP (ver ADR 0001).
- **Un formato propio.** Haría lo mismo que el RFC, sin estándar detrás.
- **`type` como URL absoluta.** El RFC la sugiere para que se pueda abrir, pero no hay dónde publicar
  esas páginas, y un identificador corto es más fácil de mantener.

## Consecuencias

- El frontend decide por `type` y muestra `title` sin traducir nada.
- Con el `trace_id` que ve la persona se encuentra la línea del log del request.
- El `type` es un contrato público: renombrarlo rompe al cliente. La lista completa está en el
  README del backend.
