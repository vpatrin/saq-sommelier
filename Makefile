install:
	poetry install

dev:
	poetry run uvicorn app.main:app --reload --port 8000

test:
	poetry run pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + && rm -rf .pytest_cache *.egg-info
