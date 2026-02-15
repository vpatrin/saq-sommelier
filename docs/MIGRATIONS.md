# Alembic Primer — Database Migrations for SAQ Sommelier

## What is Alembic?

Alembic is **version control for your database schema**. Just like Git tracks code changes, Alembic tracks database structure changes (tables, columns, indexes, constraints).

Think of it as a migration tool that bridges the gap between your Python models (SQLAlchemy) and your actual PostgreSQL database.

## Why Use Migrations Instead of Manual SQL Scripts?

**IMPORTANT:** SQLAlchemy models alone don't create database tables. The `Product` class in [core/db/models.py](../core/db/models.py) is just Python code - it doesn't touch PostgreSQL until you explicitly create the table.

You have three options to create tables:

### Option 1: One giant init_db.sql (anti-pattern)

```sql
-- init_db.sql
DROP DATABASE IF EXISTS wine_sommelier;
CREATE DATABASE wine_sommelier;
CREATE TABLE products (...);
-- recreate everything from scratch
```

**Problem:** Every schema change requires dropping and recreating the database. **You lose all data.**

### Option 2: Numbered SQL scripts (manual migrations)

```sql
-- 001_create_products.sql
CREATE TABLE products (sku VARCHAR PRIMARY KEY, ...);

-- 002_add_vintage_column.sql
ALTER TABLE products ADD COLUMN vintage VARCHAR;

-- 003_add_index_on_price.sql
CREATE INDEX idx_price ON products(price);
```

**Problems:**

- Manual tracking (which scripts ran on which environment?)
- No automatic ordering enforcement
- No rollback mechanism
- Error-prone (easy to skip a script or run them out of order)
- Doesn't scale past solo dev

### Option 3: Alembic migrations (production-grade)

```bash
alembic revision --autogenerate -m "create products table"
alembic upgrade head
```

**Benefits:**

- ✅ Automatic version tracking (`alembic_version` table in database)
- ✅ Automatic ordering (chronological, enforced)
- ✅ Built-in rollback (`alembic downgrade -1`)
- ✅ Git history shows exactly what changed and when
- ✅ Autogenerate detects model changes (no manual SQL writing)
- ✅ Team-friendly (everyone runs same migrations)
- ✅ Production-safe (review migrations before applying)

**This is why we use Alembic.** It's the industry standard for Python + SQLAlchemy projects.

## Why Set It Up Before the First Migration?

Alembic needs **configuration** before it can generate migrations:

1. **Database URL** — Where to connect (PostgreSQL)
2. **Target metadata** — Your SQLAlchemy models (the "desired state")
3. **Async/Sync conversion** — Our app uses async (asyncpg), but Alembic runs migrations synchronously (psycopg2)

Setting this up first means when you run `alembic revision --autogenerate`, Alembic already knows:

- Where the database is
- What your models look like (from `Base.metadata`)
- How to compare them and generate the migration script

Without this setup, `--autogenerate` would fail or produce empty migrations.

## How Alembic Works

Alembic compares two things:

1. **Target** (desired state) — Your SQLAlchemy models in `core/db/models.py`
2. **Current** (actual state) — What's currently in the PostgreSQL database

Then it generates a **migration script** with the SQL commands needed to transform Current → Target.

Example:

- You add a `alcohol` column to the `Product` model
- Alembic detects the difference
- It generates a migration with `ALTER TABLE products ADD COLUMN alcohol VARCHAR`
- You run the migration
- Database now matches your models

## What We Customized in env.py

Out of the box, `alembic init` generates `env.py` with boilerplate only. We customized **SECTION 2** with:

### 1. Import Base (for autogenerate)

```python
from core.db.base import Base
```

**Why:** Alembic needs to see your models to detect schema changes.

**Without this:** `--autogenerate` won't work.

### 2. Import Settings (for DATABASE_URL)

```python
from core.config.settings import settings
```

**Why:** Don't hardcode credentials in `alembic.ini`, read from environment.

**Standard practice:** 12-factor apps, Docker deployments.

### 3. Override DATABASE_URL (async → sync conversion)

```python
database_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://",  # App runtime (async)
    "postgresql+psycopg2://",  # Alembic migrations (sync)
)
config.set_main_option("sqlalchemy.url", database_url)
```

**Why:** Our app uses async SQLAlchemy (`asyncpg`) for runtime, but Alembic runs migrations synchronously and needs `psycopg2`.

**Standard practice:** Common pattern for FastAPI + async SQLAlchemy projects.

### 4. Set target_metadata

```python
target_metadata = Base.metadata
```

**Why:** This is the "desired state" reference point. Alembic compares `Base.metadata` (your models) vs actual database schema to detect changes.

**Without this:** `--autogenerate` produces empty migrations.

## Migration Workflow

### Development (local)

```bash
# 1. Edit your models in core/db/models.py
vim core/db/models.py

# 2. Generate migration (Alembic detects changes)
alembic revision --autogenerate -m "add alcohol column to products"

# 3. Review generated migration in alembic/versions/
vim alembic/versions/xxxx_add_alcohol_column_to_products.py

# 4. Apply migration
alembic upgrade head

# 5. Commit migration + model changes together
git add core/db/models.py alembic/versions/xxxx_*.py
git commit -m "feat: add alcohol column to Product model"
```

### Production (VPS)

```bash
# 1. Pull latest code (includes migration files)
git pull origin main

# 2. Run migrations
alembic upgrade head

# 3. Restart services (new code sees new schema)
docker-compose restart backend scraper
```

**Important:** Always run migrations BEFORE restarting services. If your new code expects a column that doesn't exist yet, the app will crash.

## Common Commands

```bash
# Check current database version
alembic current

# Generate a new migration (autogenerate)
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

## Key Concepts

### Migrations are Code

Each migration is a Python script in `alembic/versions/` with:

- **upgrade()** — Apply changes (add column, create table)
- **downgrade()** — Revert changes (drop column, drop table)

These run sequentially in chronological order.

### target_metadata is NOT a Command

It's a **reference point** for autogenerate. When you run `alembic revision --autogenerate`, Alembic compares:

- `target_metadata` (your models) — "desired state"
- Current database schema — "actual state"

The migration script it generates transforms actual → desired.

### Async App, Sync Migrations

Our FastAPI app runs async (uses `asyncpg` driver), but Alembic migrations run synchronously (use `psycopg2` driver).

This is why `env.py` converts the URL:

- Runtime: `postgresql+asyncpg://user:pass@host/db`
- Migrations: `postgresql+psycopg2://user:pass@host/db`

Same database, different drivers.

### Alembic Version Table

Alembic creates a table `alembic_version` in your database:

```sql
wine_sommelier=# SELECT * FROM alembic_version;
 version_num
--------------
 abc123def456
```

This tracks which migrations have been applied. When you run `alembic upgrade head`, it checks this table and only runs pending migrations.

## Best Practices

1. **Always review autogenerated migrations** — Alembic isn't perfect, sometimes it generates wrong SQL
2. **Test migrations on dev first** — Never run untested migrations on production
3. **Commit migrations with model changes** — They belong together in version control
4. **Never edit applied migrations** — Create a new migration to fix mistakes
5. **Keep migrations small** — One logical change per migration (easier to review and rollback)
6. **Run migrations before restarting services** — Avoids crashes from schema/code mismatch

## Troubleshooting

### "Target database is not up to date"

Run `alembic upgrade head` to apply pending migrations.

### "Can't locate revision identified by 'xxxx'"

Your local `alembic/versions/` is out of sync with the database. Pull latest code.

### Autogenerate creates empty migration

Check that:

- `target_metadata = Base.metadata` is set in `env.py`
- Your models are imported somewhere (via `core.db.__init__.py`)
- You actually changed the models since last migration

### Connection refused

Check that PostgreSQL is running and `DATABASE_URL` in `.env` is correct.

## Quick Reference

| Task                   | Command                                       |
|------------------------|-----------------------------------------------|
| Check current version  | `alembic current`                             |
| Generate migration     | `alembic revision --autogenerate -m "msg"`    |
| Apply migrations       | `alembic upgrade head`                        |
| Rollback one           | `alembic downgrade -1`                        |
| Show history           | `alembic history`                             |
| Create empty migration | `alembic revision -m "msg"`                   |

## Further Reading

- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLAlchemy Metadata](https://docs.sqlalchemy.org/en/20/core/metadata.html)
