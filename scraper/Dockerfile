FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /build

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY . .

CMD ["python", "-m", "main"]
