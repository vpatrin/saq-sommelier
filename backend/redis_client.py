import secrets

from redis.asyncio import Redis

from backend.config import backend_settings

#! Exchange codes are single-use JWTs stored in Redis — TTL is intentionally short.
_EXCHANGE_CODE_TTL = 60  # seconds


async def get_redis():
    client: Redis = Redis.from_url(backend_settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def store_exchange_code(redis: Redis, jwt: str) -> str:
    """Store a JWT under a random code. Returns the code."""
    code = secrets.token_urlsafe(32)
    await redis.set(code, jwt, ex=_EXCHANGE_CODE_TTL)
    return code


async def consume_exchange_code(redis: Redis, code: str) -> str | None:
    """Atomically read and delete an exchange code. Returns the JWT or None if expired/invalid."""
    return await redis.getdel(code)
