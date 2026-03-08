"""Database access layer — split by domain for readability."""

from .availability import (
    bulk_update_availability,
    get_preferred_store_ids,
    get_watched_product_availability,
)
from .embeddings import (
    bulk_update_embeddings,
    bulk_update_wine_attrs,
    get_products_needing_embedding,
)
from .events import delete_old_stock_events, emit_stock_event, get_watched_skus
from .products import (
    clear_delisted,
    get_all_skus,
    get_delisted_skus,
    get_updated_dates,
    mark_delisted,
    upsert_product,
)
from .stores import get_montreal_store_ids, upsert_stores

__all__ = [
    "bulk_update_availability",
    "bulk_update_embeddings",
    "bulk_update_wine_attrs",
    "clear_delisted",
    "delete_old_stock_events",
    "emit_stock_event",
    "get_all_skus",
    "get_delisted_skus",
    "get_montreal_store_ids",
    "get_preferred_store_ids",
    "get_products_needing_embedding",
    "get_updated_dates",
    "get_watched_product_availability",
    "get_watched_skus",
    "mark_delisted",
    "upsert_product",
    "upsert_stores",
]
