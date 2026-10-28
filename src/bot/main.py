import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from src.config import settings
from src.db.base import init_db
from src.handlers import start, add, stats, view

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(add.router)
    dp.include_router(view.router)
    dp.include_router(stats.router)
    
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
