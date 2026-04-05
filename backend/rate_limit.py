import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import RATE_LIMIT_GLOBAL, backend_settings


def get_user_or_ip(request: Request) -> str:
    """Key function for LLM endpoints — rate limit per user when authenticated, per IP otherwise.

    Decodes the JWT `sub` claim without a DB hit. Bot-secret callers have no JWT so they
    fall back to IP (the bot has its own per-user throttling in middleware.py).
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(
                auth[7:],
                options={"verify_signature": False},
                algorithms=["HS256"],
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.InvalidTokenError:
            pass
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_GLOBAL],
    storage_uri=backend_settings.REDIS_URL,
    # Fall back to in-memory if Redis is unreachable (tests, Redis hiccup in prod).
    in_memory_fallback_enabled=True,
)
