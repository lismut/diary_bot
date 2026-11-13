import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import settings
from src.db.base import async_session
from src.db import crud
from src.handlers import common
from src.handlers.common import get_active_date, set_active_day, report_active_day
from src.utils.helpers import format_date_ru, parse_date

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("day"))
async def cmd_day(message: Message):
    args = message.text.split(maxsplit=1)
    async with async_session() as session:
        if len(args) > 1:
            d = parse_date(args[1])
            if not d:
                await message.answer("Не понял дату. Пример: <code>/day 05.11</code>", parse_mode="HTML")
                return
            await set_active_day(session, d)
            await message.answer(
                f"📅 Активный день: <b>{format_date_ru(d)}</b>\n"
                f"Теперь пиши или жми кнопки — они уйдут за этот день. Вернуться: /today",
                parse_mode="HTML", reply_markup=common.main_keyboard(),
            )
        else:
            d = await get_active_date(session)
            await message.answer(
                f"📅 Активный день: <b>{format_date_ru(d)}</b>\n"
                f"Сменить: <code>/day 05.11</code>",
                parse_mode="HTML",
            )


@router.message(Command("today"))
async def cmd_today(message: Message):
    async with async_session() as session:
        await set_active_day(session, date.today())
    await message.answer("📅 Активный день: <b>сегодня</b>", parse_mode="HTML",
                         reply_markup=common.main_keyboard())


@router.message(Command("log"))
async def cmd_log(message: Message):
    async with async_session() as session:
        d = await get_active_date(session)
        day = await crud.get_day(session, d)
    if not day or not day.log_lines:
        await message.answer(f"За {format_date_ru(d)} пока нет записей.")
        return
    lines = sorted(day.log_lines, key=lambda x: x.id)
    body = "\n".join(f"{i}. {ln.raw_text}" for i, ln in enumerate(lines, 1))
    await message.answer(
        f"📋 <b>{format_date_ru(d)}</b>\n\n{body}\n\n"
        f"Удалить строку: <code>/del N</code>",
        parse_mode="HTML",
    )


@router.message(Command("del"))
async def cmd_del(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Формат: <code>/del N</code> (номер строки из /log)", parse_mode="HTML")
        return
    idx = int(args[1])
    async with async_session() as session:
        d = await get_active_date(session)
        day = await crud.get_day(session, d)
        if not day:
            await message.answer("Нет записей за этот день.")
            return
        ok = await crud.delete_log_line(session, day, idx)
    if ok:
        await message.answer(f"🗑 Удалил строку {idx} за {format_date_ru(d)}.")
    else:
        await message.answer("Нет строки с таким номером.")


@router.message(Command("undo"))
async def cmd_undo(message: Message):
    async with async_session() as session:
        d = await get_active_date(session)
        day = await crud.get_day(session, d)
        if not day or not day.log_lines:
            await message.answer("Нечего отменять.")
            return
        n = len(day.log_lines)
        removed = sorted(day.log_lines, key=lambda x: x.id)[-1].raw_text
        await crud.delete_log_line(session, day, n)
    await message.answer(f"↩️ Удалил последнюю строку: <i>{removed}</i>", parse_mode="HTML")


@router.message(Command("report"))
async def cmd_report(message: Message):
    async with async_session() as session:
        d = await get_active_date(session)
    if not settings.REPORT_CHAT_ID:
        await message.answer("REPORT_CHAT_ID не настроен.")
        return
    ok = await report_active_day(message.bot, d)
    if ok:
        await message.answer(f"📤 Отправил сводку за {format_date_ru(d)} в отчётный чат.")
    else:
        await message.answer(f"За {format_date_ru(d)} нет данных.")
