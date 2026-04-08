from unittest.mock import AsyncMock

import pytest

from backend.redis_client import (
    consume_exchange_code,
    consume_oauth_state,
    store_exchange_code,
    store_oauth_state,
)


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


async def test_store_oauth_state_sets_key_with_ttl(mock_redis):
    state = await store_oauth_state(mock_redis)

    assert len(state) > 20
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args[0][0] == f"oauth:state:{state}"
    assert call_args[1]["ex"] == 600


async def test_consume_oauth_state_returns_true_for_valid_state(mock_redis):
    mock_redis.delete.return_value = 1

    result = await consume_oauth_state(mock_redis, "validstate")

    assert result is True
    mock_redis.delete.assert_called_once_with("oauth:state:validstate")


async def test_consume_oauth_state_returns_false_for_unknown_state(mock_redis):
    mock_redis.delete.return_value = 0

    result = await consume_oauth_state(mock_redis, "unknownstate")

    assert result is False
