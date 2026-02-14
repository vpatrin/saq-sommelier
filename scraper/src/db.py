from datetime import UTC, datetime

from shared.db.base import create_session_factory
from shared.db.models import Product
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .config import settings
from .parser import ProductData

_SessionLocal = create_session_factory(settings.database_url, settings.database_echo)


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
    async with _SessionLocal() as session:
        product_dict = product_data.to_dict()
        product_dict["created_at"] = datetime.now(UTC)
        product_dict["updated_at"] = datetime.now(UTC)

        stmt = pg_insert(Product).values(product_dict)

        # On conflict (SKU already exists), update all fields except sku and created_at
        update_dict = {k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]}
        update_dict["updated_at"] = datetime.now(UTC)

        stmt = stmt.on_conflict_do_update(
            index_elements=["sku"],  # Conflict on primary key (sku)
            set_=update_dict,  # Update these fields
        )

        await session.execute(stmt)
        await session.commit()
