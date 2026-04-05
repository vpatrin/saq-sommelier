import json
from unittest.mock import MagicMock

import jwt
from fastapi import Request, status

from backend.app import rate_limit_handler
from backend.rate_limit import get_user_or_ip

# ── 429 handler ──────────────────


async def test_rate_limit_response_shape():
    """429 response contains 'detail' and correct status code."""
    response = await rate_limit_handler(MagicMock(spec=Request), MagicMock())
    body = json.loads(response.body)
    assert body["detail"] == "Rate limit exceeded"
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ── get_user_or_ip key function ──────────────────


def test_get_user_or_ip_returns_user_key_for_valid_jwt():
    """Returns 'user:{sub}' when a valid JWT is in the Authorization header."""
    token = jwt.encode({"sub": "42"}, "secret", algorithm="HS256")
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.client = MagicMock()
    request.client.host = "1.2.3.4"

    assert get_user_or_ip(request) == "user:42"


def test_get_user_or_ip_falls_back_to_ip_without_jwt():
    """Falls back to IP when no Authorization header is present (bot-secret callers)."""
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "172.18.0.3"

    assert get_user_or_ip(request) == "172.18.0.3"


def test_get_user_or_ip_falls_back_to_ip_for_malformed_jwt():
    """Falls back to IP when the JWT is malformed rather than raising."""
    request = MagicMock()
    request.headers = {"Authorization": "Bearer not.a.jwt"}
    request.client = MagicMock()
    request.client.host = "1.2.3.4"

    assert get_user_or_ip(request) == "1.2.3.4"
