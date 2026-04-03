from datetime import datetime

from pydantic import BaseModel, EmailStr


class WaitlistIn(BaseModel):
    email: EmailStr


class WaitlistRequestOut(BaseModel):
    id: int
    email: str
    status: str
    created_at: datetime
    approved_at: datetime | None
    email_sent_at: datetime | None

    model_config = {"from_attributes": True}
