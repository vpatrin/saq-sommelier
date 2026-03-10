import jwt
from core.db.models import User
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import ROLE_ADMIN, backend_settings
from backend.db import get_db
from backend.exceptions import ForbiddenError, InvalidCredentialsError
from backend.repositories import users as users_repo

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_bot_secret(x_bot_secret: str | None = Header(default=None)) -> None:
    """Require X-Bot-Secret header when BOT_SECRET is configured. No-op when unconfigured (dev)."""
    if backend_settings.BOT_SECRET and x_bot_secret != backend_settings.BOT_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot secret")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT from Authorization header and return the user."""
    if credentials is None:
        raise InvalidCredentialsError("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            backend_settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise InvalidCredentialsError("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidCredentialsError("Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidCredentialsError("Invalid token payload")

    user = await users_repo.find_by_id(db, int(user_id))
    if user is None:
        raise InvalidCredentialsError("User not found")

    return user


async def verify_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Accept either a valid JWT or a valid bot secret. Used as the global route guard."""
    #! Bot secret takes priority — bot doesn't send JWT
    if x_bot_secret and backend_settings.BOT_SECRET:
        if x_bot_secret == backend_settings.BOT_SECRET:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot secret")

    # Fall through to JWT validation
    await get_current_user(credentials, db)


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Require that the authenticated user is active."""
    if not user.is_active:
        raise ForbiddenError("Account is deactivated")
    return user


async def verify_admin(user: User = Depends(get_current_active_user)) -> User:
    """Require that the authenticated user has the admin role."""
    if user.role != ROLE_ADMIN:
        raise ForbiddenError("Admin access required")
    return user
