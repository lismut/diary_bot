import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.db.base import init_db, async_session
from src.db import crud
from src.handlers import start, view, stats, log, menu, entry, fallback, survey
from src.services.reporter import ReportService

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

HISTORY_LAST_DATE_KEY = "history_last_date"
ANALYTICS_BACKFILLED_KEY = "analytics_backfilled"

COMMANDS = [
    BotCommand(command="menu", description="Показать меню"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="day", description="Активный день (сменить: /day 05.11)"),
    BotCommand(command="today", description="Вернуться к сегодняшнему дню"),
    BotCommand(command="log", description="Строки активного дня"),
    BotCommand(command="del", description="Удалить строку по номеру"),
    BotCommand(command="undo", description="Удалить последнюю строку"),
    BotCommand(command="view", description="Сводка за день"),
    BotCommand(command="last", description="Последние дни с записями"),
    BotCommand(command="stats", description="Графики и аналитика"),
    BotCommand(command="report", description="Сводка дня в отчётный чат"),
    BotCommand(command="publish", description="Графики в отчётный чат"),
    BotCommand(command="get_chat_info", description="ID чата и топика"),
]


async def _backfill_history(bot: Bot):
    """Однократная выгрузка истории в отчётный чат.

    По каждому прошлому дню записи отправляются последовательно и по темам.
    Прогресс хранится в настройке history_last_date, поэтому перезапуск бота
    не приводит к повторной отправке уже выгруженных дней. Дни, у которых уже
    есть опубликованные разделы (например, отправленные кнопкой «Готово»),
    пропускаются — старую историю не переделываем.
    """
    if not settings.REPORT_CHAT_ID:
        return
    async with async_session() as session:
        last = await crud.get_setting(session, HISTORY_LAST_DATE_KEY)
        last_date = date.fromisoformat(last) if last else None
        analytics_done = await crud.get_setting(session, ANALYTICS_BACKFILLED_KEY)
        days = await crud.get_all_days(session)
        published_ids = await crud.days_with_section_posts(session)

    today = date.today()
    candidates = [
        d for d in days
        if d.date < today and (last_date is None or d.date > last_date)
    ]
    pending = [d for d in candidates if d.id not in published_ids]

    rep = ReportService(bot)
    if pending:
        logger.info("Выгрузка истории в отчётный чат: %d дней", len(pending))
    for d in candidates:
        # уже опубликован (напр. через «Готово») — только двигаем курсор
        if d.id in published_ids:
            async with async_session() as session:
                await crud.set_setting(session, HISTORY_LAST_DATE_KEY, d.date.isoformat())
            continue
        try:
            sent_ok = await rep.post_day(d)
        except Exception as e:
            logger.error("Ошибка выгрузки дня %s: %s", d.date, e)
            sent_ok = False
        if not sent_ok:
            logger.warning(
                "День %s отправлен не полностью (лимит Telegram?) — "
                "останавливаю выгрузку, продолжу с него после перезапуска", d.date,
            )
            return
        async with async_session() as session:
            await crud.set_setting(session, HISTORY_LAST_DATE_KEY, d.date.isoformat())
        logger.info("День %s выгружен", d.date)

    if not analytics_done:
        all_days = [d for d in days if d.date <= today]
        try:
            analytics_ok = await rep.post_analytics(all_days, "за всё время")
        except Exception as e:
            logger.error("Ошибка аналитики истории: %s", e)
            analytics_ok = False
        if analytics_ok:
            async with async_session() as session:
                await crud.set_setting(session, ANALYTICS_BACKFILLED_KEY, "true")
            logger.info("Историческая аналитика выгружена")
        else:
            logger.warning("Аналитика выгружена не полностью — повторю при следующем запуске")


async def _daily_report(bot: Bot):
    if not settings.REPORT_CHAT_ID:
        return
    yesterday = date.today() - timedelta(days=1)
    async with async_session() as session:
        day = await crud.get_day(session, yesterday)
    if day and day.log_lines:
        try:
            await ReportService(bot).post_day(day)
            logger.info("Отчёт за %s отправлен", yesterday)
        except Exception as e:
            logger.error("Ошибка автоотчёта: %s", e)


async def _weekly_analytics(bot: Bot):
    if not settings.REPORT_CHAT_ID:
        return
    end = date.today()
    start = end - timedelta(days=7)
    async with async_session() as session:
        days = await crud.get_days_range(session, start, end)
    try:
        await ReportService(bot).post_analytics(days, "за неделю")
    except Exception as e:
        logger.error("Ошибка недельной аналитики: %s", e)


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    await init_db()
    logger.info("База данных готова")

    # Порядок важен: кнопки меню — до FSM-состояний, свободный текст — последним.
    dp.include_router(start.router)
    dp.include_router(view.router)
    dp.include_router(stats.router)
    dp.include_router(log.router)
    dp.include_router(menu.router)
    dp.include_router(entry.router)
    dp.include_router(fallback.router)

    await bot.set_my_commands(COMMANDS)

    scheduler = AsyncIOScheduler(timezone=settings.TZ)
    if settings.AUTO_REPORT and settings.REPORT_CHAT_ID:
        scheduler.add_job(
            _daily_report, CronTrigger(hour=settings.REPORT_HOUR, minute=settings.REPORT_MINUTE),
            args=[bot], id="daily_report",
        )
        scheduler.add_job(
            _weekly_analytics, CronTrigger(day_of_week="sun", hour=20, minute=0),
            args=[bot], id="weekly_analytics",
        )
    if settings.SURVEYS_ENABLED and settings.MAIN_CHAT_ID:
        # будни: утренний опрос; выходные: позже
        scheduler.add_job(
            survey.send_morning,
            CronTrigger(day_of_week="mon-fri",
                        hour=settings.MORNING_WEEKDAY_HOUR,
                        minute=settings.MORNING_WEEKDAY_MINUTE),
            args=[bot], id="morning_weekday",
        )
        scheduler.add_job(
            survey.send_morning,
            CronTrigger(day_of_week="sat,sun",
                        hour=settings.MORNING_WEEKEND_HOUR,
                        minute=settings.MORNING_WEEKEND_MINUTE),
            args=[bot], id="morning_weekend",
        )
        scheduler.add_job(
            survey.send_evening,
            CronTrigger(hour=settings.EVENING_HOUR, minute=settings.EVENING_MINUTE),
            args=[bot], id="evening_survey",
        )
    if scheduler.get_jobs():
        scheduler.start()
        logger.info("Планировщик запущен (%d задач)", len(scheduler.get_jobs()))

    # Однократная выгрузка истории (идемпотентна благодаря history_last_date)
    asyncio.create_task(_backfill_history(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
