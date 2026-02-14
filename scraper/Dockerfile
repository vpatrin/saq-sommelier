FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /build

# Copy only dependency files for caching
COPY scraper/pyproject.toml scraper/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction

FROM python:3.12-slim

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local

# Copy shared code (database models, config)
COPY shared/ shared/

# Copy scraper code
COPY scraper/src/ scraper/src/

# Set working directory to scraper/ so relative imports work
WORKDIR /app/scraper

CMD ["python", "-m", "src"]
