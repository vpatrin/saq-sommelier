from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import MAIN_MENU

HELP_TEXT = (
    "🍷 *Alerte Vin*\n"
    "Your personal wine discovery bot for the SAQ.\n\n"
    "*Browse*\n"
    "/new — Recently added wines\n"
    "/random — Random wine suggestion\n\n"
    "*Watch*\n"
    "/watch `<sku> or <url>` — Get alerts when a wine is back\n"
    "/unwatch `<sku> or <url>` — Stop watching\n"
    "/alerts — Your watched wines\n\n"
    "/help — Show this message\n\n"
    "— Made with ❤️ by @secp256k2 • 🛠 [vpatrin/saq-sommelier](https://github.com/vpatrin/saq-sommelier)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=MAIN_MENU,
    )


help_command = start
