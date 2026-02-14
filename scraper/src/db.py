from datetime import UTC, datetime

from shared.db.base import AsyncSessionLocal
from shared.db.models import Product
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .parser import ProductData


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
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
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
        update_dict = {k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]}
        update_dict["updated_at"] = datetime.now(UTC)  # Always update timestamp

        stmt = stmt.on_conflict_do_update(
            index_elements=["sku"],  # Conflict on primary key (sku)
            set_=update_dict,  # Update these fields
        )

        await session.execute(stmt)
        await session.commit()
