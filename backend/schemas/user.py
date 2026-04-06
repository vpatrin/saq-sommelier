from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserUpdateIn(BaseModel):
    is_active: bool


class UserUpdateSelfIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: Literal["fr", "en"] | None = None


class UserMeOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    locale: str | None
    role: str

    model_config = {"from_attributes": True}


class OAuthAccountOut(BaseModel):
    provider: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    telegram_id: int | None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}
