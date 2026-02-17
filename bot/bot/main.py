import sys

from loguru import logger
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from bot.config import SERVICE_NAME, settings
from bot.handlers.start import help_command, start


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<level>{level:<8}</level> | {time:HH:mm:ss} | <cyan>{name}</cyan> | {message}",
    )
    logger.info("Logging initialized for {}", SERVICE_NAME)


def create_app() -> Application:
    """Build the Telegram bot application with all handlers registered."""
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    return app


def main() -> None:
    _setup_logging()
    app = create_app()
    app.run_polling()


if __name__ == "__main__":
    main()
