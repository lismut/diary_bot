"""Общие утилиты для обработчиков: активный день, меню, применение записей."""
from __future__ import annotations

import logging
from datetime import date

from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
)

from src.config import settings
from src.db.base import async_session
from src.db import crud
from src.services import parser as P
from src.services import sections
from src.services.reporter import ReportService
from src.utils.helpers import format_date_ru

logger = logging.getLogger(__name__)

ACTIVE_DAY_KEY = "active_day"

# ---------------------------------------------------------------- кнопки меню
BTN_SLEEP = "😴 Сон"
BTN_WEIGHT = "⚖️ Вес"
BTN_TRAIN = "💪 Тренировка"
BTN_CLIMB = "🧗 Лазание"
BTN_HANG = "🤸 Висы"
BTN_FOOD = "🍽 Питание"
BTN_SUPP = "💊 Добавки"
BTN_STEPS = "👟 Шаги"
BTN_SUMMARY = "📋 Сводка дня"
BTN_STATS = "📊 Статистика"
BTN_REPORT = "📤 В отчёт"
BTN_DAY = "📅 День"

MENU_TEXTS = {
    BTN_SLEEP, BTN_WEIGHT, BTN_TRAIN, BTN_CLIMB, BTN_HANG, BTN_FOOD,
    BTN_SUPP, BTN_STEPS, BTN_SUMMARY, BTN_STATS, BTN_REPORT, BTN_DAY,
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SLEEP), KeyboardButton(text=BTN_WEIGHT)],
            [KeyboardButton(text=BTN_TRAIN), KeyboardButton(text=BTN_CLIMB)],
            [KeyboardButton(text=BTN_HANG), KeyboardButton(text=BTN_FOOD)],
            [KeyboardButton(text=BTN_SUPP), KeyboardButton(text=BTN_STEPS)],
            [KeyboardButton(text=BTN_SUMMARY), KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_REPORT), KeyboardButton(text=BTN_DAY)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери раздел или просто напиши строку",
    )


# ---------------------------------------------------------------- доступ
def allowed(message: Message) -> bool:
    if settings.MAIN_CHAT_ID is None:
        return True
    return message.chat.id == settings.MAIN_CHAT_ID


def allowed_cb(callback: CallbackQuery) -> bool:
    if settings.MAIN_CHAT_ID is None:
        return True
    if callback.message and callback.message.chat:
        return callback.message.chat.id == settings.MAIN_CHAT_ID
    return True


# ---------------------------------------------------------------- активный день
async def get_active_date(session) -> date:
    v = await crud.get_setting(session, ACTIVE_DAY_KEY)
    if v:
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    return date.today()


async def set_active_day(session, d: date) -> None:
    await crud.set_setting(session, ACTIVE_DAY_KEY, d.isoformat())


async def active_day() -> date:
    async with async_session() as session:
        return await get_active_date(session)


# ---------------------------------------------------------------- применение
async def apply_text(session, day_date: date, text: str):
    """Разбирает текст (возможно многострочный) и применяет к дню."""
    day = await crud.get_or_create_day(session, day_date)
    await session.refresh(day, ["log_lines"])
    has_wake = bool(day.wake_time)
    has_sleep = bool(day.sleep_time)

    applied: list[P.ParsedLine] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        items = P.parse_line(line, has_wake=has_wake, has_sleep=has_sleep)
        if not items:
            continue
        applied += await crud.apply_parsed(session, day, items)
        for it in items:
            if it.category == P.WAKE:
                has_wake = True
            elif it.category == P.SLEEP_TIME:
                has_sleep = True
    return day, applied


def confirmation(day_date: date, applied: list[P.ParsedLine]) -> str:
    head = f"📥 <b>{format_date_ru(day_date)}</b>"
    if day_date != date.today():
        head += " <i>(не сегодня)</i>"
    lines = [head, ""]
    for it in applied:
        lines.append(it.display)
    return "\n".join(lines)


async def add_items(bot, day_date: date, items: list[P.ParsedLine]) -> list[P.ParsedLine]:
    """Применяет записи к дню. Публикация в отчётный чат — отдельно,
    по нажатию «Готово» в разделе (см. ReportService.publish_section)."""
    async with async_session() as session:
        day = await crud.get_or_create_day(session, day_date)
        applied = await crud.apply_parsed(session, day, items)
    return applied


async def report_active_day(bot, day_date: date) -> bool:
    async with async_session() as session:
        day = await crud.get_day(session, day_date)
    if not day or not settings.REPORT_CHAT_ID:
        return False
    try:
        await ReportService(bot).post_day(day)
        return True
    except Exception as e:
        logger.error("post_day error: %s", e)
        return False


async def publish_sections_for(bot, day_date: date, applied, always_diary: bool = False) -> None:
    """Публикует/правит сообщения разделов, затронутых добавленными строками."""
    if not settings.REPORT_CHAT_ID or not applied:
        return
    base: list[str] = ["diary"] if always_diary else []
    for it in applied:
        sec = sections.section_for_category(it.category)
        if sec and sec not in base:
            base.append(sec)
    # тренировка делит строки с ЛФК и висами — обновляем и их разделы
    section_names: list[str] = []
    for sec in base:
        for s in sections.related_sections(sec):
            if s not in section_names:
                section_names.append(s)
    if not section_names:
        return
    async with async_session() as session:
        day = await crud.get_day(session, day_date)
    if not day:
        return
    rep = ReportService(bot)
    for sec in section_names:
        try:
            await rep.publish_section(day, sec)
        except Exception as e:  # noqa: BLE001
            logger.error("publish_section %s error: %s", sec, e)


async def publish_section(bot, day_date: date, section: str) -> None:
    """Публикует/правит сообщение одного раздела."""
    if not settings.REPORT_CHAT_ID or not section:
        return
    async with async_session() as session:
        day = await crud.get_day(session, day_date)
    if not day:
        return
    try:
        await ReportService(bot).publish_section(day, section)
    except Exception as e:  # noqa: BLE001
        logger.error("publish_section %s error: %s", section, e)
