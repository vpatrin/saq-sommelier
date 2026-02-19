from core.logging import setup_logging

from bot.app import create_app
from bot.config import SERVICE_NAME, settings

setup_logging(SERVICE_NAME, level=settings.LOG_LEVEL)
app = create_app()
app.run_polling()
