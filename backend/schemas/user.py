from datetime import datetime

from pydantic import BaseModel, Field


class UserUpdateIn(BaseModel):
    is_active: bool


class UserUpdateSelfIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


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
