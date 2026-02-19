FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
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

COPY --from=builder /usr/local /usr/local
COPY bot/bot/ bot/bot/

RUN useradd --create-home appuser
USER appuser

WORKDIR /app/bot

CMD ["python", "-m", "bot"]
