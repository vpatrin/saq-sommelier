import anthropic

from backend.config import backend_settings

_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return a shared AsyncAnthropic client, lazily initialized."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=backend_settings.ANTHROPIC_API_KEY)
    return _client
