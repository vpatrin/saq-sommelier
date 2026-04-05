import httpx
from fastapi import HTTPException, status

from backend.config import backend_settings

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


async def fetch_google_access_token(code: str, redirect_uri: str) -> str:
    """Exchange Google OAuth code for an access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": backend_settings.GOOGLE_CLIENT_ID,
                "client_secret": backend_settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OAuth failed",
        ) from exc
    token = resp.json().get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth failed")
    return token


async def fetch_google_user(access_token: str) -> tuple[str, str, str | None]:
    """Fetch Google user info. Returns (google_user_id, email, display_name)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google API error",
        ) from exc

    data = resp.json()
    google_user_id = data.get("sub")
    if not google_user_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google API error")

    email = data.get("email")
    if not email or not data.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no verified email address",
        )

    raw_name: str | None = data.get("name")
    display_name: str | None = raw_name[:100] if raw_name else None

    return google_user_id, email, display_name
