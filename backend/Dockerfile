FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /build

# Copy backend dependency files + install
COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction

FROM python:3.12-slim

# Logs appear immediately in docker compose logs (no buffering)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local

# Copy backend code
COPY backend/main.py .

# Run as non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
