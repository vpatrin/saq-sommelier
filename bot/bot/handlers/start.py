from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    "🍷 *Alerte Vin* — Wine discovery bot\n\n"
    "*Commands:*\n"
    "/search `<query>` — Search wines by name\n"
    "/new — Recently added wines\n"
    "/random — Random wine suggestion\n"
    "/watch `<sku>` — Get alerts for availability changes\n"
    "/unwatch `<sku>` — Stop watching a wine\n"
    "/alerts — List your watched wines\n"
    "/help — Show this message"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Welcome! I help you discover wines available at the SAQ.\n\n{HELP_TEXT}",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
