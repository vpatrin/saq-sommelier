from fastapi import Header, HTTPException, status

from backend.config import backend_settings


def verify_bot_secret(x_bot_secret: str | None = Header(default=None)) -> None:
    """Require X-Bot-Secret header when BOT_SECRET is configured. No-op when unconfigured (dev)."""
    if backend_settings.BOT_SECRET and x_bot_secret != backend_settings.BOT_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot secret")
