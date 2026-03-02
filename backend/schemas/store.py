from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.config import MAX_SAQ_STORE_ID_LENGTH


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    saq_store_id: str
    name: str
    store_type: str | None
    address: str | None
    city: str
    postcode: str | None
    telephone: str | None
    latitude: float | None
    longitude: float | None
    temporarily_closed: bool


class StoreWithDistance(StoreOut):
    """Store enriched with computed Haversine distance from a query point."""

    distance_km: float


class UserStorePreferenceIn(BaseModel):
    saq_store_id: str = Field(min_length=1, max_length=MAX_SAQ_STORE_ID_LENGTH)


class UserStorePreferenceOut(BaseModel):
    saq_store_id: str
    created_at: datetime
    store: StoreOut
