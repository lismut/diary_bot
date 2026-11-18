"""Проактивные опросы в личном чате.

Утром бот спрашивает время пробуждения и качество сна, вечером — итоги дня
(шаги, добавки, еда, тренировка) и время засыпания. Кнопки опросов
обрабатываются в entry.py (callback'и sleep:* и survey:*).
"""
from __future__ import annotations

import logging
from datetime import date

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.config import settings
from src.db.base import async_session
from src.handlers import common

logger = logging.getLogger(__name__)


def morning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Проснулся в 07:30", callback_data="sleep:def:wake"),
         InlineKeyboardButton(text="✍️ Другое время", callback_data="sleep:wake")],
    ])


def evening_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👟 Шаги", callback_data="survey:steps")],
        [InlineKeyboardButton(text="💊 Добавки", callback_data="survey:open:routines"),
         InlineKeyboardButton(text="🍽 Еда", callback_data="survey:open:nutrition")],
        [InlineKeyboardButton(text="💪 Тренировка", callback_data="survey:open:training")],
        [InlineKeyboardButton(text="🌙 Заснул в 00:30", callback_data="sleep:def:sleep"),
         InlineKeyboardButton(text="✍️ Другое время", callback_data="sleep:sleep")],
    ])


async def _set_active_today() -> None:
    async with async_session() as session:
        await common.set_active_day(session, date.today())


async def _advance_active_to_today() -> None:
    """Ставит активным сегодняшний день, если текущий активный — раньше."""
    async with async_session() as session:
        cur = await common.get_active_date(session)
        if cur < date.today():
            await common.set_active_day(session, date.today())


async def send_morning(bot: Bot) -> None:
    if not settings.SURVEYS_ENABLED or not settings.MAIN_CHAT_ID:
        return
    await _advance_active_to_today()
    try:
        await bot.send_message(
            settings.MAIN_CHAT_ID,
            "☀️ Доброе утро! Во сколько проснулся? И как спал (1–10)?",
            reply_markup=morning_keyboard(),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Утренний опрос не отправлен: %s", e)


async def send_evening(bot: Bot) -> None:
    if not settings.SURVEYS_ENABLED or not settings.MAIN_CHAT_ID:
        return
    await _set_active_today()
    try:
        await bot.send_message(
            settings.MAIN_CHAT_ID,
            "🌙 Итоги дня: сколько шагов, добавки, еда, тренировка? "
            "И во сколько собираешься засыпать?",
            reply_markup=evening_keyboard(),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Вечерний опрос не отправлен: %s", e)
