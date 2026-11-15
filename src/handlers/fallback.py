"""Свободный ввод строк (запасной вариант, когда ничего не выбрано кнопками)."""
from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message

from src.db.base import async_session
from src.handlers import common
from src.handlers.common import allowed, apply_text, confirmation, get_active_date, publish_sections_for

router = Router()
logger = logging.getLogger(__name__)


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def on_text(message: Message):
    if not allowed(message):
        return
    async with async_session() as session:
        d = await get_active_date(session)
        _, applied = await apply_text(session, d, message.text)

    if not applied:
        await message.answer(
            "Не распознал. Выбери кнопку в меню или напиши /help — там примеры строк.",
            reply_markup=common.main_keyboard(),
        )
        return

    await message.answer(confirmation(d, applied), parse_mode="HTML")

    await publish_sections_for(message.bot, d, applied, always_diary=True)
