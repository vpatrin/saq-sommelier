# Data Flow — Three Schemas, One Product

## The problem

A product passes through three stages: scraping, storage, and API response. Each stage has different requirements. Using a single model for all three creates tight coupling — changing how you scrape forces changes to your API contract.

## The solution

Three separate schemas, one per boundary:

```
SAQ.com HTML                    PostgreSQL                      JSON API
     │                               │                              │
     ▼                               ▼                              ▼
 ProductData                     Product                    ProductResponse
 (dataclass)                  (SQLAlchemy)                    (Pydantic)
     │                               │                              │
 scraper/src/parser.py        core/db/models.py          backend/schemas/product.py
```

## Why each tool

### ProductData — `@dataclass`

The scraper parses messy HTML. Fields might be missing, malformed, or unexpected. A dataclass is a transparent container — it stores whatever you give it without fighting back. Validation happens in your parser logic, not in the data structure.

```python
# Accepts whatever the parser extracts — you handle edge cases yourself
product = ProductData(price=extracted_price, name=extracted_name)
```

If this were Pydantic, every edge case (missing field, wrong type, unexpected format) would need to be declared upfront in the type system. That's the wrong place to handle scraping uncertainty.

### Product — SQLAlchemy Model

The ORM model is the single source of truth for the database schema. Alembic generates migrations from it. Both services import it from `core/db/models.py` — the scraper writes to it, the backend reads from it.

This is the only schema shared across service boundaries, and it's read-only from the backend's perspective.

### ProductResponse — Pydantic `BaseModel`

The API response schema does three things a dataclass can't:

1. **Validates** — guarantees the ORM object has all required fields before serializing
2. **Coerces** — `Decimal` → `"15.99"` (string), `datetime` → ISO 8601, automatically
3. **Filters** — `from_attributes=True` picks only declared fields, silently dropping `description`, `url`, `image` (excluded for legal reasons)

FastAPI reads this schema to generate OpenAPI docs and enforce the response contract. The schema _is_ the API documentation.

## What flows where

| Stage | Schema | Tool | Responsibility |
|-------|--------|------|----------------|
| Scrape | `ProductData` | `@dataclass` | Accept messy input, let parser handle validation |
| Store | `Product` | SQLAlchemy | DB schema, migrations, queries |
| Respond | `ProductResponse` | Pydantic | Strict output contract, serialization, docs |

## Why not one model for everything?

Coupling. If `ProductData` and `ProductResponse` were the same class:

- Adding a scraper field (e.g., `raw_html` for debugging) would leak into the API
- Removing an API field (e.g., `description` for legal reasons) would break the scraper
- Changing serialization (e.g., price precision) would require touching scraper code

With separate schemas, each boundary evolves independently. The database is the only shared contract — and that's enforced by Alembic migrations, not by Python imports.

## The rule of thumb

- **Dataclass** = "I know what I'm putting in" (internal, trusted input)
- **Pydantic** = "I need to guarantee what comes out" (external boundary, untrusted consumers)
- **SQLAlchemy** = "This is how it's stored" (persistence layer)
