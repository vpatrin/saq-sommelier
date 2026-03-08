from core.db.models import Product
from loguru import logger
from sqlalchemy import bindparam, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..embed import compute_embedding_hash
from .session import SessionLocal

_BULK_CHUNK_SIZE = 1000


async def get_products_needing_embedding() -> list[dict]:
    """Fetch products whose embedding is stale or missing.

    Two-pass approach:
    - Never-embedded (last_embedded_hash IS NULL): always dirty, no hash needed
    - Previously embedded: compute hash in Python, keep only changed rows
    """
    columns = [
        Product.sku,
        Product.category,
        Product.taste_tag,
        Product.tasting_profile,
        Product.grape_blend,
        Product.grape,
        Product.producer,
        Product.region,
        Product.appellation,
        Product.designation,
        Product.classification,
        Product.country,
        Product.vintage,
        Product.description,
        Product.last_embedded_hash,
    ]
    async with SessionLocal() as session:
        # Never-embedded products — guaranteed dirty
        new_rows = await session.execute(
            select(*columns).where(Product.last_embedded_hash.is_(None))
        )
        # Previously embedded — need hash comparison
        existing_rows = await session.execute(
            select(*columns).where(Product.last_embedded_hash.is_not(None))
        )
        new = [row._asdict() for row in new_rows.all()]
        existing = [row._asdict() for row in existing_rows.all()]

    dirty = []
    for row in new:
        row["_computed_hash"] = compute_embedding_hash(row)
        dirty.append(row)
    for row in existing:
        h = compute_embedding_hash(row)
        if h != row["last_embedded_hash"]:
            row["_computed_hash"] = h
            dirty.append(row)
    return dirty


async def bulk_update_embeddings(
    updates: list[dict],
) -> int:
    """Batch-update embedding vectors and last_embedded_hash."""
    if not updates:
        return 0
    table = Product.__table__
    stmt = (
        update(table)
        .where(table.c.sku == bindparam("_sku"))
        .values(
            embedding=bindparam("_embedding"),
            last_embedded_hash=bindparam("_hash"),
        )
    )
    params = [
        {"_sku": u["sku"], "_embedding": u["embedding"], "_hash": u["last_embedded_hash"]}
        for u in updates
    ]
    async with SessionLocal() as session:
        try:
            for i in range(0, len(params), _BULK_CHUNK_SIZE):
                chunk = params[i : i + _BULK_CHUNK_SIZE]
                await session.execute(stmt, chunk)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "Failed to bulk-update embeddings for {} SKUs", len(updates)
            )
            raise
    return len(updates)


async def bulk_update_wine_attrs(
    updates: dict[str, dict[str, str | list | dict | None]],
) -> int:
    """Batch-update wine attributes (taste_tag, vintage, tasting_profile, grape_blend)."""
    if not updates:
        return 0
    all_params = [
        {
            "_sku": sku,
            "taste_tag": attrs.get("taste_tag"),
            "vintage": attrs.get("vintage"),
            "tasting_profile": attrs.get("tasting_profile"),
            "grape_blend": attrs.get("grape_blend"),
        }
        for sku, attrs in updates.items()
    ]
    table = Product.__table__
    stmt = (
        update(table)
        .where(table.c.sku == bindparam("_sku"))
        .values(
            taste_tag=bindparam("taste_tag"),
            vintage=bindparam("vintage"),
            tasting_profile=bindparam("tasting_profile"),
            grape_blend=bindparam("grape_blend"),
        )
    )
    async with SessionLocal() as session:
        try:
            for i in range(0, len(all_params), _BULK_CHUNK_SIZE):
                chunk = all_params[i : i + _BULK_CHUNK_SIZE]
                await session.execute(stmt, chunk)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "Failed to bulk-update wine attributes for {} SKUs", len(updates)
            )
            raise
    return len(updates)
