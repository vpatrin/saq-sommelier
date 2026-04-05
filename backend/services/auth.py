import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import jwt
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import WAITLIST_APPROVED, backend_settings
from backend.exceptions import ForbiddenError, InvalidCredentialsError
from backend.redis_client import store_exchange_code
from backend.repositories import oauth_accounts as oauth_accounts_repo
from backend.repositories import users as users_repo
from backend.repositories import waitlist as waitlist_repo
from backend.schemas.auth import TelegramLoginIn, TokenOut

# Telegram login data expires after 1 day
_TELEGRAM_AUTH_MAX_AGE_SECONDS = 86400

_JWT_EXPIRY_DAYS = 7


def _verify_telegram_hash(data: TelegramLoginIn, bot_token: str) -> bool:
    """Verify Telegram Login Widget HMAC-SHA-256 signature."""
    # Build check string: sorted key=value pairs, excluding "hash"
    check_pairs = []
    for key in sorted(type(data).model_fields):
        if key == "hash":
            continue
        value = getattr(data, key)
        if value is not None:
            check_pairs.append(f"{key}={value}")
    check_string = "\n".join(check_pairs)

    #! Telegram uses SHA-256 of bot token as HMAC key
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, data.hash)


def _create_jwt(user_id: int, role: str, display_name: str | None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "display_name": display_name,
        "exp": now + timedelta(days=_JWT_EXPIRY_DAYS),
        "iat": now,
    }
    return jwt.encode(payload, backend_settings.JWT_SECRET_KEY, algorithm="HS256")


async def create_oauth_session(
    db: AsyncSession,
    redis: Redis,
    *,
    provider: str,
    provider_user_id: str,
    email: str,
    display_name: str | None,
) -> tuple[str, bool]:
    """Upsert user via OAuth, mint JWT, store in Redis. Returns (exchange_code, is_new)."""
    is_new = False
    account = await oauth_accounts_repo.find_by_provider(db, provider, provider_user_id)

    if account:
        user = await users_repo.find_by_id(db, account.user_id)
        if not user or not user.is_active:
            raise ForbiddenError("Account is deactivated")
        user.last_login_at = datetime.now(UTC)
        await db.flush()
    else:
        user = await users_repo.find_by_email(db, email)
        if user:
            # Existing user signing in with OAuth for the first time — link the account
            if not user.is_active:
                raise ForbiddenError("Account is deactivated")
            user.last_login_at = datetime.now(UTC)
            await db.flush()
        else:
            waitlist_entry = await waitlist_repo.find_by_email(db, email)
            if not waitlist_entry or waitlist_entry.status != WAITLIST_APPROVED:
                raise ForbiddenError("This email has not been approved for access")
            user = await users_repo.create_oauth_user(db, email=email, display_name=display_name)
            is_new = True
        await oauth_accounts_repo.create(
            db, user_id=user.id, provider=provider, provider_user_id=provider_user_id, email=email
        )

    logger.info(
        "OAuth auth: provider={} provider_user_id={} user_id={} email={}",
        provider,
        provider_user_id,
        user.id,
        email,
    )

    token = _create_jwt(user.id, user.role, user.display_name)
    await db.commit()
    code = await store_exchange_code(redis, token)
    return code, is_new


async def authenticate_telegram(db: AsyncSession, data: TelegramLoginIn) -> TokenOut:
    """Verify Telegram OAuth, upsert user, return JWT."""
    if time.time() - data.auth_date > _TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise InvalidCredentialsError("Telegram authentication data has expired")

    if not _verify_telegram_hash(data, backend_settings.TELEGRAM_BOT_TOKEN):
        raise InvalidCredentialsError("Invalid Telegram authentication hash")

    existing = await users_repo.find_by_telegram_id(db, data.id)
    if existing and not existing.is_active:
        raise ForbiddenError("Account is deactivated")

    user = await users_repo.upsert_telegram(db, data.id)

    logger.info("Telegram auth: telegram_id={} user_id={}", data.id, user.id)

    token = _create_jwt(user.id, user.role, user.display_name)
    return TokenOut(access_token=token)
