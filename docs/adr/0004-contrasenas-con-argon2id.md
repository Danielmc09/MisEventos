# 0004 · Contraseñas con Argon2id

**Estado:** aceptada

## Contexto

Una contraseña elegida por una persona tiene poca entropía: se adivina probando. Si la tabla `users`
se filtra, lo que protege a esas personas es cuánto cuesta cada intento. Un hash de propósito general
como SHA-256 está hecho para ser rápido: una GPU prueba miles de millones por segundo, y sin sal dos
personas con la misma contraseña tienen el mismo hash y sirven las tablas precalculadas.

## Decisión

- Las contraseñas se guardan con **Argon2id** (`argon2-cffi`), en `backend/app/core/contrasenas.py`.
  Con los parámetros por defecto de la librería: 64 MiB de memoria, 3 pasadas, 4 hilos.
- Cada hash lleva su propia sal aleatoria y sus parámetros, dentro del mismo texto
  (`$argon2id$v=19$m=65536,t=3,p=4$...`).
- `verificar()` devuelve `False` ante una contraseña incorrecta o un hash que no es Argon2; nunca lanza.
- El login con un email inexistente igual verifica contra un hash ficticio (`_HASH_FICTICIO` en
  `backend/app/services/autenticacion.py`), para tardar lo mismo que con uno real.
- El registro con un email que ya existe igual calcula el hash Argon2 de la contraseña recibida y lo
  descarta, para tardar lo mismo que con un email nuevo.
- Email de más de 254 caracteres o contraseña de más de 128 se rechazan antes de llegar a Argon2: una
  contraseña de 1 MB por request sería una denegación de servicio barata.
- Nunca se guarda ni se loguea una contraseña, tampoco una intentada.
- Un hook de pre-commit (`sin-hashlib` en `.pre-commit-config.yaml`) rechaza `hashlib` en
  `backend/app/`, salvo en `app/core/tokens.py`.

## Alternativas descartadas

- **SHA-256, con o sin sal.** Rápido por diseño: lo que conviene para verificar integridad es lo que
  no conviene para una contraseña.
- **bcrypt.** Sigue siendo aceptable, pero solo usa los primeros 72 bytes y no exige memoria, así que
  se paraleliza bien en GPU.
- **PBKDF2.** Tampoco exige memoria; necesita cientos de miles de iteraciones para acercarse.
- **scrypt.** Válido, pero Argon2id es la recomendación actual de OWASP y su variante `id` resiste
  ataques de canal lateral y de GPU a la vez.

## Consecuencias

- Cada login, registro y cambio de contraseña cuesta decenas de milisegundos y 64 MiB por un momento.
  Es el precio buscado.
- No hay límite de intentos de login: frente a la fuerza bruta en línea, lo único que frena es ese
  costo. Se agregaría un límite por IP y por cuenta.
- Si se suben los parámetros, los hashes viejos siguen verificando pero no se actualizan:
  `check_needs_rehash()` no se usa todavía. Se resolvería rehasheando en el login exitoso.
