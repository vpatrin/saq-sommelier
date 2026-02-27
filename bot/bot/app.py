from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot.api_client import BackendClient
from bot.categories import group_facets
from bot.config import (
    CALLBACK_PREFIX,
    CALLBACK_STORE_DONE,
    CALLBACK_STORE_PREFIX,
    CMD_ALERTS,
    CMD_HELP,
    CMD_MYSTORES,
    CMD_NEW,
    CMD_RANDOM,
    CMD_START,
    CMD_UNWATCH,
    CMD_WATCH,
    MENU_ALERTS,
    MENU_HELP,
    MENU_NEW,
    MENU_RANDOM,
    MENU_STORES,
    settings,
)
from bot.handlers.filters import filter_callback
from bot.handlers.mystores import (
    back_handler,
    location_handler,
    mystores_command,
    store_done_callback,
    store_remove_callback,
    store_toggle_callback,
)
from bot.handlers.new import new_command
from bot.handlers.notifications import poll_notifications
from bot.handlers.random import random_command
from bot.handlers.start import help_command, start
from bot.handlers.watch import alerts_command, unwatch_command, watch_command
from bot.middleware import allowlist_gate, rate_limit_gate


async def _post_init(application: Application) -> None:
    api = BackendClient(settings.BACKEND_URL, settings.BACKEND_TIMEOUT)
    await api.open()
    application.bot_data["api"] = api
    logger.info("BackendClient initialized ({})", settings.BACKEND_URL)

    # Fetch product facets and cache grouped categories for filter keyboard
    try:
        facets = await api.get_facets()
        application.bot_data["category_groups"] = group_facets(facets["categories"])
        group_count = len(application.bot_data["category_groups"])
        logger.info("Category groups loaded ({} active groups)", group_count)
    except Exception:
        logger.warning("Failed to fetch facets — category filters will use fallback")
        application.bot_data["category_groups"] = {}


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
    # Middlewares — runs before all command handlers, in group order
    app.add_handler(TypeHandler(Update, allowlist_gate), group=-2)
    app.add_handler(TypeHandler(Update, rate_limit_gate), group=-1)
    # Command handlers (group=0, default)
    app.add_handler(CommandHandler(CMD_START, start))
    app.add_handler(CommandHandler(CMD_HELP, help_command))
    app.add_handler(CommandHandler(CMD_NEW, new_command))
    app.add_handler(CommandHandler(CMD_RANDOM, random_command))
    app.add_handler(CommandHandler(CMD_WATCH, watch_command))
    app.add_handler(CommandHandler(CMD_UNWATCH, unwatch_command))
    app.add_handler(CommandHandler(CMD_ALERTS, alerts_command))
    app.add_handler(CommandHandler(CMD_MYSTORES, mystores_command))
    # Location messages — triggers nearby store lookup
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    # Reply keyboard menu — text messages from persistent bottom buttons
    app.add_handler(MessageHandler(filters.Text([MENU_NEW]), new_command))
    app.add_handler(MessageHandler(filters.Text([MENU_RANDOM]), random_command))
    app.add_handler(MessageHandler(filters.Text([MENU_ALERTS]), alerts_command))
    app.add_handler(MessageHandler(filters.Text([MENU_STORES]), mystores_command))
    app.add_handler(MessageHandler(filters.Text([MENU_HELP]), help_command))
    app.add_handler(MessageHandler(filters.Text(["\u2190 Back"]), back_handler))
    # Inline button callbacks — store selection ("s:") and product filters ("f:")
    app.add_handler(
        CallbackQueryHandler(store_toggle_callback, pattern=rf"^{CALLBACK_STORE_PREFIX}toggle:")
    )
    app.add_handler(
        CallbackQueryHandler(store_remove_callback, pattern=rf"^{CALLBACK_STORE_PREFIX}rm:")
    )
    app.add_handler(CallbackQueryHandler(store_done_callback, pattern=rf"^{CALLBACK_STORE_DONE}$"))
    app.add_handler(CallbackQueryHandler(filter_callback, pattern=rf"^{CALLBACK_PREFIX}"))
    # Poll backend for restock notifications on a timer
    app.job_queue.run_repeating(
        poll_notifications,
        interval=settings.NOTIFICATION_POLL_INTERVAL,
        first=0,
    )
    return app
