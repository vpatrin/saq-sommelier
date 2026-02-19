# Load root .env and export to all child processes (bare-metal dev).
# -include: don't fail if .env is missing (CI, fresh clone).
# export: make vars available to commands (poetry run, pytest, etc.).
-include .env
export

.PHONY: install dev-backend dev-bot dev-scraper migrate revision reset-db lint-backend lint-scraper lint-core lint-bot lint format-backend format-scraper format-core format-bot format test-backend test-scraper test-bot test coverage-backend coverage-scraper coverage-bot coverage build-backend build-scraper build-bot build run run-db run-scraper down clean

install:
	git config core.hooksPath .githooks
	cd backend && poetry lock && poetry install
	cd scraper && poetry lock && poetry install
	cd core && poetry lock && poetry install
	cd bot && poetry lock && poetry install

dev-backend:
	cd backend && poetry run uvicorn backend.app:app --reload --port 8000

dev-bot:
	cd bot && poetry run python -m bot

dev-scraper:
	cd scraper && poetry run python -m src

# Database migrations
migrate:
	cd core && poetry run alembic upgrade head

revision:
	@test -n "$(msg)" || (echo "Usage: make revision msg=\"description\"" && exit 1)
	cd core && poetry run alembic revision --autogenerate -m "$(msg)"

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

lint-bot:
	@echo "\n▶ Linting bot/"
	cd bot && poetry run ruff check . && poetry run ruff format --check .

lint: lint-backend lint-scraper lint-core lint-bot

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

format-bot:
	@echo "\n▶ Formatting bot/"
	cd bot && poetry run ruff format . && poetry run ruff check --fix .

format: format-backend format-scraper format-core format-bot

# Test
test-backend:
	@echo "\n▶ Testing backend/"
	cd backend && poetry run pytest -v

test-scraper:
	@echo "\n▶ Testing scraper/"
	cd scraper && poetry run pytest -v

test-bot:
	@echo "\n▶ Testing bot/"
	cd bot && poetry run pytest -v

test: test-backend test-scraper test-bot

# Coverage
coverage-backend:
	@echo "\n▶ Coverage backend/"
	cd backend && poetry run pytest --cov --cov-report=xml -v && poetry run coverage report

coverage-scraper:
	@echo "\n▶ Coverage scraper/"
	cd scraper && poetry run pytest --cov --cov-report=xml -v && poetry run coverage report

coverage-bot:
	@echo "\n▶ Coverage bot/"
	cd bot && poetry run pytest --cov --cov-report=xml -v && poetry run coverage report

coverage: coverage-backend coverage-scraper coverage-bot
	@echo "\n▶ Generating badges"
	python scripts/generate_badges.py

# Build
build-backend:
	docker build -f backend/Dockerfile -t saq-backend .

build-scraper:
	docker build -f scraper/Dockerfile -t saq-scraper .

build-bot:
	docker build -f bot/Dockerfile -t saq-bot .

build: build-backend build-scraper build-bot

# Docker Compose
run:
	docker compose --profile dev up -d postgres backend bot

run-db:
	docker compose --profile dev up -d postgres

run-scraper:
	docker compose run --rm scraper

down:
	docker compose --profile dev down

clean:
	@echo "\n▶ Cleaning caches"
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache backend/.pytest_cache scraper/.pytest_cache bot/.pytest_cache
	rm -rf .ruff_cache backend/.ruff_cache scraper/.ruff_cache core/.ruff_cache bot/.ruff_cache
	rm -rf *.egg-info
