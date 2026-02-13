.PHONY: install dev scrape lint-backend lint-scraper lint format-backend format-scraper format test-backend test-scraper test build-scraper build clean

install:
	cd backend && poetry install
	cd scraper && poetry install

dev:
	cd backend && poetry run uvicorn backend.main:app --reload --port 8000

scrape:
	cd scraper && poetry run python -m src

# Lint
lint-backend:
	cd backend && poetry run ruff check . && poetry run ruff format --check .

lint-scraper:
	cd scraper && poetry run ruff check . && poetry run ruff format --check .

lint: lint-backend lint-scraper

# Format
format-backend:
	cd backend && poetry run ruff format . && poetry run ruff check --fix .

format-scraper:
	cd scraper && poetry run ruff format . && poetry run ruff check --fix .

format: format-backend format-scraper

# Test
test-backend:
	cd backend && poetry run pytest -v

test-scraper:
	cd scraper && poetry run pytest -v

test: test-backend test-scraper

# Build
build-scraper:
	docker build -t saq-scraper scraper/

build: build-scraper

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache backend/.pytest_cache scraper/.pytest_cache
	rm -rf .ruff_cache backend/.ruff_cache scraper/.ruff_cache
	rm -rf *.egg-info
