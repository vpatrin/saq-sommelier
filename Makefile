# Load root .env and export to all child processes (bare-metal dev).
# -include: don't fail if .env is missing (CI, fresh clone).
# export: make vars available to commands (poetry run, pytest, etc.).
-include .env
export

.PHONY: install dev scrape migrate revision squash reset-db lint-backend lint-scraper lint-core lint format-backend format-scraper format-core format test-backend test-scraper test coverage-backend coverage-scraper coverage build-backend build-scraper build up down clean

install:
	git config core.hooksPath .githooks
	cd backend && poetry install
	cd scraper && poetry install
	cd core && poetry install

dev:
	cd backend && poetry run uvicorn backend.app:app --reload --port 8000

scrape:
	cd scraper && poetry run python -m src

# Database migrations
migrate:
	cd core && poetry run alembic upgrade head

revision:
	@test -n "$(msg)" || (echo "Usage: make revision msg=\"description\"" && exit 1)
	cd core && poetry run alembic revision --autogenerate -m "$(msg)"

squash:
	@echo "▶ Squashing all migrations into one initial migration"
	cd core && poetry run alembic downgrade base
	rm -f core/alembic/versions/*.py
	cd core && poetry run alembic revision --autogenerate -m "initial schema"
	@echo "⚠ Hand-add CREATE EXTENSION statements to the generated migration"
	@echo "⚠ Then run: make reset-db"

reset-db:
	cd core && poetry run alembic downgrade base && poetry run alembic upgrade head

# Lint
lint-backend:
	@echo "\n▶ Linting backend/"
	cd backend && poetry run ruff check . && poetry run ruff format --check .

lint-scraper:
	@echo "\n▶ Linting scraper/"
	cd scraper && poetry run ruff check . && poetry run ruff format --check .

lint-core:
	@echo "\n▶ Linting core/"
	cd core && poetry run ruff check . && poetry run ruff format --check .

lint: lint-backend lint-scraper lint-core

# Format
format-backend:
	@echo "\n▶ Formatting backend/"
	cd backend && poetry run ruff format . && poetry run ruff check --fix .

format-scraper:
	@echo "\n▶ Formatting scraper/"
	cd scraper && poetry run ruff format . && poetry run ruff check --fix .

format-core:
	@echo "\n▶ Formatting core/"
	cd core && poetry run ruff format . && poetry run ruff check --fix .

format: format-backend format-scraper format-core

# Test
test-backend:
	@echo "\n▶ Testing backend/"
	cd backend && poetry run pytest -v

test-scraper:
	@echo "\n▶ Testing scraper/"
	cd scraper && poetry run pytest -v

test: test-backend test-scraper

# Coverage
coverage-backend:
	@echo "\n▶ Coverage backend/"
	cd backend && poetry run pytest --cov --cov-report=term --cov-report=xml

coverage-scraper:
	@echo "\n▶ Coverage scraper/"
	cd scraper && poetry run pytest --cov --cov-report=term --cov-report=xml

coverage: coverage-backend coverage-scraper
	@echo "\n▶ Generating badges"
	python scripts/generate_badges.py

# Build
build-backend:
	docker build -f backend/Dockerfile -t saq-backend .

build-scraper:
	docker build -f scraper/Dockerfile -t saq-scraper .

build: build-backend build-scraper

# Docker Compose (local dev)
up:
	docker compose --profile dev up -d postgres

down:
	docker compose --profile dev down

clean:
	@echo "\n▶ Cleaning caches"
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache backend/.pytest_cache scraper/.pytest_cache
	rm -rf .ruff_cache backend/.ruff_cache scraper/.ruff_cache core/.ruff_cache
	rm -rf *.egg-info
