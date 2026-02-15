import os

# Set fallback DB env vars so that importing backend.db doesn't fail in CI (no .env file).
# Tests mock get_db, so no real DB connection is made.
for var, default in [
    ("DB_USER", "test"),
    ("DB_PASSWORD", "test"),
    ("DB_HOST", "localhost"),
    ("DB_PORT", "5432"),
    ("DB_NAME", "test"),
]:
    os.environ.setdefault(var, default)
