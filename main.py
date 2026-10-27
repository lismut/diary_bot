import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import diary, info
from db import db

logging.basicConfig(level=logging.INFO)
db.init()

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN missing")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", diary.start))
    app.add_handler(CommandHandler(["id", "ids", "chatid"], info.get_chat_ids))
    app.add_handler(diary.conv_handler)

    app.run_polling()

if __name__ == '__main__':
    main()