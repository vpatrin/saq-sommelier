from loguru import logger
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.formatters import format_recommendations


async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommend <query> — natural language wine recommendations."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /recommend `<what you're looking for>`")
        return

    api: BackendClient = context.bot_data["api"]

    # Typing indicator while the pipeline runs (intent + embedding + search)
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        data = await api.recommend(query)
    except (BackendUnavailableError, BackendAPIError) as exc:
        logger.warning("Backend unavailable during /recommend: {}", exc)
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    text = format_recommendations(data)
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
