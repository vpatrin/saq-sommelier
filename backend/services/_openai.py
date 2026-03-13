from openai import AsyncOpenAI

from backend.config import backend_settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Return a shared AsyncOpenAI client, lazily initialized."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=backend_settings.OPENAI_API_KEY)
    return _client
