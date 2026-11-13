from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import settings
from src.db.base import async_session
from src.db import crud, models
from src.utils.helpers import format_date_ru

router = Router()


def build_summary(day: models.DayRecord) -> str:
    t = f"📋 <b>Сводка за {format_date_ru(day.date)}</b>\n\n"

    if day.wake_time or day.sleep_time or day.sleep_quality:
        t += "😴 <b>Сон</b>\n"
        if day.sleep_time:
            t += f"  Засыпание: {day.sleep_time}\n"
        if day.wake_time:
            t += f"  Пробуждение: {day.wake_time}\n"
        if day.sleep_hours:
            t += f"  Длительность: {day.sleep_hours} ч\n"
        if day.sleep_quality:
            t += f"  Качество: {day.sleep_quality}/10\n"
        t += "\n"

    body = []
    if day.weight:
        body.append(f"⚖️ Вес: {day.weight} кг")
    if day.resting_hr:
        body.append(f"❤️ Пульс покоя: {day.resting_hr}")
    if day.mood:
        body.append(f"🙂 Настроение: {day.mood}/10")
    if day.energy:
        body.append(f"⚡ Самочувствие: {day.energy}/10")
    if day.water_l:
        body.append(f"💧 Вода: {day.water_l} л")
    if day.steps:
        body.append(f"👟 Шаги: {day.steps}")
    if day.alcohol:
        body.append("🍷 Был алкоголь")
    if body:
        t += "\n".join(body) + "\n\n"

    if day.exercises:
        t += "💪 <b>Тренировка</b>\n"
        for e in day.exercises:
            t += f"  • {e.detail or e.name}\n"
        t += "\n"

    if day.climbing_routes:
        t += "🧗 <b>Скалодром</b>\n"
        for r in day.climbing_routes:
            t += f"  • {r.detail or (r.grade or 'трасса')}\n"
        attempts = sum(r.attempts or 0 for r in day.climbing_routes)
        if attempts:
            t += f"  Всего попыток: {attempts}\n"
        t += "\n"

    if day.hangs:
        t += "🤸 <b>Висы</b>\n"
        for h in day.hangs:
            t += f"  • {h.detail or (h.hold_size or '')}\n"
        t += "\n"

    if day.meals:
        total = day.protein_total()
        norm = settings.PROTEIN_NORM_PER_DAY
        mark = "🟢" if total >= norm else "🟡"
        t += f"🍽 <b>Питание</b> — белок {mark} <b>{total}г</b> / {norm}г\n"
        for m in day.meals:
            t += f"  • {m.food_name} {m.amount_grams:g}г (+{m.protein_g:g}г)\n"
        t += "\n"

    done = [r.routine_name for r in day.routines if r.completed]
    if done:
        t += "✅ <b>Добавки/рутины:</b> " + ", ".join(done) + "\n"

    if day.notes:
        t += f"\n📝 {day.notes}\n"

    return t


@router.message(Command("view"))
async def cmd_view(message: Message):
    args = message.text.split(maxsplit=1)
    from src.utils.helpers import parse_date
    async with async_session() as session:
        if len(args) > 1:
            d = parse_date(args[1]) or date.today()
        else:
            from src.handlers.common import get_active_date
            d = await get_active_date(session)
        day = await crud.get_day(session, d)
    if not day:
        await message.answer(f"За {format_date_ru(d)} нет записей.")
        return
    await message.answer(build_summary(day), parse_mode="HTML")


@router.message(Command("last"))
async def cmd_last(message: Message):
    async with async_session() as session:
        days = await crud.list_days(session, limit=15)
    if not days:
        await message.answer("Записей пока нет.")
        return
    t = "🗓 <b>Последние дни с записями</b>\n\n"
    for d in days:
        parts = []
        if d.weight:
            parts.append(f"{d.weight}кг")
        if d.sleep_hours:
            parts.append(f"{d.sleep_hours}ч")
        if d.steps:
            parts.append(f"{d.steps}ш")
        if d.meals:
            parts.append(f"{d.protein_total()}г белка")
        n = len(d.log_lines)
        t += f"• <b>{format_date_ru(d.date)}</b> — {n} строк"
        if parts:
            t += " (" + ", ".join(parts) + ")"
        t += "\n"
    t += "\nСмотреть день: /view 05.11"
    await message.answer(t, parse_mode="HTML")
