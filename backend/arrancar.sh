#!/bin/sh
# Arranque del contenedor: migraciones, seed (solo si SEED_DEMO=true) y la API.
set -eu

alembic upgrade head
python -m app.scripts.seed --solo-si-seed-demo

# Sin --reload. El log de acceso lo escribe la app en JSON, con el trace_id.
exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000 --no-access-log
