from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ForbiddenError, NotFoundError
from backend.repositories import tastings as repo
from backend.schemas.tasting import TastingOut


def _to_out(note, product) -> TastingOut:
    return TastingOut(
        id=note.id,
        sku=note.sku,
        rating=note.rating,
        notes=note.notes,
        pairing=note.pairing,
        tasted_at=note.tasted_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
        product_name=product.name if product else None,
        product_image_url=product.image if product else None,
    )


async def create_tasting(
    db: AsyncSession,
    user_id: str | None,
    sku: str,
    rating: int,
    notes: str | None,
    pairing: str | None,
    tasted_at: date | None,
) -> TastingOut:
    effective_date = tasted_at or date.today()
    try:
        note = await repo.create(db, user_id, sku, rating, notes, pairing, effective_date)
    except IntegrityError as exc:
        await db.rollback()
        raise NotFoundError("Product", sku) from exc
    return TastingOut(
        id=note.id,
        sku=note.sku,
        rating=note.rating,
        notes=note.notes,
        pairing=note.pairing,
        tasted_at=note.tasted_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
        product_name=None,
        product_image_url=None,
    )


async def list_tastings(
    db: AsyncSession,
    user_id: str | None,
    limit: int,
    offset: int,
) -> list[TastingOut]:
    rows = await repo.find_by_user(db, user_id, limit, offset)
    return [_to_out(note, product) for note, product in rows]


async def update_tasting(
    db: AsyncSession,
    user_id: str | None,
    note_id: int,
    rating: int | None,
    notes: str | None,
    pairing: str | None,
    tasted_at: date | None,
) -> TastingOut:
    note = await repo.find_one(db, note_id)
    if note is None:
        raise NotFoundError("TastingNote", str(note_id))
    if note.user_id != user_id:
        raise ForbiddenError
    updated = await repo.update(db, note, rating, notes, pairing, tasted_at)
    return TastingOut(
        id=updated.id,
        sku=updated.sku,
        rating=updated.rating,
        notes=updated.notes,
        pairing=updated.pairing,
        tasted_at=updated.tasted_at,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        product_name=None,
        product_image_url=None,
    )


async def delete_tasting(db: AsyncSession, user_id: str, note_id: int) -> None:
    note = await repo.find_one(db, note_id)
    if note is None:
        raise NotFoundError("TastingNote", str(note_id))
    if note.user_id != user_id:
        raise ForbiddenError
    await repo.delete(db, note)
