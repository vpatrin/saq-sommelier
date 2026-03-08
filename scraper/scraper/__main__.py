import argparse
import asyncio
import sys

from core.logging import setup_logging

from .commands import availability_check, embed_sync, enrich_wines, scrape_products, scrape_stores
from .config import settings

setup_logging(settings.SERVICE_NAME, level=settings.LOG_LEVEL)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scraper", description="SAQ Sommelier data pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scrape", help="Scrape products from SAQ sitemap (default)")
    sub.add_parser("stores", help="Sync SAQ store directory")
    sub.add_parser("enrich", help="Enrich wine attributes via Adobe API")
    sub.add_parser("embed", help="Sync product embeddings")
    sub.add_parser("availability", help="Check watched-product availability")

    return parser


_COMMANDS: dict[str | None, object] = {
    None: scrape_products,
    "scrape": scrape_products,
    "stores": scrape_stores,
    "enrich": enrich_wines,
    "embed": embed_sync,
    "availability": availability_check,
}

if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()
    runner = _COMMANDS.get(args.command)
    if runner is None:
        parser.print_help()
        sys.exit(1)
    sys.exit(asyncio.run(runner()))
