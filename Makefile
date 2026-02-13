install:
	cd backend && poetry install
	cd scraper && poetry install

dev:
	cd backend && poetry run uvicorn backend.main:app --reload --port 8000

scrape:
	cd scraper && poetry run python main.py

lint:
	cd backend && poetry run ruff check .
	cd scraper && poetry run ruff check .

format:
	cd backend && poetry run ruff format .
	cd scraper && poetry run ruff format .

test:
	cd backend && poetry run pytest -v
	cd scraper && poetry run pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + && rm -rf .pytest_cache backend/.pytest_cache scraper/.pytest_cache .ruff_cache backend/.ruff_cache scraper/.ruff_cache *.egg-info
