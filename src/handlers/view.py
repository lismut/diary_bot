from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F
from datetime import date, timedelta
from src.db.base import async_session
from src.db import crud
from src.utils.helpers import format_date_russian, get_date_from_text

router = Router()


@router.message(Command("view"))
async def cmd_view(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="view_today")],
        [InlineKeyboardButton(text="Вчера", callback_data="view_yesterday")],
        [InlineKeyboardButton(text="Указать дату", callback_data="view_custom")],
    ])
    await message.answer("Данные за какой день посмотреть?", reply_markup=kb)


@router.callback_query(F.data.startswith("view_"))
async def view_callback(callback: CallbackQuery):
    today = date.today()
    if callback.data == "view_today":
        chosen_date = today
    elif callback.data == "view_yesterday":
        chosen_date = today - timedelta(days=1)
    elif callback.data == "view_custom":
        await callback.message.answer("Введи дату в формате ДД.ММ.ГГГГ или ДД.ММ")
        return
    else:
        chosen_date = today
    
    async with async_session() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await session.execute(select(crud.models.DayRecord).options(
            selectinload(crud.models.DayRecord.exercises),
            selectinload(crud.models.DayRecord.climbing_routes),
            selectinload(crud.models.DayRecord.hangs),
            selectinload(crud.models.DayRecord.meals),
            selectinload(crud.models.DayRecord.routines)
        ).where(crud.models.DayRecord.date == chosen_date))
        day_record = result.scalar_one_or_none()
    
    if not day_record:
        await callback.message.answer(f"За {format_date_russian(chosen_date)} нет записей")
        await callback.answer()
        return
    
    text = f"📋 <b>Дневник за {format_date_russian(chosen_date)}</b>\n\n"
    
    if day_record.wake_up_time or day_record.sleep_time or day_record.sleep_quality:
        text += f"😴 <b>Сон</b>\n"
        if day_record.wake_up_time:
            text += f"  Пробуждение: {day_record.wake_up_time}\n"
        if day_record.sleep_time:
            text += f"  Засыпание: {day_record.sleep_time}\n"
        if day_record.sleep_hours:
            text += f"  Длительность: {day_record.sleep_hours} ч.\n"
        if day_record.sleep_quality:
            text += f"  Качество: {day_record.sleep_quality}/10\n"
        text += "\n"
    
    if day_record.weight:
        text += f"⚖️ <b>Вес:</b> {day_record.weight} кг\n\n"
    
    if day_record.steps:
        text += f"👟 <b>Шаги:</b> {day_record.steps}\n\n"
    
    if day_record.exercises:
        text += f"💪 <b>Тренировка</b>\n"
        for ex in day_record.exercises:
            line = f"  • {ex.name}"
            if ex.sets and ex.reps:
                line += f" {ex.sets}х{ex.reps}"
            if ex.weight:
                line += f" {ex.weight} кг"
            text += line + "\n"
        text += "\n"
    
    if day_record.climbing_routes:
        text += f"🧗 <b>Скалодром</b>\n"
        for route in day_record.climbing_routes:
            line = f"  • {route.route_name or 'Трасса'}"
            if route.grade:
                line += f" [{route.grade}]"
            if route.attempts:
                line += f" попыток: {route.attempts}"
            text += line + "\n"
        text += "\n"
    
    if day_record.hangs:
        text += f"🤸 <b>Висы</b>\n"
        for hang in day_record.hangs:
            line = f"  • Зацеп {hang.hold_size}"
            if hang.weight:
                line += f", {hang.weight} кг"
            if hang.duration_seconds:
                line += f", {hang.duration_seconds} сек"
            if hang.sets:
                line += f", {hang.sets} п."
            text += line + "\n"
        text += "\n"
    
    if day_record.meals:
        total_protein = sum(m.protein_g for m in day_record.meals)
        text += f"🍽 <b>Питание</b> (всего белка: {total_protein:.1f}г)\n"
        for meal in day_record.meals:
            text += f"  • {meal.food_name}: {meal.amount_grams}г (+{meal.protein_g:.1f}г)\n"
        text += "\n"
    
    if day_record.routines:
        text += f"✅ <b>Рутины/добавки</b>\n"
        for r in day_record.routines:
            status = "✓" if r.completed else "✗"
            text += f"  {status} {r.routine_name}\n"
        text += "\n"
    
    await callback.message.answer(text, parse_mode='HTML')
    await callback.answer()
