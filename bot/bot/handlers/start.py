from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import MAIN_MENU

HELP_TEXT = (
    "🍷 *Alerte Vin*\n"
    "Never miss a good bottle at the SAQ again.\n\n"
    "🛒 *Browse*\n"
    "/new — What just hit the shelves\n"
    "/random — Dealer's choice 🎲\n\n"
    "🔔 *Watch*\n"
    "/watch `<url>` — Stalk a bottle\n"
    "/unwatch `<    url>` — Let it go\n"
    "/alerts — Your watchlist\n\n"
    "🏪 *Stores*\n"
    "/mystores — Pick your SAQ spots\n\n"
    "/help — This thing right here\n\n"
    "— Made with ❤️ by @secp256k2\n\n"
    "Like the wine? — [drop a ⭐](https://github.com/vpatrin/saq-sommelier)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=MAIN_MENU,
    )


help_command = start
