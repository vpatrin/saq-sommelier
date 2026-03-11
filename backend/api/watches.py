from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_caller_user_id, resolve_user_id
from backend.config import MAX_SKU_LENGTH, MAX_USER_ID_LENGTH
from backend.db import get_db
from backend.schemas.watch import AckIn, NotificationOut, WatchIn, WatchWithProduct
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
    body: WatchIn,
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> WatchWithProduct:
    """Create a watch on a product for a user."""
    user_id = resolve_user_id(caller_user_id, body.user_id)
    return await create_watch(db, user_id, body.sku)


@router.get("", response_model=list[WatchWithProduct])
async def get_watches(
    user_id: str | None = Query(default=None, min_length=1, max_length=MAX_USER_ID_LENGTH),
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[WatchWithProduct]:
    """List all watches for a user, with product details."""
    resolved = resolve_user_id(caller_user_id, user_id)
    return await list_watches(db, resolved)


@router.get(
    "/notifications",
    response_model=list[NotificationOut],
)
async def get_pending_notifications(
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    """List all pending stock event notifications (for bot polling)."""
    return await list_pending_notifications(db)


@router.post(
    "/notifications/ack",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def ack_notifications_endpoint(
    body: AckIn,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Acknowledge processed notifications (mark as sent)."""
    await ack_notifications(db, body.event_ids)


@router.delete("/{sku}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watch(
    sku: str = Path(max_length=MAX_SKU_LENGTH),
    user_id: str | None = Query(default=None, min_length=1, max_length=MAX_USER_ID_LENGTH),
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a watch. JWT callers derive user_id from token; bot passes it explicitly."""
    resolved = resolve_user_id(caller_user_id, user_id)
    await delete_watch(db, resolved, sku)
