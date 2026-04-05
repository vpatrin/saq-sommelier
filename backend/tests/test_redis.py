from unittest.mock import AsyncMock

import pytest

from backend.redis_client import consume_exchange_code, store_exchange_code


@pytest.fixture
def mock_redis():
    return AsyncMock()


async def test_store_exchange_code_sets_key_with_ttl(mock_redis):
    mock_redis.getdel.return_value = None
    jwt = "header.payload.sig"

    code = await store_exchange_code(mock_redis, jwt)

    assert len(code) > 20
    mock_redis.set.assert_called_once_with(f"oauth:exchange:{code}", jwt, ex=60)


async def test_consume_exchange_code_returns_jwt(mock_redis):
    mock_redis.getdel.return_value = "header.payload.sig"

    result = await consume_exchange_code(mock_redis, "somecode")

    assert result == "header.payload.sig"
    mock_redis.getdel.assert_called_once_with("oauth:exchange:somecode")


async def test_consume_exchange_code_returns_none_when_expired(mock_redis):
    mock_redis.getdel.return_value = None

    result = await consume_exchange_code(mock_redis, "expiredcode")

    assert result is None


async def test_store_exchange_code_generates_unique_codes(mock_redis):
    codes = {await store_exchange_code(mock_redis, "jwt") for _ in range(10)}
    assert len(codes) == 10
