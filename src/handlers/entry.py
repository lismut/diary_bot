"""Кнопочный ввод данных: сон, вес, шаги, тренировка, лазание, висы, питание, добавки."""
from __future__ import annotations

import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from src.db.base import async_session
from src.db import crud
from src.services import parser as P
from src.handlers import common
from src.handlers.common import (
    BTN_SLEEP, BTN_WEIGHT, BTN_TRAIN, BTN_CLIMB, BTN_HANG, BTN_FOOD, BTN_SUPP, BTN_STEPS,
    add_items, confirmation, active_day,
)
from src.handlers.states import EntryStates
from src.utils.helpers import format_date_ru

router = Router()
logger = logging.getLogger(__name__)

GRADES = ["6a", "6b", "6c", "7a", "7b", "7c"]
HOLDS = ["20мм", "18мм", "15мм", "12мм", "10мм", "8мм"]
QUICK_FOODS = ["творог", "курица", "яйцо", "протеин", "кефир", "орехи"]


# ---------------------------------------------------------------- вспомогательное
def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="entry:cancel")],
    ])


def _done_kb(extra: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="entry:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _confirm(bot, items, message: Message, extra_kb: InlineKeyboardMarkup | None = None):
    day_date = await active_day()
    applied = await add_items(bot, day_date, items)
    if not applied:
        await message.answer("Не получилось распознать, попробуй ещё раз.",
                             reply_markup=extra_kb or _cancel_kb())
        return
    await message.answer(confirmation(day_date, applied), parse_mode="HTML", reply_markup=extra_kb)


# ---------------------------------------------------------------- отмена/готово
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. Выбери раздел в меню.", reply_markup=common.main_keyboard())


@router.callback_query(F.data == "entry:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено.")
    await callback.answer()


@router.callback_query(F.data == "entry:done")
async def cb_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("Готово ✅")


# ================================================================ СОН
@router.message(F.text == BTN_SLEEP)
async def menu_sleep(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Пробуждение", callback_data="sleep:wake"),
         InlineKeyboardButton(text="🌙 Засыпание", callback_data="sleep:sleep")],
        [InlineKeyboardButton(text="😴 Качество сна", callback_data="sleep:quality")],
    ])
    await message.answer("😴 <b>Сон</b>\nЧто записать?", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "sleep:wake")
async def cb_sleep_wake(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.sleep_time)
    await state.update_data(mode="wake")
    await callback.message.answer("⏰ Во сколько проснулся? Напиши время, напр. <code>7:30</code>",
                                  parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "sleep:sleep")
async def cb_sleep_sleep(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.sleep_time)
    await state.update_data(mode="sleep")
    await callback.message.answer("🌙 Во сколько заснул? Напр. <code>00:30</code>",
                                  parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "sleep:quality")
async def cb_sleep_quality(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    rows, row = [], []
    for q in range(1, 11):
        row.append(InlineKeyboardButton(text=str(q), callback_data=f"sleep:q:{q}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    await callback.message.answer("😴 Оцени качество сна (1–10):",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("sleep:q:"))
async def cb_sleep_q(callback: CallbackQuery, state: FSMContext):
    q = int(callback.data.split(":")[2])
    await state.clear()
    await _confirm(callback.bot, [P.line_sleep_quality(q)], callback.message)
    await callback.answer("Записал")


@router.message(EntryStates.sleep_time, F.text)
async def on_sleep_time(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode", "wake")
    t = P.parse_time_value(message.text)
    if not t:
        await message.answer("Не понял время. Напиши, напр. <code>7:30</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    items = [P.line_wake(t) if mode == "wake" else P.line_sleep_time(t)]
    await state.clear()
    await _confirm(message.bot, items, message)


# ================================================================ ВЕС
@router.message(F.text == BTN_WEIGHT)
async def menu_weight(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(EntryStates.weight)
    await message.answer("⚖️ Какой утренний вес? Напр. <code>78.1</code>",
                         parse_mode="HTML", reply_markup=_cancel_kb())


@router.message(EntryStates.weight, F.text)
async def on_weight(message: Message, state: FSMContext):
    w = P.parse_weight_value(message.text)
    if w is None:
        await message.answer("Не понял вес. Напиши число, напр. <code>78.1</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    await _confirm(message.bot, [P.line_weight(w)], message)


# ================================================================ ШАГИ
@router.message(F.text == BTN_STEPS)
async def menu_steps(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(EntryStates.steps)
    await message.answer("👟 Сколько шагов? Напр. <code>15000</code> или <code>15к</code>",
                         parse_mode="HTML", reply_markup=_cancel_kb())


@router.message(EntryStates.steps, F.text)
async def on_steps(message: Message, state: FSMContext):
    s = P.parse_steps_value(message.text)
    if not s:
        await message.answer("Не понял. Напиши число шагов, напр. <code>15000</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    await _confirm(message.bot, [P.line_steps(s)], message)


# ================================================================ ТРЕНИРОВКА
def _train_kb() -> InlineKeyboardMarkup:
    return _done_kb([
        [InlineKeyboardButton(text="🏊 Бассейн", callback_data="train:pool")],
        [InlineKeyboardButton(text="✍️ Ввести упражнение", callback_data="train:add")],
    ])


@router.message(F.text == BTN_TRAIN)
async def menu_train(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💪 <b>Тренировка</b>\nЗаписывай упражнения по одному или отметь бассейн.",
        reply_markup=_train_kb(), parse_mode="HTML")


@router.callback_query(F.data == "train:pool")
async def cb_train_pool(callback: CallbackQuery, state: FSMContext):
    item = P.line_exercise_name("Бассейн")
    await _confirm(callback.bot, [item], callback.message, extra_kb=_train_kb())
    await callback.answer("Бассейн записан")


@router.callback_query(F.data == "train:add")
async def cb_train_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.exercise)
    await callback.message.answer(
        "✍️ Напиши упражнение, напр. <code>Гиря вбок 3х3 12кг</code> или <code>Лфк с резинкой</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.exercise, F.text)
async def on_exercise(message: Message, state: FSMContext):
    item = P.line_exercise(message.text)
    await _confirm(message.bot, [item], message, extra_kb=_train_kb())


# ================================================================ ЛАЗАНИЕ
def _climb_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(GRADES), 3):
        rows.append([InlineKeyboardButton(text=g, callback_data=f"climb:g:{g}") for g in GRADES[i:i + 3]])
    rows.append([InlineKeyboardButton(text="✍️ Другое", callback_data="climb:other")])
    return _done_kb(rows)


@router.message(F.text == BTN_CLIMB)
async def menu_climb(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🧗 <b>Лазание</b>\nВыбери категорию:", reply_markup=_climb_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("climb:g:"))
async def cb_climb_grade(callback: CallbackQuery, state: FSMContext):
    grade = callback.data.split(":")[2]
    await state.set_state(EntryStates.climb_count)
    await state.update_data(grade=grade)
    await callback.message.answer(
        f"🧗 <b>{grade}</b>: сколько трасс? Напиши число (напр. <code>5</code>), "
        f"или <code>флеш</code>, или <code>4 попытки</code>.",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "climb:other")
async def cb_climb_other(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.climb_text)
    await callback.message.answer(
        "✍️ Напиши, как было, напр. <code>5 6а, 4 6б, 6с флеш</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.climb_count, F.text)
async def on_climb_count(message: Message, state: FSMContext):
    data = await state.get_data()
    grade = data.get("grade")
    raw = message.text.strip()
    low = raw.lower()
    kind, count, attempts = "attempts", None, None
    if "флеш" in low:
        kind = "flash"
    elif "перепролаз" in low or "залез" in low or "софт" in low:
        kind = "send"
    m = re.search(r"(\d+)", low)
    if m:
        n = int(m.group(1))
        if "попыт" in low:
            attempts = n
        else:
            count = n
    if count is None and attempts is None:
        count = 1
    item = P.line_climb(grade, count, attempts, kind, f"{grade} {raw}")
    await state.clear()
    await _confirm(message.bot, [item], message, extra_kb=_climb_kb())


@router.message(EntryStates.climb_text, F.text)
async def on_climb_text(message: Message, state: FSMContext):
    items = [it for it in P.parse_line(message.text) if it.category == P.CLIMBING]
    if not items:
        await message.answer("Не понял. Напр. <code>5 6а, 4 6б, 6с флеш</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    await _confirm(message.bot, items, message, extra_kb=_climb_kb())


# ================================================================ ВИСЫ
def _hang_kb() -> InlineKeyboardMarkup:
    rows, row = [], []
    for h in HOLDS:
        row.append(InlineKeyboardButton(text=h, callback_data=f"hang:h:{h}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Другое", callback_data="hang:other")])
    return _done_kb(rows)


@router.message(F.text == BTN_HANG)
async def menu_hang(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🤸 <b>Висы</b>\nРазмер зацепки:", reply_markup=_hang_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("hang:h:"))
async def cb_hang_hold(callback: CallbackQuery, state: FSMContext):
    hold = callback.data.split(":")[2]
    await state.set_state(EntryStates.hang_weight)
    await state.update_data(hold=hold)
    await callback.message.answer(
        f"🤸 <b>{hold}</b>: отягощение в кг? Напр. <code>10</code> или <code>0</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "hang:other")
async def cb_hang_other(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.hang_text)
    await callback.message.answer(
        "✍️ Напиши висы, напр. <code>Висы 10мм 10кг 5х10/50</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.hang_weight, F.text)
async def on_hang_weight(message: Message, state: FSMContext):
    data = await state.get_data()
    hold = data.get("hold")
    m = re.search(r"(\d+(?:[.,]\d+)?)", message.text)
    weight = float(m.group(1).replace(",", ".")) if m else None
    item = P.line_hang(hold, weight, f"Висы {hold} {message.text.strip()}")
    await state.clear()
    await _confirm(message.bot, [item], message, extra_kb=_hang_kb())


@router.message(EntryStates.hang_text, F.text)
async def on_hang_text(message: Message, state: FSMContext):
    items = [it for it in P.parse_line(message.text) if it.category == P.HANG]
    if not items:
        await message.answer("Не понял. Напр. <code>Висы 10мм 10кг 5х10/50</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    await _confirm(message.bot, items, message, extra_kb=_hang_kb())


# ================================================================ ПИТАНИЕ
def _food_kb() -> InlineKeyboardMarkup:
    rows, row = [], []
    for name in QUICK_FOODS:
        row.append(InlineKeyboardButton(text=name, callback_data=f"food:q:{name}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Ввести", callback_data="food:add")])
    return _done_kb(rows)


@router.message(F.text == BTN_FOOD)
async def menu_food(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🍽 <b>Питание</b>\nЖми продукт из списка или введи текстом — белок посчитаю сам.",
        reply_markup=_food_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("food:q:"))
async def cb_food_quick(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 2)[2]
    item = P.line_quick_food(name)
    if not item:
        await callback.answer("Не нашёл продукт", show_alert=True)
        return
    await _confirm(callback.bot, [item], callback.message, extra_kb=_food_kb())
    await callback.answer("Записал")


@router.callback_query(F.data == "food:add")
async def cb_food_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.food)
    await callback.message.answer(
        "✍️ Напиши, что съел, напр. <code>Творог 250г, кешью 20г</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.food, F.text)
async def on_food(message: Message, state: FSMContext):
    items = P.parse_food(message.text)
    if not items:
        await message.answer(
            "Не нашёл продуктов. Попробуй иначе, напр. <code>Творог 250г</code>",
            parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await _confirm(message.bot, items, message, extra_kb=_food_kb())


# ================================================================ ДОБАВКИ
def _supp_kb(done: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    def add_names(names: list[str]):
        row: list[InlineKeyboardButton] = []
        for name in names:
            mark = "✅" if name in done else "⬜"
            row.append(InlineKeyboardButton(text=f"{mark} {name}", callback_data=f"supp:t:{name}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

    add_names(P.config_supplements())
    routines = P.config_routines()
    if routines:
        rows.append([InlineKeyboardButton(text="— рутины —", callback_data="supp:noop")])
        add_names(routines)
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="entry:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _completed_names(day_date) -> set[str]:
    async with async_session() as session:
        day = await crud.get_day(session, day_date)
        if not day:
            return set()
        return {r.routine_name for r in day.routines if r.completed}


@router.message(F.text == BTN_SUPP)
async def menu_supp(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    done = await _completed_names(day_date)
    await message.answer(
        f"💊 <b>Добавки и рутины</b> — {format_date_ru(day_date)}\nОтмечай нажатием:",
        reply_markup=_supp_kb(done), parse_mode="HTML")


@router.callback_query(F.data.startswith("supp:t:"))
async def cb_supp_toggle(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 2)[2]
    day_date = await active_day()
    async with async_session() as session:
        day = await crud.get_or_create_day(session, day_date)
        await crud.toggle_routine(session, day, name)
    done = await _completed_names(day_date)
    try:
        await callback.message.edit_reply_markup(reply_markup=_supp_kb(done))
    except Exception:
        pass
    await callback.answer("Отмечено ✅" if name in done else "Снято")


@router.callback_query(F.data == "supp:noop")
async def cb_supp_noop(callback: CallbackQuery):
    await callback.answer()
