"""Database operations for scraper service.

Handles writing scraped product data to PostgreSQL.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .parser import ProductData

# Add project root to sys.path so shared/ can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.db.base import AsyncSessionLocal
from shared.db.models import Product


async def upsert_product(product_data: ProductData) -> None:
    """Insert or update a product in the database.

    Uses PostgreSQL's INSERT ON CONFLICT DO UPDATE (upsert) to:
    - Insert new product if SKU doesn't exist
    - Update existing product if SKU already exists

    Args:
        product_data: Parsed product data from scraper

    Pattern:
        INSERT INTO products (sku, name, price, ...)
        VALUES (...)
        ON CONFLICT (sku) DO UPDATE
        SET name = EXCLUDED.name, price = EXCLUDED.price, updated_at = NOW()
    """
    async with AsyncSessionLocal() as session:
        # Convert ProductData to dict for database
        product_dict = {
            "sku": product_data.sku,
            "url": product_data.url,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            # JSON-LD fields
            "name": product_data.name,
            "description": product_data.description,
            "category": product_data.category,
            "country": product_data.country,
            "barcode": product_data.barcode,
            "color": product_data.color,
            "size": product_data.size,
            "image": product_data.image,
            "price": product_data.price,
            "currency": product_data.currency,
            "availability": product_data.availability,
            "manufacturer": product_data.manufacturer,
            "rating": product_data.rating,
            "review_count": product_data.review_count,
            # HTML attribute fields
            "region": product_data.region,
            "appellation": product_data.appellation,
            "designation": product_data.designation,
            "classification": product_data.classification,
            "grape": product_data.grape,
            "alcohol": product_data.alcohol,
            "sugar": product_data.sugar,
            "producer": product_data.producer,
            "saq_code": product_data.saq_code,
            "cup_code": product_data.cup_code,
        }

        # PostgreSQL upsert statement
        stmt = pg_insert(Product).values(product_dict)

        # On conflict (SKU already exists), update all fields except sku and created_at
        update_dict = {
            k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]
        }
        update_dict["updated_at"] = datetime.now(timezone.utc)  # Always update timestamp

        stmt = stmt.on_conflict_do_update(
            index_elements=["sku"],  # Conflict on primary key (sku)
            set_=update_dict,  # Update these fields
        )

        await session.execute(stmt)
        await session.commit()


async def bulk_upsert_products(products: list[ProductData]) -> None:
    """Bulk insert or update multiple products.

    More efficient than individual upserts for large batches.

    Args:
        products: List of parsed product data

    Note:
        Uses a single database transaction for all products.
        If one fails, all fail (atomicity).
    """
    if not products:
        return

    async with AsyncSessionLocal() as session:
        for product_data in products:
            product_dict = {
                "sku": product_data.sku,
                "url": product_data.url,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "name": product_data.name,
                "description": product_data.description,
                "category": product_data.category,
                "country": product_data.country,
                "barcode": product_data.barcode,
                "color": product_data.color,
                "size": product_data.size,
                "image": product_data.image,
                "price": product_data.price,
                "currency": product_data.currency,
                "availability": product_data.availability,
                "manufacturer": product_data.manufacturer,
                "rating": product_data.rating,
                "review_count": product_data.review_count,
                "region": product_data.region,
                "appellation": product_data.appellation,
                "designation": product_data.designation,
                "classification": product_data.classification,
                "grape": product_data.grape,
                "alcohol": product_data.alcohol,
                "sugar": product_data.sugar,
                "producer": product_data.producer,
                "saq_code": product_data.saq_code,
                "cup_code": product_data.cup_code,
            }

            stmt = pg_insert(Product).values(product_dict)

            update_dict = {
                k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]
            }
            update_dict["updated_at"] = datetime.now(timezone.utc)

            stmt = stmt.on_conflict_do_update(
                index_elements=["sku"],
                set_=update_dict,
            )

            await session.execute(stmt)

        await session.commit()
