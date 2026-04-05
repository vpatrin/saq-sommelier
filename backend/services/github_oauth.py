import asyncio

import httpx
from fastapi import HTTPException, status

from backend.config import backend_settings

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


async def fetch_github_access_token(code: str) -> str:
    """Exchange GitHub OAuth code for an access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GITHUB_TOKEN_URL,
            json={
                "client_id": backend_settings.GITHUB_CLIENT_ID,
                "client_secret": backend_settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub OAuth failed")
    return token


async def fetch_github_user(access_token: str) -> tuple[str, str, str | None]:
    """Fetch GitHub user. Returns (github_user_id, email, display_name)."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient() as client:
        user_resp, emails_resp = await asyncio.gather(
            client.get(_GITHUB_USER_URL, headers=headers),
            client.get(_GITHUB_EMAILS_URL, headers=headers),
        )
    user_data = user_resp.json()
    github_user_id = str(user_data["id"])
    display_name: str | None = user_data.get("name") or user_data.get("login")

    emails = emails_resp.json()
    email = next(
        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
        None,
    )
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account has no verified email address",
        )
    return github_user_id, email, display_name
