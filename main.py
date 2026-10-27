import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import menu, entry, routines, publish, info
from db import db

logging.basicConfig(level=logging.INFO)
db.init()

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN missing")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", menu.start))
    app.add_handler(CommandHandler(["id", "ids", "chatid"], info.get_chat_ids))

    app.add_handler(entry.conv)
    app.add_handler(routines.conv)
    app.add_handler(publish.conv)
    app.add_handler(CallbackQueryHandler(menu.cb, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(charts.cb, pattern="^charts:"))

    app.run_polling()

if __name__ == '__main__':
    main()