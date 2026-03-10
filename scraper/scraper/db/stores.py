from dataclasses import asdict
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import Store

from ..stores import StoreData
from .session import SessionLocal


async def get_montreal_store_ids() -> list[str]:
    """Get consumer-facing Montreal store IDs (excludes SAQ Restauration)."""
    async with SessionLocal() as session:
        stmt = (
            select(Store.saq_store_id)
            .where(Store.city == "Montréal")
            .where(Store.store_type != "SAQ Restauration")
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def upsert_stores(stores: list[StoreData]) -> None:
    """Bulk upsert stores into the database."""
    if not stores:
        return

    now = datetime.now(UTC)
    values_list = [{**asdict(store), "created_at": now} for store in stores]

    # Preserve created_at on re-runs — same semantics as Product.created_at
    update_cols = [c for c in values_list[0] if c not in ("saq_store_id", "created_at")]

    async with SessionLocal() as session:
        stmt = pg_insert(Store).values(values_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=list(Store.__table__.primary_key),
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error("DB error upserting {} stores", len(stores))
            raise
