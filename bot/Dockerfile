FROM python:3.12-slim AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy bot dependency files + install
COPY bot/pyproject.toml bot/poetry.lock bot/
WORKDIR /build/bot
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction \
    && pip install --no-cache-dir --no-deps --force-reinstall /build/core

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local
# Strip build tools leaked from builder (not needed at runtime)
RUN pip uninstall pip setuptools wheel poetry -y

# Copy bot code
COPY bot/bot/ bot/bot/

RUN useradd --create-home appuser
USER appuser

WORKDIR /app/bot

CMD ["python", "-m", "bot"]
