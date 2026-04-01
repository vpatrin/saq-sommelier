from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Product, TastingNote


async def create(
    db: AsyncSession,
    user_id: str | None,
    sku: str,
    rating: int,
    notes: str | None,
    pairing: str | None,
    tasted_at: date,
) -> TastingNote:
    note = TastingNote(
        user_id=user_id,
        sku=sku,
        rating=rating,
        notes=notes,
        pairing=pairing,
        tasted_at=tasted_at,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def find_by_user(
    db: AsyncSession,
    user_id: str | None,
    limit: int,
    offset: int,
) -> list[tuple[TastingNote, Product | None]]:
    stmt = (
        select(TastingNote, Product)
        .outerjoin(Product, TastingNote.sku == Product.sku)
        .where(TastingNote.user_id == user_id)
        .order_by(TastingNote.tasted_at.desc(), TastingNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.all())


async def find_one(db: AsyncSession, note_id: int) -> TastingNote | None:
    stmt = select(TastingNote).where(TastingNote.id == note_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update(
    db: AsyncSession,
    note: TastingNote,
    rating: int | None,
    notes: str | None,
    pairing: str | None,
    tasted_at: date | None,
) -> TastingNote:
    if rating is not None:
        note.rating = rating
    if notes is not None:
        note.notes = notes
    if pairing is not None:
        note.pairing = pairing
    if tasted_at is not None:
        note.tasted_at = tasted_at
    await db.flush()
    await db.refresh(note)
    return note


async def delete(db: AsyncSession, note: TastingNote) -> None:
    await db.delete(note)
    await db.flush()
