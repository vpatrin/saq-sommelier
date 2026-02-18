import sys

from loguru import logger
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from bot.api_client import BackendClient
from bot.config import SERVICE_NAME, settings
from bot.handlers.filters import filter_callback
from bot.handlers.new import new_command
from bot.handlers.start import help_command, start


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<level>{level:<8}</level> | {time:HH:mm:ss} | <cyan>{name}</cyan> | {message}",
    )
    logger.info("Logging initialized for {}", SERVICE_NAME)


async def _post_init(application: Application) -> None:
    api = BackendClient(settings.BACKEND_URL, settings.BACKEND_TIMEOUT)
    await api.open()
    application.bot_data["api"] = api
    logger.info("BackendClient initialized ({})", settings.BACKEND_URL)


async def _post_shutdown(application: Application) -> None:
    api = application.bot_data.get("api")
    if api:
        await api.close()
        logger.info("BackendClient closed")


def create_app() -> Application:
    """Build the Telegram bot application with all handlers registered."""
    app = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CallbackQueryHandler(filter_callback, pattern=r"^f:"))
    return app
