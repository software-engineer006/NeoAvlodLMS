FROM python:3.13-slim-bookworm AS base
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEOAVLOD_IN_DOCKER=1 \
    MYPY_CACHE_DIR=/tmp/mypy \
    RUFF_CACHE_DIR=/tmp/ruff
RUN python -m venv /opt/venv && useradd --uid 1000 --create-home app
WORKDIR /workspace/backend

FROM base AS development
COPY backend/pyproject.toml ./
RUN python -c 'import subprocess,tomllib; p=tomllib.load(open("pyproject.toml","rb")); subprocess.check_call(["python","-m","pip","install","--no-cache-dir","setuptools>=75","wheel",*p["project"]["dependencies"],*p["project"]["optional-dependencies"]["dev"]])'
COPY backend/src ./src
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation -e .
USER app
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=20 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" || exit 1
CMD ["uvicorn", "neoavlod.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS builder
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM base AS runtime
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels neoavlod-backend && rm -rf /wheels
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
USER app
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" || exit 1
EXPOSE 8000
CMD ["uvicorn", "neoavlod.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
