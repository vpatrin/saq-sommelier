import hashlib
import hmac as hmac_lib
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.exceptions import InvalidCredentialsError
from backend.schemas.auth import TelegramLoginIn
from backend.services.auth import _verify_telegram_hash, verify_telegram_data

BOT_TOKEN = "test_bot_token"


def _signed_data(
    *,
    bot_token: str = BOT_TOKEN,
    auth_date: int | None = None,
    hash_override: str | None = None,
) -> TelegramLoginIn:
    """Build a TelegramLoginIn with a correctly computed HMAC for the given bot_token."""
    if auth_date is None:
        auth_date = int(time.time())
    fields = {"auth_date": auth_date, "first_name": "Victor", "id": 12345678}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac_lib.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return TelegramLoginIn(
        id=12345678,
        first_name="Victor",
        auth_date=auth_date,
        hash=hash_override or computed_hash,
    )


class TestVerifyTelegramHash:
    def test_returns_true_for_valid_hmac_signature(self) -> None:
        data = _signed_data()
        assert _verify_telegram_hash(data, BOT_TOKEN) is True

    def test_returns_false_for_wrong_bot_token(self) -> None:
        data = _signed_data(bot_token=BOT_TOKEN)
        assert _verify_telegram_hash(data, "wrong_token") is False


class TestVerifyTelegramData:
    @patch("backend.services.auth.backend_settings")
    def test_raises_when_auth_date_is_expired(self, mock_settings: MagicMock) -> None:
        mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
        data = _signed_data(auth_date=int(time.time()) - 86401)
        with pytest.raises(InvalidCredentialsError, match="expired"):
            verify_telegram_data(data)

    @patch("backend.services.auth.backend_settings")
    def test_raises_when_hash_is_invalid(self, mock_settings: MagicMock) -> None:
        mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
        data = _signed_data(hash_override="a" * 64)
        with pytest.raises(InvalidCredentialsError, match="hash"):
            verify_telegram_data(data)
