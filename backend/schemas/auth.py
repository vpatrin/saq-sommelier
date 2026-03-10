from pydantic import BaseModel, Field


class TelegramLoginIn(BaseModel):
    id: int = Field(description="Telegram user ID")
    first_name: str = Field(min_length=1, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    photo_url: str | None = Field(default=None)
    auth_date: int = Field(description="Unix timestamp of authentication")
    hash: str = Field(description="HMAC-SHA-256 verification hash")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
