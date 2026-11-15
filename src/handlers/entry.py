"""Кнопочный ввод данных: сон, вес, шаги, тренировка, лазание, висы, питание, добавки, ЛФК.

Важно: пока пользователь находится в разделе, в отчётный чат ничего не уходит.
Публикация происходит по кнопке «Готово» — тогда весь раздел уходит одним
сообщением (при повторном «Готово» то же сообщение правится).
"""
from __future__ import annotations

import html
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
from src.services import sections
from src.services.reporter import ReportService
from src.handlers import common
from src.handlers.common import (
    BTN_SLEEP, BTN_WEIGHT, BTN_TRAIN, BTN_CLIMB, BTN_HANG, BTN_FOOD, BTN_SUPP, BTN_STEPS,
    BTN_LFK, add_items, confirmation, active_day,
)
from src.handlers.states import EntryStates

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


def _quality_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for q in range(1, 11):
        row.append(InlineKeyboardButton(text=str(q), callback_data=f"sleep:q:{q}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _load_day(day_date):
    async with async_session() as session:
        return await crud.get_day(session, day_date)


# --- ряды кнопок разделов ---
def _train_rows() -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton(text="🏊 Бассейн", callback_data="train:pool")],
        [InlineKeyboardButton(text="✍️ Ввести упражнение", callback_data="train:add")],
    ]


def _climb_rows() -> list[list[InlineKeyboardButton]]:
    rows = []
    for i in range(0, len(GRADES), 3):
        rows.append([InlineKeyboardButton(text=g, callback_data=f"climb:g:{g}") for g in GRADES[i:i + 3]])
    rows.append([InlineKeyboardButton(text="✍️ Другое", callback_data="climb:other")])
    return rows


def _hang_rows() -> list[list[InlineKeyboardButton]]:
    rows, row = [], []
    for h in HOLDS:
        row.append(InlineKeyboardButton(text=h, callback_data=f"hang:h:{h}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Другое", callback_data="hang:other")])
    return rows


def _food_rows() -> list[list[InlineKeyboardButton]]:
    rows, row = [], []
    for name in QUICK_FOODS:
        row.append(InlineKeyboardButton(text=name, callback_data=f"food:q:{name}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Ввести", callback_data="food:add")])
    return rows


def _lfk_rows() -> list[list[InlineKeyboardButton]]:
    return [[InlineKeyboardButton(text="✍️ Ввести упражнение", callback_data="lfk:add")]]


_SECTION_INTRO = {
    "training": "💪 <b>Тренировка</b>\nЗаписывай упражнения по одному или отметь бассейн.",
    "climbing": "🧗 <b>Лазание</b>\nВыбери категорию или введи текстом.",
    "hangs": "🤸 <b>Висы</b>\nВыбери зацепку или введи текстом.",
    "nutrition": "🍽 <b>Питание</b>\nЖми продукт из списка или введи текстом — белок посчитаю сам.",
    "lfk": "🤸‍♂️ <b>ЛФК</b>\nЗаписывай упражнения по одному.",
    "routines": "💊 <b>Добавки и рутины</b>\nОтмечай нажатием.",
}


async def _section_ui(section: str, day_date) -> tuple[str, list[list[InlineKeyboardButton]]]:
    intro = _SECTION_INTRO.get(section, "")
    if section == "training":
        return intro, _train_rows()
    if section == "climbing":
        return intro, _climb_rows()
    if section == "hangs":
        return intro, _hang_rows()
    if section == "nutrition":
        return intro, _food_rows()
    if section == "lfk":
        return intro, _lfk_rows()
    if section == "routines":
        done = await _completed_names(day_date)
        return intro, _supp_rows(done)
    return intro, []


async def _section_view(section: str, day_date, message: Message, edit: bool = False):
    """Показывает текущее состояние раздела с кнопками и «Готово»."""
    intro, action_rows = await _section_ui(section, day_date)
    day = await _load_day(day_date)
    lines = sections.section_log_lines(day, section) if day else []

    text = intro
    if section == "routines":
        done = [r.routine_name for r in (day.routines if day else []) if r.completed]
        text += "\n\n" + ("✅ " + ", ".join(done) if done else "<i>Пока пусто</i>")
    elif lines:
        text += "\n\n<b>Записано:</b>\n" + "\n".join(
            f"{i}. {html.escape(ln.raw_text)}" for i, ln in enumerate(lines, 1))
    else:
        text += "\n\n<i>Пока пусто</i>"

    rows = list(action_rows)
    if section != "routines" and lines:
        del_row: list[InlineKeyboardButton] = []
        for i, ln in enumerate(lines, 1):
            del_row.append(InlineKeyboardButton(
                text=f"🗑 {i}", callback_data=f"entry:del:{section}:{ln.id}"))
            if len(del_row) == 5:
                rows.append(del_row)
                del_row = []
        if del_row:
            rows.append(del_row)
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"entry:done:{section}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if edit:
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def _add_to_section(bot, day_date, items, section: str, message: Message):
    """Добавляет строки в раздел (без публикации) и перерисовывает раздел."""
    applied = await add_items(bot, day_date, items)
    if not applied:
        await message.answer("Не понял, попробуй ещё раз.", reply_markup=_cancel_kb())
        return
    await _section_view(section, day_date, message)


async def _apply_and_publish(bot, day_date, items, section: str, message: Message,
                             extra_kb: InlineKeyboardMarkup | None = None):
    """Для простых разделов (сон/вес/шаги): применяет и сразу публикует раздел."""
    applied = await add_items(bot, day_date, items)
    if not applied:
        await message.answer("Не получилось распознать, попробуй ещё раз.",
                             reply_markup=extra_kb or _cancel_kb())
        return
    day = await _load_day(day_date)
    if day:
        try:
            await ReportService(bot).publish_section(day, section)
        except Exception as e:  # noqa: BLE001
            logger.error("publish_section %s error: %s", section, e)
    await message.answer(confirmation(day_date, applied), parse_mode="HTML", reply_markup=extra_kb)


# ---------------------------------------------------------------- отмена/готово/удаление
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. Выбери раздел в меню.", reply_markup=common.main_keyboard())


@router.callback_query(F.data == "entry:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("entry:done:"))
async def cb_done(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":", 2)[2]
    await state.clear()
    day_date = await active_day()
    day = await _load_day(day_date)
    if day:
        try:
            await ReportService(callback.bot).publish_section(day, section)
        except Exception as e:  # noqa: BLE001
            logger.error("publish_section %s error: %s", section, e)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("Готово ✅")


@router.callback_query(F.data.startswith("entry:del:"))
async def cb_del(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 4 or not parts[3].isdigit():
        await callback.answer("Не понял", show_alert=True)
        return
    section, line_id = parts[2], int(parts[3])
    day_date = await active_day()
    async with async_session() as session:
        day = await crud.get_or_create_day(session, day_date)
        await crud.delete_log_line_by_id(session, day, line_id)
    await _section_view(section, day_date, callback.message, edit=True)
    await callback.answer("Удалил")


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
    await callback.message.answer("😴 Оцени качество сна (1–10):",
                                  reply_markup=_quality_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("sleep:q:"))
async def cb_sleep_q(callback: CallbackQuery, state: FSMContext):
    q = int(callback.data.split(":")[2])
    await state.clear()
    day_date = await active_day()
    await _apply_and_publish(callback.bot, day_date, [P.line_sleep_quality(q)], "sleep", callback.message)
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
    day_date = await active_day()
    await _apply_and_publish(message.bot, day_date, items, "sleep", message)
    # качество сна спрашиваем только после времени пробуждения
    if mode == "wake":
        await state.set_state(EntryStates.sleep_quality)
        await message.answer("😴 Оцени качество сна (1–10):", reply_markup=_quality_keyboard())


@router.message(EntryStates.sleep_quality, F.text)
async def on_sleep_quality(message: Message, state: FSMContext):
    q = P.parse_quality_value(message.text)
    if not q:
        await message.answer("Не понял оценку. Напиши число от 1 до 10.",
                             reply_markup=_quality_keyboard())
        return
    await state.clear()
    day_date = await active_day()
    await _apply_and_publish(message.bot, day_date, [P.line_sleep_quality(q)], "sleep", message)


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
    day_date = await active_day()
    await _apply_and_publish(message.bot, day_date, [P.line_weight(w)], "weight", message)


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
    day_date = await active_day()
    await _apply_and_publish(message.bot, day_date, [P.line_steps(s)], "steps", message)


# ================================================================ ТРЕНИРОВКА
@router.message(F.text == BTN_TRAIN)
async def menu_train(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("training", day_date, message)


@router.callback_query(F.data == "train:pool")
async def cb_train_pool(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    item = P.line_exercise_name("Бассейн")
    await _add_to_section(callback.bot, day_date, [item], "training", callback.message)
    await callback.answer("Бассейн записан")


@router.callback_query(F.data == "train:add")
async def cb_train_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.exercise)
    await callback.message.answer(
        "✍️ Напиши упражнение, напр. <code>Гиря вбок 3х3 12кг</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.exercise, F.text)
async def on_exercise(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, [P.line_exercise(message.text)], "training", message)


# ================================================================ ЛАЗАНИЕ
@router.message(F.text == BTN_CLIMB)
async def menu_climb(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("climbing", day_date, message)


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
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, [item], "climbing", message)


@router.message(EntryStates.climb_text, F.text)
async def on_climb_text(message: Message, state: FSMContext):
    items = [it for it in P.parse_line(message.text) if it.category == P.CLIMBING]
    if not items:
        await message.answer("Не понял. Напр. <code>5 6а, 4 6б, 6с флеш</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, items, "climbing", message)


# ================================================================ ВИСЫ
@router.message(F.text == BTN_HANG)
async def menu_hang(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("hangs", day_date, message)


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
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, [item], "hangs", message)


@router.message(EntryStates.hang_text, F.text)
async def on_hang_text(message: Message, state: FSMContext):
    items = [it for it in P.parse_line(message.text) if it.category == P.HANG]
    if not items:
        await message.answer("Не понял. Напр. <code>Висы 10мм 10кг 5х10/50</code>",
                             parse_mode="HTML", reply_markup=_cancel_kb())
        return
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, items, "hangs", message)


# ================================================================ ПИТАНИЕ
@router.message(F.text == BTN_FOOD)
async def menu_food(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("nutrition", day_date, message)


@router.callback_query(F.data.startswith("food:q:"))
async def cb_food_quick(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 2)[2]
    item = P.line_quick_food(name)
    if not item:
        await callback.answer("Не нашёл продукт", show_alert=True)
        return
    day_date = await active_day()
    await _add_to_section(callback.bot, day_date, [item], "nutrition", callback.message)
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
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, items, "nutrition", message)


# ================================================================ ЛФК
@router.message(F.text == BTN_LFK)
async def menu_lfk(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("lfk", day_date, message)


@router.callback_query(F.data == "lfk:add")
async def cb_lfk_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.lfk)
    await callback.message.answer(
        "✍️ Напиши упражнение ЛФК, напр. <code>Лфк с резинкой 3х15</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.lfk, F.text)
async def on_lfk(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, [P.line_lfk(message.text)], "lfk", message)


# ================================================================ ДОБАВКИ
def _supp_rows(done: set[str]) -> list[list[InlineKeyboardButton]]:
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
    return rows


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
    await _section_view("routines", day_date, message)


@router.callback_query(F.data.startswith("supp:t:"))
async def cb_supp_toggle(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 2)[2]
    day_date = await active_day()
    async with async_session() as session:
        day = await crud.get_or_create_day(session, day_date)
        await crud.toggle_routine(session, day, name)
    await _section_view("routines", day_date, callback.message, edit=True)
    await callback.answer("Отмечено")


@router.callback_query(F.data == "supp:noop")
async def cb_supp_noop(callback: CallbackQuery):
    await callback.answer()
