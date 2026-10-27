import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers import diary

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не найден в .env")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", diary.start))
    app.add_handler(diary.conv_handler)
    app.add_handler(CallbackQueryHandler(diary.button_handler, pattern="^(view_week|chart_mood|chart_sleep)$"))
    
    print("Бот запущен...")
    app.run_polling()
