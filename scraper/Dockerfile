FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy scraper dependency files + install into a virtualenv
COPY scraper/pyproject.toml scraper/poetry.lock scraper/
WORKDIR /build/scraper
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

# Copy scraper code
COPY scraper/scraper/ scraper/scraper/

# Run as non-root user
RUN useradd --no-create-home --uid 1000 appuser
USER appuser

WORKDIR /app/scraper

CMD ["python", "-m", "scraper"]
