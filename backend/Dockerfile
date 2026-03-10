FROM python:3.12-slim AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy backend dependency files + install
COPY backend/pyproject.toml backend/poetry.lock backend/
WORKDIR /build/backend
# Same fix as scraper: editable install creates .pth symlinks that don't
# survive multi-stage builds. pip re-installs core as a proper package.
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction \
    && pip install --no-cache-dir --no-deps --force-reinstall /build/core

FROM python:3.12-slim

# Logs appear immediately in docker compose logs (no buffering)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local
# Strip build tools leaked from builder (not needed at runtime)
RUN pip uninstall pip setuptools wheel poetry -y

# Copy backend code
COPY backend/ backend/

# Alembic config + migration scripts (run: alembic -c core/alembic.ini upgrade head)
COPY core/alembic.ini core/alembic.ini
COPY core/alembic/ core/alembic/

# Run as non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8001"]
