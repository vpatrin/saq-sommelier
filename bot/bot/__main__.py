from bot.app import _setup_logging, create_app

_setup_logging()
app = create_app()
app.run_polling()
