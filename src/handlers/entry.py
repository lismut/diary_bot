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
    add_items, confirmation, active_day,
)
from src.handlers.states import EntryStates
from src.utils.helpers import format_date_ru

router = Router()
logger = logging.getLogger(__name__)

GRADES = ["5", "6a", "6b", "6c", "7a", "7b", "7c"]
HOLDS = ["20мм", "18мм", "15мм", "12мм", "10мм", "8мм"]
QUICK_FOODS = ["творог", "курица", "яйцо", "протеин", "кефир", "орехи"]
DEFAULT_WAKE = "07:30"
DEFAULT_SLEEP = "00:30"


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
    for i in range(0, len(GRADES), 4):
        rows.append([InlineKeyboardButton(text=g, callback_data=f"climb:g:{g}") for g in GRADES[i:i + 4]])
    rows.append([InlineKeyboardButton(text="✍️ Другое", callback_data="climb:other")])
    return rows


def _climb_kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Флеш", callback_data="climb:kind:flash"),
         InlineKeyboardButton(text="🔄 Не флеш", callback_data="climb:kind:send")],
        [InlineKeyboardButton(text="❌ Не залез", callback_data="climb:kind:fail")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="entry:cancel")],
    ])


def _climb_attempts_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for n in range(1, 7):
        row.append(InlineKeyboardButton(text=str(n), callback_data=f"climb:att:{n}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="entry:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


_SECTION_INTRO = {
    "training": "💪 <b>Тренировка</b>\nЗаписывай упражнения по одному или отметь бассейн.\n"
                "ЛФК и висы тоже пиши сюда — они уйдут и в свои разделы.",
    "climbing": "🧗 <b>Лазание</b>\nВыбери категорию трассы (5, 6a…7c), затем результат: "
                "флеш / не флеш / не залез.",
    "hangs": "🤸 <b>Висы</b>\nВыбери зацепку или введи текстом (дублируется в тренировку).",
    "nutrition": "🍽 <b>Питание</b>\nЖми продукт из списка или введи текстом — белок посчитаю сам.",
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
    if section == "routines":
        done = await _completed_names(day_date)
        return intro, _supp_rows(done)
    return intro, []


async def _section_view(section: str, day_date, message: Message, edit: bool = False):
    """Показывает текущее состояние раздела с кнопками и «Готово»."""
    intro, action_rows = await _section_ui(section, day_date)
    day = await _load_day(day_date)
    lines = sections.section_log_lines(day, section) if day else []
    counts = sections.climb_counts(day) if (day and section == "climbing") else {}

    text = intro
    if section == "routines":
        done = [r.routine_name for r in (day.routines if day else []) if r.completed]
        text += "\n\n" + ("✅ " + ", ".join(done) if done else "<i>Пока пусто</i>")
    elif lines:
        text += "\n\n<b>Записано:</b>\n" + "\n".join(
            f"{i}. {html.escape(ln.raw_text)}"
            + (f" ×{counts[ln.raw_text]}" if counts.get(ln.raw_text, 1) > 1 else "")
            for i, ln in enumerate(lines, 1))
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
    await common.answer_long(message, confirmation(day_date, applied), parse_mode="HTML",
                             reply_markup=extra_kb)


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
        rep = ReportService(callback.bot)
        for sec in sections.related_sections(section):
            try:
                await rep.publish_section(day, sec)
            except Exception as e:  # noqa: BLE001
                logger.error("publish_section %s error: %s", sec, e)
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
async def _ask_sleep_quality(message: Message):
    await message.answer("😴 Оцени качество сна (1–10):", reply_markup=_quality_keyboard())


async def _record_sleep_time(bot, message: Message, mode: str, t: str):
    """Записывает время пробуждения/засыпания и публикует раздел «Сон».

    После времени засыпания активный день переключается на следующий:
    ввели для сегодня — активным станет завтра, для вчера — сегодня.
    """
    day_date = await active_day()
    items = [P.line_wake(t) if mode == "wake" else P.line_sleep_time(t)]
    await _apply_and_publish(bot, day_date, items, "sleep", message)
    if mode == "sleep":
        new_day = await common.shift_active_after_sleep(day_date)
        await message.answer(
            f"📅 Активный день: <b>{format_date_ru(new_day)}</b> (день после засыпания).",
            parse_mode="HTML",
        )


@router.message(F.text == BTN_SLEEP)
async def menu_sleep(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏰ Пробуждение {DEFAULT_WAKE}", callback_data="sleep:def:wake")],
        [InlineKeyboardButton(text=f"🌙 Засыпание {DEFAULT_SLEEP}", callback_data="sleep:def:sleep")],
        [InlineKeyboardButton(text="😴 Качество сна", callback_data="sleep:quality")],
    ])
    await message.answer(
        "😴 <b>Сон</b>\nЖми кнопку со временем по умолчанию или просто напиши своё время текстом.",
        reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "sleep:def:wake")
async def cb_sleep_def_wake(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _record_sleep_time(callback.bot, callback.message, "wake", DEFAULT_WAKE)
    await callback.answer("Записал")
    await state.set_state(EntryStates.sleep_quality)
    await _ask_sleep_quality(callback.message)


@router.callback_query(F.data == "sleep:def:sleep")
async def cb_sleep_def_sleep(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _record_sleep_time(callback.bot, callback.message, "sleep", DEFAULT_SLEEP)
    await callback.answer("Записал")


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
    await _ask_sleep_quality(callback.message)
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
    await state.clear()
    await _record_sleep_time(message.bot, message, mode, t)
    # качество сна спрашиваем только после времени пробуждения
    if mode == "wake":
        await state.set_state(EntryStates.sleep_quality)
        await _ask_sleep_quality(message)


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
        "✍️ Напиши упражнение, напр. <code>Гиря вбок 3х3 12кг</code>.\n"
        "ЛФК (<code>ЛФК с лентой</code>) и висы (<code>Висы 10мм 10кг</code>) "
        "тоже пиши сюда — они уйдут и в свои разделы.",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.message(EntryStates.exercise, F.text)
async def on_exercise(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _add_to_section(message.bot, day_date, [P.line_training(message.text)], "training", message)


# ================================================================ ЛАЗАНИЕ
@router.message(F.text == BTN_CLIMB)
async def menu_climb(message: Message, state: FSMContext):
    await state.clear()
    day_date = await active_day()
    await _section_view("climbing", day_date, message)


@router.callback_query(F.data.startswith("climb:g:"))
async def cb_climb_grade(callback: CallbackQuery, state: FSMContext):
    grade = callback.data.split(":")[2]
    await state.set_state(EntryStates.climb_kind)
    await state.update_data(grade=grade)
    await callback.message.answer(
        f"🧗 <b>{grade}</b>: как прошло?",
        parse_mode="HTML", reply_markup=_climb_kind_kb())
    await callback.answer()


@router.callback_query(F.data == "climb:other")
async def cb_climb_other(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EntryStates.climb_text)
    await callback.message.answer(
        "✍️ Напиши, как было, напр. <code>5х6а</code> (5 трасс 6а на флеш), "
        "<code>6б не залез 4</code>, <code>7а с 7 попытки</code>",
        parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


async def _save_climb(bot, message: Message, state: FSMContext, kind: str, attempts: int | None = None):
    data = await state.get_data()
    grade = data.get("grade")
    await state.clear()
    if not grade:
        await message.answer("Не понял категорию. Начни заново из раздела «Лазание».")
        return
    if kind == "flash":
        attempts = 1
    day_date = await active_day()
    item = P.line_climb_route(grade, int(attempts or 1), kind)
    await _add_to_section(bot, day_date, [item], "climbing", message)


@router.callback_query(F.data.startswith("climb:kind:"))
async def cb_climb_kind(callback: CallbackQuery, state: FSMContext):
    kind = callback.data.split(":")[2]  # flash / send / fail
    data = await state.get_data()
    grade = data.get("grade")
    if not grade:
        await callback.answer("Начни заново из раздела «Лазание»", show_alert=True)
        return
    if kind == "flash":
        await _save_climb(callback.bot, callback.message, state, "flash")
        await callback.answer("Флеш ✅")
        return
    await state.set_state(EntryStates.climb_attempts)
    await state.update_data(kind=kind)
    label = "залез, но не с первой попытки" if kind == "send" else "не залез"
    await callback.message.answer(
        f"🧗 <b>{grade}</b> — {label}.\nСколько попыток? Напиши число или жми кнопку.",
        parse_mode="HTML", reply_markup=_climb_attempts_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("climb:att:"))
async def cb_climb_attempts(callback: CallbackQuery, state: FSMContext):
    n = int(callback.data.split(":")[2])
    data = await state.get_data()
    kind = data.get("kind") or "send"
    await _save_climb(callback.bot, callback.message, state, kind, n)
    await callback.answer()


@router.message(EntryStates.climb_attempts, F.text)
async def on_climb_attempts(message: Message, state: FSMContext):
    m = re.search(r"(\d+)", message.text)
    if not m:
        await message.answer("Не понял число попыток. Напиши, напр. <code>5</code>",
                             parse_mode="HTML", reply_markup=_climb_attempts_kb())
        return
    data = await state.get_data()
    kind = data.get("kind") or "send"
    await _save_climb(message.bot, message, state, kind, int(m.group(1)))


@router.message(EntryStates.climb_text, F.text)
async def on_climb_text(message: Message, state: FSMContext):
    items = [it for it in P.parse_line(message.text) if it.category == P.CLIMBING]
    if not items:
        await message.answer("Не понял. Напр. <code>5х6а</code> или <code>6с флеш</code>",
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


# ================================================================ ОПРОСЫ
# Кнопки из проактивных опросов (см. src/handlers/survey.py).
_SURVEY_SECTIONS = ("training", "nutrition", "routines", "hangs", "climbing")


@router.callback_query(F.data == "survey:steps")
async def cb_survey_steps(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(EntryStates.steps)
    await callback.message.answer("👟 Сколько шагов? Напр. <code>15000</code> или <code>15к</code>",
                                  parse_mode="HTML", reply_markup=_cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("survey:open:"))
async def cb_survey_open(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":", 2)[2]
    if section not in _SURVEY_SECTIONS:
        await callback.answer("Не понял", show_alert=True)
        return
    await state.clear()
    day_date = await active_day()
    await _section_view(section, day_date, callback.message)
    await callback.answer()
