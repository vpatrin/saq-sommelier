from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_caller_user_id, resolve_user_id
from backend.config import (
    DEFAULT_NEARBY_LIMIT,
    MAX_NEARBY_LIMIT,
    MAX_SAQ_STORE_ID_LENGTH,
    MAX_USER_ID_LENGTH,
)
from backend.db import get_db
from backend.schemas.store import StoreWithDistance, UserStorePreferenceIn, UserStorePreferenceOut
from backend.services.stores import (
    add_user_store,
    get_nearby_stores,
    get_user_stores,
    remove_user_store,
)

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/nearby", response_model=list[StoreWithDistance])
async def nearby_stores(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    limit: int = Query(default=DEFAULT_NEARBY_LIMIT, ge=1, le=MAX_NEARBY_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> list[StoreWithDistance]:
    """Return the nearest SAQ stores to the given GPS coordinates."""
    return await get_nearby_stores(db, lat, lng, limit)


@router.get("/preferences", response_model=list[UserStorePreferenceOut])
async def list_user_stores(
    user_id: str | None = Query(default=None, min_length=1, max_length=MAX_USER_ID_LENGTH),
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[UserStorePreferenceOut]:
    """List the caller's preferred stores."""
    resolved = resolve_user_id(caller_user_id, user_id)
    return await get_user_stores(db, resolved)


@router.post(
    "/preferences",
    response_model=UserStorePreferenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_store_preference(
    body: UserStorePreferenceIn,
    user_id: str | None = Query(default=None, min_length=1, max_length=MAX_USER_ID_LENGTH),
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserStorePreferenceOut:
    """Add a store to the caller's preferred stores."""
    resolved = resolve_user_id(caller_user_id, user_id)
    return await add_user_store(db, resolved, body.saq_store_id)


@router.delete(
    "/preferences/{saq_store_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_store_preference(
    saq_store_id: str = Path(min_length=1, max_length=MAX_SAQ_STORE_ID_LENGTH),
    user_id: str | None = Query(default=None, min_length=1, max_length=MAX_USER_ID_LENGTH),
    caller_user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a store from the caller's preferred stores."""
    resolved = resolve_user_id(caller_user_id, user_id)
    await remove_user_store(db, resolved, saq_store_id)
