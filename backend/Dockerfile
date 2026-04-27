FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy backend dependency files + install into a virtualenv
COPY backend/pyproject.toml backend/poetry.lock backend/
WORKDIR /build/backend
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# Poetry editable install creates .pth symlinks to /build/core/ — these don't
# survive multi-stage builds. pip re-installs core as a proper package.
RUN poetry install --only main --no-interaction \
    && pip install --no-cache-dir --no-deps --force-reinstall /build/core

FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

# Logs appear immediately in docker compose logs (no buffering)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only the virtualenv — no pip/setuptools/poetry leak
COPY --from=builder /opt/venv /opt/venv
# Patch OS packages (picks up openssl fixes not yet in the pinned base image digest)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
# Strip pip from venv and base image (not needed at runtime, avoids Trivy CVEs)
RUN pip uninstall pip -y && rm -rf /usr/local/lib/python*/site-packages/pip*

# Copy backend code
COPY backend/ backend/

# Alembic config + migration scripts (run: alembic -c core/alembic.ini upgrade head)
COPY core/alembic.ini core/alembic.ini
COPY core/alembic/ core/alembic/

# Prometheus multiprocess mode — each worker writes metrics here; /metrics aggregates all.
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

# Run as non-root user
RUN useradd --no-create-home --uid 1000 appuser
USER appuser

EXPOSE 8001

CMD ["gunicorn", "backend.app:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8001", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
