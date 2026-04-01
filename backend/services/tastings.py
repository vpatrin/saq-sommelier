from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ForbiddenError, NotFoundError
from backend.repositories import tastings as repo
from backend.schemas.tasting import TastingOut
from core.db.models import TastingNote


async def _get_owned_note(db: AsyncSession, user_id: str | None, note_id: int) -> TastingNote:
    note = await repo.find_one(db, note_id)
    if note is None:
        raise NotFoundError("TastingNote", str(note_id))
    if note.user_id != user_id:
        raise ForbiddenError
    return note


async def create_tasting(
    db: AsyncSession,
    user_id: str | None,
    sku: str,
    rating: int,
    notes: str | None,
    pairing: str | None,
    tasted_at: date | None,
) -> TastingOut:
    effective_date = tasted_at if tasted_at is not None else date.today()
    try:
        note = await repo.create(db, user_id, sku, rating, notes, pairing, effective_date)
    except IntegrityError as exc:
        await db.rollback()
        raise NotFoundError("Product", sku) from exc
    return TastingOut.model_validate(note)


async def list_tastings(
    db: AsyncSession,
    user_id: str | None,
    limit: int,
    offset: int,
) -> list[TastingOut]:
    rows = await repo.find_by_user(db, user_id, limit, offset)
    return [
        TastingOut.model_validate(note).model_copy(
            update={
                "product_name": product.name if product else None,
                "product_image_url": product.image if product else None,
            }
        )
        for note, product in rows
    ]


async def update_tasting(
    db: AsyncSession,
    user_id: str | None,
    note_id: int,
    rating: int | None,
    notes: str | None,
    pairing: str | None,
    tasted_at: date | None,
) -> TastingOut:
    note = await _get_owned_note(db, user_id, note_id)
    updated = await repo.update(db, note, rating, notes, pairing, tasted_at)
    return TastingOut.model_validate(updated)


async def delete_tasting(db: AsyncSession, user_id: str | None, note_id: int) -> None:
    note = await _get_owned_note(db, user_id, note_id)
    await repo.delete(db, note)
