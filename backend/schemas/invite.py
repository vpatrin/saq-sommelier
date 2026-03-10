from datetime import datetime

from pydantic import BaseModel


class InviteCodeOut(BaseModel):
    id: int
    code: str
    created_by_id: int
    used_by_id: int | None = None
    used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
