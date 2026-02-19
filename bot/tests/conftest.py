import os

# Set before any bot module is imported (BotSettings requires these).
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("NOTIFICATION_POLL_INTERVAL", "60")
