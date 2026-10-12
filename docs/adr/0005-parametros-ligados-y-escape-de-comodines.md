# 0005 · Consultas con parámetros ligados y escape de comodines en la búsqueda

**Estado:** aceptada

## Contexto

Hay tres búsquedas por texto libre: eventos por nombre (`GET /events?q=`), ponentes por nombre y
usuarios por nombre o email en la administración. Armar el SQL con f-strings o concatenación deja
que el texto del usuario cambie la consulta: con `q = "' OR 1=1 --"` se ve todo, incluidos los
borradores ajenos. Hay además un problema que no es inyección pero da resultados falsos: en `ILIKE`,
`%` y `_` son comodines, así que buscar `50%` o `_` encuentra cualquier cosa.

## Decisión

- **Toda consulta se arma con `select()` de SQLModel/SQLAlchemy**: los valores viajan siempre como
  parámetros ligados y el driver (psycopg) los manda separados del texto SQL. No hay SQL armado con
  f-strings ni con concatenación en `backend/app/`.
- **Los comodines se escapan** antes de armar el patrón, con `escapar_like()` en
  `backend/app/repositories/eventos.py`, y la consulta declara el carácter de escape:

  ```python
  patron = f"%{escapar_like(filtros.q)}%"            # el patrón es un valor, no SQL
  condiciones.append(col(Event.name).ilike(patron, escape="\\"))
  ```

  La barra se escapa primero; si no, se escaparían las barras que agrega el propio escape. La misma
  función la usan `backend/app/repositories/ponentes.py` y `backend/app/repositories/usuarios.py`.
- El carácter nulo (`\x00`) se rechaza con `422` en la entrada (`backend/app/schemas/comunes.py` y
  `backend/app/api/dependencias.py`): Postgres no lo acepta en un texto y terminaría en un `500`.
- El único SQL textual con un valor variable está en los tests (`CREATE DATABASE`, que no acepta
  parámetros) y va como identificador citado con `psycopg.sql.Identifier`.

## Alternativas descartadas

- **Escapar las comillas a mano.** Frágil: depende de conocer cada caso del dialecto.
- **Prohibir `%` y `_` en la búsqueda.** Rechaza búsquedas legítimas como `50%`.
- **Búsqueda de texto completo de Postgres (`tsvector`).** Mejor para relevancia y para mucho
  volumen, pero suma columnas e índices que la búsqueda por nombre no necesita hoy.

## Consecuencias

- La inyección queda descartada por construcción, no por revisión. Ruff corre con las reglas `S`
  (bandit), que marcan SQL armado como texto.
- `backend/tests/integration/test_busqueda_eventos.py` lo prueba contra Postgres: una inyección en
  `q` responde `200` sin resultados, y `q=%` busca el porcentaje literal.
- `ILIKE '%…%'` no usa un índice B-tree: con muchos eventos sería un escaneo completo. Se resolvería
  con un índice trigram (`pg_trgm`) sobre el nombre.
