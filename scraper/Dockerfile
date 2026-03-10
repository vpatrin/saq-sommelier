FROM python:3.12-slim AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency of scraper)
COPY core/ core/

# Copy scraper dependency files + install
COPY scraper/pyproject.toml scraper/poetry.lock scraper/
WORKDIR /build/scraper

# Poetry installs core as editable (develop=true), creating .pth symlinks to
# /build/core/ — these don't survive multi-stage builds. After poetry install,
# pip re-installs core as a proper package into site-packages.
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

# Copy scraper code
COPY scraper/scraper/ scraper/scraper/

# Run as non-root user
RUN useradd --create-home appuser
USER appuser

WORKDIR /app/scraper

CMD ["python", "-m", "scraper"]
