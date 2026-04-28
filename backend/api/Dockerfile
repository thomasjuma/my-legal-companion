# API image for App Runner. Build from repository root:
#   docker build -f backend/api/Dockerfile .
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=400

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"

# pyproject.toml / uv.lock live in backend/api/ — keep this as WORKDIR so
# uv sync resolves the path dependency (../database) correctly.
WORKDIR /app/backend/api

# Path dependency: ../database
COPY backend/database /app/backend/database
COPY backend/api/pyproject.toml backend/api/uv.lock ./

# Pre-install hatchling and skip isolated build for the path dep so a second PyPI
# fetch for `build-system.requires` is not needed (avoids common timeouts to PyPI in CI).
RUN uv venv \
    && uv pip install hatchling editables \
    && uv sync --frozen --no-dev --no-build-isolation-package legal-companion-database

COPY backend/api/ ./

EXPOSE 8000
# --app-dir sets sys.path to app/ so all flat imports (core, routers, services)
# resolve correctly — same as running `uv run uvicorn main:app` from inside app/.
CMD ["uv", "run", "uvicorn", "main:app", "--app-dir", "/app/backend/api/app", "--host", "0.0.0.0", "--port", "8000"]
