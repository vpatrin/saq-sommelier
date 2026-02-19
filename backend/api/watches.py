from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import MAX_SKU_LENGTH, MAX_USER_ID_LENGTH
from backend.db import get_db
from backend.schemas.watch import AckRequest, PendingNotification, WatchCreate, WatchWithProduct
from backend.services.watches import (
    ack_notifications,
    create_watch,
    delete_watch,
    list_pending_notifications,
    list_watches,
)

router = APIRouter(prefix="/watches", tags=["watches"])


@router.post("", response_model=WatchWithProduct, status_code=status.HTTP_201_CREATED)
async def post_watch(
    body: WatchCreate,
    db: AsyncSession = Depends(get_db),
) -> WatchWithProduct:
    """Create a watch on a product for a user."""
    return await create_watch(db, body.user_id, body.sku)


@router.get("", response_model=list[WatchWithProduct])
async def get_watches(
    user_id: str = Query(min_length=1, max_length=MAX_USER_ID_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> list[WatchWithProduct]:
    """List all watches for a user, with product details."""
    return await list_watches(db, user_id)


@router.get("/notifications", response_model=list[PendingNotification])
async def get_pending_notifications(
    db: AsyncSession = Depends(get_db),
) -> list[PendingNotification]:
    """List all pending restock notifications (for bot polling)."""
    return await list_pending_notifications(db)


@router.post("/notifications/ack", status_code=status.HTTP_204_NO_CONTENT)
async def ack_notifications_endpoint(
    body: AckRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Acknowledge processed notifications (mark as sent)."""
    await ack_notifications(db, body.event_ids)


@router.delete("/{sku}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watch(
    sku: str = Path(max_length=MAX_SKU_LENGTH),
    user_id: str = Query(min_length=1, max_length=MAX_USER_ID_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a watch. user_id passed as query param (no auth)."""
    await delete_watch(db, user_id, sku)
