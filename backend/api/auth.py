from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_bot_secret
from backend.config import RATE_LIMIT_AUTH, backend_settings
from backend.db import get_db
from backend.exceptions import ForbiddenError, NotFoundError
from backend.rate_limit import limiter
from backend.redis_client import (
    consume_exchange_code,
    consume_oauth_state,
    get_redis,
    store_oauth_state,
)
from backend.repositories import users as users_repo
from backend.schemas.auth import TelegramLoginIn, TokenOut
from backend.services.auth import authenticate_telegram, create_oauth_session
from backend.services.github_oauth import fetch_github_access_token, fetch_github_user
from backend.services.google_oauth import fetch_google_access_token, fetch_google_user

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"


@router.post("/telegram", response_model=TokenOut)
@limiter.limit(RATE_LIMIT_AUTH)
async def login_telegram(
    request: Request,
    body: TelegramLoginIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    return await authenticate_telegram(db, body)


@router.get("/github/login")
@limiter.limit(RATE_LIMIT_AUTH)
async def github_login(request: Request, redis: Redis = Depends(get_redis)) -> RedirectResponse:
    """Initiate GitHub OAuth — generate CSRF state, redirect to GitHub."""
    state = await store_oauth_state(redis)
    params = urlencode(
        {
            "client_id": backend_settings.GITHUB_CLIENT_ID,
            "scope": "user:email",
            "state": state,
        }
    )
    return RedirectResponse(url=f"{_GITHUB_AUTHORIZE_URL}?{params}")


# Callbacks are intentionally not rate-limited — a valid state+code pair requires a prior
# limited initiation request, so they can't be independently abused.
@router.get("/github/callback")
async def github_callback(
    code: str = Query(),
    state: str = Query(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """GitHub OAuth callback — validate state, exchange code, upsert user, redirect to frontend."""
    if not await consume_oauth_state(redis, state):
        return RedirectResponse(
            url=f"{backend_settings.FRONTEND_URL}/auth/callback?error=invalid_state"
        )
    access_token = await fetch_github_access_token(code)
    github_user_id, email, display_name = await fetch_github_user(access_token)
    try:
        exchange, is_new = await create_oauth_session(
            db,
            redis,
            provider="github",
            provider_user_id=github_user_id,
            email=email,
            display_name=display_name,
        )
    except ForbiddenError:
        return RedirectResponse(
            url=f"{backend_settings.FRONTEND_URL}/auth/callback?error=not_approved"
        )
    url = f"{backend_settings.FRONTEND_URL}/auth/callback?code={exchange}"
    if is_new:
        url += "&new=1"
    return RedirectResponse(url=url)


@router.get("/google/login")
@limiter.limit(RATE_LIMIT_AUTH)
async def google_login(request: Request, redis: Redis = Depends(get_redis)) -> RedirectResponse:
    """Initiate Google OAuth — generate CSRF state, redirect to Google."""
    state = await store_oauth_state(redis)
    params = urlencode(
        {
            "client_id": backend_settings.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "redirect_uri": f"{backend_settings.BACKEND_URL}/api/auth/google/callback",
        }
    )
    return RedirectResponse(url=f"{_GOOGLE_AUTHORIZE_URL}?{params}")


# See comment above github_callback — same reasoning applies.
@router.get("/google/callback")
async def google_callback(
    code: str = Query(),
    state: str = Query(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Google OAuth callback — validate state, exchange code, upsert user, redirect to frontend."""
    if not await consume_oauth_state(redis, state):
        return RedirectResponse(
            url=f"{backend_settings.FRONTEND_URL}/auth/callback?error=invalid_state"
        )
    redirect_uri = f"{backend_settings.BACKEND_URL}/api/auth/google/callback"
    access_token = await fetch_google_access_token(code, redirect_uri)
    google_user_id, email, display_name = await fetch_google_user(access_token)
    try:
        exchange, is_new = await create_oauth_session(
            db,
            redis,
            provider="google",
            provider_user_id=google_user_id,
            email=email,
            display_name=display_name,
        )
    except ForbiddenError:
        return RedirectResponse(
            url=f"{backend_settings.FRONTEND_URL}/auth/callback?error=not_approved"
        )
    url = f"{backend_settings.FRONTEND_URL}/auth/callback?code={exchange}"
    if is_new:
        url += "&new=1"
    return RedirectResponse(url=url)


@router.get("/exchange", response_model=TokenOut)
async def exchange_token(
    code: str = Query(),
    redis: Redis = Depends(get_redis),
) -> TokenOut:
    """Exchange a single-use code for a JWT. Code expires in 60 seconds."""
    token = await consume_exchange_code(redis, code)
    if token is None:
        raise NotFoundError("exchange code", "")
    return TokenOut(access_token=token)


@router.get(
    "/telegram/check",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_bot_secret)],
)
async def check_user(
    telegram_id: int = Query(),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Check if a Telegram user is registered and active. Bot-secret only."""
    user = await users_repo.find_by_telegram_id(db, telegram_id)
    if not user:
        raise NotFoundError("User", str(telegram_id))
    if not user.is_active:
        raise ForbiddenError("Account is deactivated")
