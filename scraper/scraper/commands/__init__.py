"""Scraper CLI subcommands — each returns an exit code (0/1/2)."""

from .availability import availability_check
from .embed import embed_sync
from .enrich import enrich_wines
from .scrape import scrape_products
from .stores import scrape_stores

__all__ = [
    "availability_check",
    "embed_sync",
    "enrich_wines",
    "scrape_products",
    "scrape_stores",
]
