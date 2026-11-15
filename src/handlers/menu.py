"""Главное меню: сводка дня, статистика, выгрузка в отчёт, выбор дня."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.config import settings
from src.db.base import async_session
from src.db import crud
from src.handlers import common
from src.handlers.common import (
    BTN_SUMMARY, BTN_STATS, BTN_REPORT, BTN_DAY,
    active_day, set_active_day, report_active_day,
)
from src.handlers.states import EntryStates
from src.handlers.view import build_summary
from src.handlers.stats import periods_keyboard
from src.utils.helpers import format_date_ru, parse_date

router = Router()

WELCOME = (
    "🏋️ <b>Спортивный дневник</b>\n\n"
    "Записывай данные кнопками внизу — я всё сохраню за активный день "
    "и разложу в отчётный чат.\n\n"
    "😴 Сон · ⚖️ Вес · 💪 Тренировка · 🧗 Лазание\n"
    "🤸 Висы · 🤸‍♂️ ЛФК · 🍽 Питание · 💊 Добавки · 👟 Шаги\n"
    "📋 Сводка дня · 📊 Статистика · 📤 В отчёт · 📅 День\n\n"
    "Можно и просто писать строками: <code>7:30</code>, <code>Сон 7/10</code>, "
    "<code>78.1</code>, <code>Творог 250г</code>, <code>5 6а</code>, <code>Шаги 15к</code>."
)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=common.main_keyboard(), parse_mode="HTML")


# ---------------------------------------------------------------- сводка
@router.message(F.text == BTN_SUMMARY)
async def menu_summary(message: Message, state: FSMContext):
    await state.clear()
    d = await active_day()
    async with async_session() as session:
        day = await crud.get_day(session, d)
    if not day:
        await message.answer(f"За {format_date_ru(d)} пока нет записей.")
        return
    await message.answer(build_summary(day), parse_mode="HTML")


# ---------------------------------------------------------------- статистика
@router.message(F.text == BTN_STATS)
async def menu_stats(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📊 <b>Статистика</b>\nВыбери период:",
                         reply_markup=periods_keyboard(), parse_mode="HTML")


# ---------------------------------------------------------------- выгрузка
@router.message(F.text == BTN_REPORT)
async def menu_report(message: Message, state: FSMContext):
    await state.clear()
    d = await active_day()
    if not settings.REPORT_CHAT_ID:
        await message.answer("REPORT_CHAT_ID не настроен.")
        return
    ok = await report_active_day(message.bot, d)
    if ok:
        await message.answer(f"📤 Отправил сводку за {format_date_ru(d)} в отчётный чат.")
    else:
        await message.answer(f"За {format_date_ru(d)} нет данных.")


# ---------------------------------------------------------------- выбор дня
@router.message(F.text == BTN_DAY)
async def menu_day(message: Message, state: FSMContext):
    await state.clear()
    d = await active_day()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="day:today"),
         InlineKeyboardButton(text="Вчера", callback_data="day:yesterday")],
        [InlineKeyboardButton(text="Другая дата", callback_data="day:custom")],
    ])
    await message.answer(f"📅 Активный день: <b>{format_date_ru(d)}</b>",
                         reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "day:today")
async def cb_day_today(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        await set_active_day(session, date.today())
    await callback.message.answer("📅 Активный день: <b>сегодня</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "day:yesterday")
async def cb_day_yesterday(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    d = date.today() - timedelta(days=1)
    async with async_session() as session:
        await set_active_day(session, d)
    await callback.message.answer(f"📅 Активный день: <b>{format_date_ru(d)}</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "day:custom")
async def cb_day_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.day_input)
    await callback.message.answer("📅 Введи дату, напр. <code>05.11</code>", parse_mode="HTML")
    await callback.answer()


@router.message(EntryStates.day_input, F.text)
async def on_day_input(message: Message, state: FSMContext):
    d = parse_date(message.text)
    if not d:
        await message.answer("Не понял дату. Напр. <code>05.11</code>", parse_mode="HTML")
        return
    await state.clear()
    async with async_session() as session:
        await set_active_day(session, d)
    await message.answer(f"📅 Активный день: <b>{format_date_ru(d)}</b>",
                         parse_mode="HTML", reply_markup=common.main_keyboard())
