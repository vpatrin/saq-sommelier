import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import ROLE_ADMIN, backend_settings
from backend.db import get_db
from backend.exceptions import ForbiddenError, InvalidCredentialsError
from backend.repositories import users as users_repo
from core.db.models import User

_bearer_scheme = HTTPBearer(auto_error=False)


def require_bot_secret(x_bot_secret: str | None = Header(default=None)) -> None:
    """Require X-Bot-Secret header when BOT_SECRET is configured. No-op when unconfigured (dev)."""
    if backend_settings.BOT_SECRET and x_bot_secret != backend_settings.BOT_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot secret")


async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, look up user, reject if inactive."""
    if credentials is None:
        raise InvalidCredentialsError("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            backend_settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidCredentialsError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidCredentialsError("Invalid token") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidCredentialsError("Invalid token payload")

    user = await users_repo.find_by_id(db, int(user_id))
    if user is None:
        raise InvalidCredentialsError("User not found")

    if not user.is_active:
        raise ForbiddenError("Account is deactivated")

    return user


async def verify_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Accept either a valid JWT or a valid bot secret. Used as the global route guard.

    Returns the User for JWT callers, None for bot-secret callers.
    """
    #! Bot secret takes priority — bot doesn't send JWT
    if x_bot_secret and backend_settings.BOT_SECRET:
        if x_bot_secret == backend_settings.BOT_SECRET:
            return None
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot secret")

    return await get_current_active_user(credentials, db)


def get_caller_user_id(user: User | None = Depends(verify_auth)) -> str | None:
    """Derive user_id from JWT for authenticated users. Returns None for bot-secret callers."""
    if user is None:
        return None
    return f"tg:{user.telegram_id}"


def resolve_user_id(caller_user_id: str | None, target_user_id: str | None) -> str:
    """Pick the authoritative user_id based on caller type.

    JWT callers: use the JWT-derived ID (ignore any client-supplied value).
    Bot-secret callers: require the explicit parameter.
    """
    if caller_user_id is not None:
        return caller_user_id
    if target_user_id:
        return target_user_id
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="user_id is required for bot-secret callers",
    )


async def verify_admin(user: User | None = Depends(verify_auth)) -> User:
    """Require that the authenticated user is an active admin.

    Bot-secret callers (user=None) are rejected — admin endpoints are JWT-only.
    """
    if user is None:
        raise ForbiddenError("Admin access requires user authentication")
    if user.role != ROLE_ADMIN:
        raise ForbiddenError("Admin access required")
    return user
