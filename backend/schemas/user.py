from datetime import datetime

from pydantic import BaseModel


class UserUpdateIn(BaseModel):
    is_active: bool


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    telegram_id: int | None
    username: str | None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}
