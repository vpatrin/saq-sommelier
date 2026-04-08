FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4 AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy bot dependency files + install into a virtualenv
COPY bot/pyproject.toml bot/poetry.lock bot/
WORKDIR /build/bot
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
# Patch OS packages (picks up openssl fixes not yet in the pinned base image digest)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
# Strip pip from venv and base image (not needed at runtime, avoids Trivy CVEs)
RUN pip uninstall pip -y && rm -rf /usr/local/lib/python*/site-packages/pip*

# Copy bot code
COPY bot/bot/ bot/bot/

# Run as non-root user
RUN useradd --no-create-home --uid 1000 appuser
USER appuser

WORKDIR /app/bot

CMD ["python", "-m", "bot"]
