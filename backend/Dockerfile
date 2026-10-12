# syntax=docker/dockerfile:1

# ── builder: solo las dependencias de producción, en un venv ─────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true \
    POETRY_NO_INTERACTION=1

RUN pip install "poetry==2.5.1"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root


# ── runtime: el venv, la app y las migraciones, sin root ─────────────────────
FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Sin pip en runtime (el venv nace sin pip y el del sistema se quita): trae dependencias vendorizadas con CVE y la app no lo usa.
RUN python -m pip uninstall --yes pip

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
# Misma ruta que en el builder: los scripts del venv apuntan a /app/.venv.
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY --chmod=755 arrancar.sh ./

USER app
EXPOSE 8000

# Sin curl en la imagen: el chequeo lo hace Python. Un 503 de /health levanta HTTPError.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

ENTRYPOINT ["/app/arrancar.sh"]
