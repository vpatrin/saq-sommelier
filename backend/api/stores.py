from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import (
    DEFAULT_NEARBY_LIMIT,
    MAX_NEARBY_LIMIT,
    MAX_SAQ_STORE_ID_LENGTH,
    MAX_USER_ID_LENGTH,
)
from backend.db import get_db
from backend.schemas.store import AddStorePreference, StoreWithDistance, UserStorePreferenceOut
from backend.services.stores import (
    add_user_store,
    get_nearby_stores,
    get_user_stores,
    remove_user_store,
)

stores_router = APIRouter(prefix="/stores", tags=["stores"])
users_router = APIRouter(prefix="/users", tags=["stores"])


@stores_router.get("/nearby", response_model=list[StoreWithDistance])
async def nearby_stores(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    limit: int = Query(default=DEFAULT_NEARBY_LIMIT, ge=1, le=MAX_NEARBY_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> list[StoreWithDistance]:
    """Return the nearest SAQ stores to the given GPS coordinates."""
    return await get_nearby_stores(db, lat, lng, limit)


@users_router.get("/{user_id}/stores", response_model=list[UserStorePreferenceOut])
async def list_user_stores(
    user_id: str = Path(min_length=1, max_length=MAX_USER_ID_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> list[UserStorePreferenceOut]:
    """List a user's preferred stores."""
    return await get_user_stores(db, user_id)


@users_router.post(
    "/{user_id}/stores",
    response_model=UserStorePreferenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_store_preference(
    body: AddStorePreference,
    user_id: str = Path(min_length=1, max_length=MAX_USER_ID_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> UserStorePreferenceOut:
    """Add a store to the user's preferred stores."""
    return await add_user_store(db, user_id, body.saq_store_id)


@users_router.delete(
    "/{user_id}/stores/{saq_store_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_store_preference(
    user_id: str = Path(min_length=1, max_length=MAX_USER_ID_LENGTH),
    saq_store_id: str = Path(min_length=1, max_length=MAX_SAQ_STORE_ID_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a store from the user's preferred stores."""
    await remove_user_store(db, user_id, saq_store_id)
