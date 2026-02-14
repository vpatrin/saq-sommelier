FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /build

# Copy shared package (path dependency of scraper)
COPY shared/ shared/

# Copy scraper dependency files + install
COPY scraper/pyproject.toml scraper/poetry.lock scraper/
WORKDIR /build/scraper
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction

FROM python:3.12-slim

WORKDIR /app

# Copy installed Python packages from builder (includes shared via poetry install)
COPY --from=builder /usr/local /usr/local

# Copy scraper code
COPY scraper/src/ scraper/src/

WORKDIR /app/scraper

CMD ["python", "-m", "src"]
