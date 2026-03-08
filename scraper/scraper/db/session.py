from core.db.base import create_session_factory

from ..config import settings

SessionLocal = create_session_factory(settings.database_url, settings.database_echo)
