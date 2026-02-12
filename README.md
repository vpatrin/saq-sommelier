# SAQ Sommelier

AI-powered wine recommendation platform — SAQ catalog scraper, Claude RAG, Telegram bot & web app.

## Stack

- **Backend**: Python 3.12 + FastAPI
- **Database**: PostgreSQL 16 (async via SQLAlchemy + asyncpg)
- **Scraping**: httpx + BeautifulSoup4 (SAQ sitemap + product pages)
- **Migrations**: Alembic
- **Deployment**: Docker + Docker Compose + Caddy

## Setup

### Prerequisites

- Python 3.12+
- shared-postgres running (Docker)
- SAQ database + user created in shared-postgres

### Local development

```bash
# Copy env file and edit with your DB credentials
cp .env.example .env

# Install dependencies
pip install -e ".[dev]"

# Start shared-postgres + run migrations
make deps
make migrate

# Start the dev server
make dev
```

### Run the scraper

```bash
make scrape
```

### Run tests

```bash
make test
```

### Production (Docker)

```bash
make up
```

## API

- `GET /api/products` — list products (filters: `region`, `type`, `country`, `price_min`, `price_max`, `available`)
- `GET /api/products/{saq_code}` — get a single product by SAQ code

## Project structure

```text
app/
├── main.py              # FastAPI app
├── config.py            # Pydantic Settings
├── database.py          # SQLAlchemy async engine + session
├── models/product.py    # Product model
├── scraper/
│   ├── sitemap.py       # SAQ XML sitemap parser
│   └── product_parser.py # Product page HTML parser
├── services/
│   └── scraper_service.py # Scraper orchestration
└── api/products.py      # REST endpoints
```
