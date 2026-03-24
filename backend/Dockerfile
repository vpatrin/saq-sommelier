FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4 AS builder

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

FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

# Logs appear immediately in docker compose logs (no buffering)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only the virtualenv — no pip/setuptools/poetry leak
COPY --from=builder /opt/venv /opt/venv
# Strip pip from venv and base image (not needed at runtime, avoids Trivy CVEs)
RUN pip uninstall pip -y && rm -rf /usr/local/lib/python*/site-packages/pip*

# Copy backend code
COPY backend/ backend/

# Alembic config + migration scripts (run: alembic -c core/alembic.ini upgrade head)
COPY core/alembic.ini core/alembic.ini
COPY core/alembic/ core/alembic/

# Run as non-root user
RUN useradd --no-create-home --uid 1000 appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8001"]
