from loguru import logger
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from bot.api_client import BackendClient
from bot.config import (
    CALLBACK_PREFIX,
    CMD_ALERTS,
    CMD_HELP,
    CMD_NEW,
    CMD_RANDOM,
    CMD_START,
    CMD_UNWATCH,
    CMD_WATCH,
    settings,
)
from bot.handlers.filters import filter_callback
from bot.handlers.new import new_command
from bot.handlers.random import random_command
from bot.handlers.start import help_command, start
from bot.handlers.watch import alerts_command, unwatch_command, watch_command


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
    app.add_handler(CommandHandler(CMD_START, start))
    app.add_handler(CommandHandler(CMD_HELP, help_command))
    app.add_handler(CommandHandler(CMD_NEW, new_command))
    app.add_handler(CommandHandler(CMD_RANDOM, random_command))
    app.add_handler(CommandHandler(CMD_WATCH, watch_command))
    app.add_handler(CommandHandler(CMD_UNWATCH, unwatch_command))
    app.add_handler(CommandHandler(CMD_ALERTS, alerts_command))
    # Only button taps whose callback_data starts with "f:" reach filter_callback
    app.add_handler(CallbackQueryHandler(filter_callback, pattern=rf"^{CALLBACK_PREFIX}"))
    return app
