install:
	poetry install

dev:
	poetry run uvicorn app.main:app --reload --port 8000

lint:
	cd backend && poetry run ruff check .

format:
	cd backend && poetry run ruff format .

test:
	cd backend && poetry run pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + && rm -rf .pytest_cache backend/.pytest_cache .ruff_cache backend/.ruff_cache *.egg-info
