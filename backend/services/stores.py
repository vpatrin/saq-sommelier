import math

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import stores as repo
from backend.schemas.store import StoreOut, StoreWithDistance, UserStorePreferenceOut


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculates the shortest path along the Earth's surface between two GPS points"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


async def get_nearby_stores(
    db: AsyncSession, lat: float, lng: float, limit: int
) -> list[StoreWithDistance]:
    """Return the nearest stores to the given coordinates, sorted by distance.

    Stores without GPS coordinates are excluded.
    """
    stores = await repo.get_all_stores(db)
    results: list[StoreWithDistance] = []
    for store in stores:
        if store.latitude is None or store.longitude is None:
            continue
        dist = _haversine_km(lat, lng, store.latitude, store.longitude)
        store_data = StoreOut.model_validate(store).model_dump()
        results.append(StoreWithDistance(**store_data, distance_km=dist))
    results.sort(key=lambda s: s.distance_km)
    return results[:limit]


async def get_user_stores(db: AsyncSession, user_id: str) -> list[UserStorePreferenceOut]:
    """Return a user's preferred stores."""
    rows = await repo.get_user_stores(db, user_id)
    return [
        UserStorePreferenceOut(
            saq_store_id=pref.saq_store_id,
            created_at=pref.created_at,
            store=StoreOut.model_validate(store),
        )
        for pref, store in rows
    ]


async def add_user_store(
    db: AsyncSession, user_id: str, saq_store_id: str
) -> UserStorePreferenceOut:
    """Add a store preference for a user.

    Raises NotFoundError if the store doesn't exist, ConflictError if already added.
    """
    store = await repo.get_store_by_id(db, saq_store_id)
    if store is None:
        raise NotFoundError("Store", saq_store_id)
    try:
        pref = await repo.add_user_store(db, user_id, saq_store_id)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "UserStorePreference",
            f"user {user_id!r} already has store {saq_store_id!r}",
        ) from exc
    return UserStorePreferenceOut(
        saq_store_id=pref.saq_store_id,
        created_at=pref.created_at,
        store=StoreOut.model_validate(store),
    )


async def remove_user_store(db: AsyncSession, user_id: str, saq_store_id: str) -> None:
    """Remove a store preference. Raises NotFoundError if it doesn't exist."""
    deleted = await repo.remove_user_store(db, user_id, saq_store_id)
    if not deleted:
        raise NotFoundError("UserStorePreference", saq_store_id)
