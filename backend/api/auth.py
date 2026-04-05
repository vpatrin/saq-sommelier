from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_bot_secret
from backend.config import backend_settings
from backend.db import get_db
from backend.exceptions import ForbiddenError, NotFoundError
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

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"


@router.post("/telegram", response_model=TokenOut)
async def login_telegram(
    body: TelegramLoginIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    return await authenticate_telegram(db, body)


@router.get("/github/login")
async def github_login(redis: Redis = Depends(get_redis)) -> RedirectResponse:
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


@router.get("/github/callback")
async def github_callback(
    code: str = Query(),
    state: str = Query(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """GitHub OAuth callback — validate state, exchange code, upsert user, redirect to frontend."""
    if not await consume_oauth_state(redis, state):
        raise ForbiddenError("Invalid or expired OAuth state")
    access_token = await fetch_github_access_token(code)
    github_user_id, email, display_name = await fetch_github_user(access_token)
    exchange = await create_oauth_session(
        db,
        redis,
        provider="github",
        provider_user_id=github_user_id,
        email=email,
        display_name=display_name,
    )
    return RedirectResponse(url=f"{backend_settings.FRONTEND_URL}/auth/callback?code={exchange}")


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
