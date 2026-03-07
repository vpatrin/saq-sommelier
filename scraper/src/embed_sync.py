import time

from core.embedding_client import create_embeddings
from loguru import logger

from .config import settings
from .constants import EXIT_FATAL, EXIT_OK
from .db import bulk_update_embeddings, get_products_needing_embedding
from .embed import build_embedding_text


async def embed_sync() -> int:
    """Compute and store embeddings for products with stale or missing vectors.

    Workflow:
    1. Query products where computed hash != last_embedded_hash
    2. Build embedding text from product fields
    3. Call OpenAI API in batches
    4. Store vectors + update last_embedded_hash
    """
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot run --embed-sync")
        return EXIT_FATAL

    start = time.monotonic()

    products = await get_products_needing_embedding()
    if not products:
        logger.info("All embeddings up to date — nothing to sync")
        return EXIT_OK

    logger.info("Found {} products needing embedding", len(products))

    # Build texts and collect field dicts for hash verification
    texts: list[str] = []
    skus: list[str] = []
    hashes: list[str] = []

    for p in products:
        text = build_embedding_text(
            category=p["category"],
            taste_tag=p["taste_tag"],
            tasting_profile=p["tasting_profile"],
            grape_blend=p["grape_blend"],
            grape=p["grape"],
            producer=p["producer"],
            region=p["region"],
            appellation=p["appellation"],
            designation=p["designation"],
            classification=p["classification"],
            country=p["country"],
            vintage=p["vintage"],
            description=p["description"],
        )
        if not text:
            logger.debug("Skipping SKU {} — empty embedding text", p["sku"])
            continue

        texts.append(text)
        skus.append(p["sku"])
        hashes.append(p["_computed_hash"])

    if not texts:
        logger.info("No products with non-empty embedding text — nothing to sync")
        return EXIT_OK

    logger.info("Embedding {} products via OpenAI API...", len(texts))
    try:
        vectors = create_embeddings(texts, api_key=settings.OPENAI_API_KEY)
    except Exception as exc:
        logger.opt(exception=exc).error("OpenAI API call failed")
        return EXIT_FATAL

    # Build update payloads
    updates = [
        {"sku": sku, "embedding": vector, "last_embedded_hash": h}
        for sku, vector, h in zip(skus, vectors, hashes)
    ]

    try:
        count = await bulk_update_embeddings(updates)
    except Exception as exc:
        logger.opt(exception=exc).error("Failed to store embeddings")
        return EXIT_FATAL

    elapsed = time.monotonic() - start
    logger.info(
        "Embed sync complete: {} products embedded in {:.1f}s",
        count,
        elapsed,
    )
    return EXIT_OK
