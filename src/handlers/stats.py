from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from datetime import date, timedelta
from src.db.base import async_session
from src.db import crud
from src.services.charts import ChartService

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="За неделю", callback_data="stats_week")],
        [InlineKeyboardButton(text="За месяц", callback_data="stats_month")],
        [InlineKeyboardButton(text="За год", callback_data="stats_year")],
        [InlineKeyboardButton(text="Вес", callback_data="chart_weight")],
        [InlineKeyboardButton(text="Сон", callback_data="chart_sleep")],
        [InlineKeyboardButton(text="Белок", callback_data="chart_protein")],
        [InlineKeyboardButton(text="Лазание", callback_data="chart_climb")],
        [InlineKeyboardButton(text="Шаги", callback_data="chart_steps")],
    ])
    await message.answer("📈 Статистика и графики", reply_markup=kb)


@router.callback_query(F.data.startswith("chart_"))
async def send_chart(callback: CallbackQuery):
    chart_type = callback.data.split('_')[1]
    today = date.today()
    start = today - timedelta(days=30)
    
    async with async_session() as session:
        days = await crud.get_days_range(session, start, today)
    
    buf = None
    if chart_type == "weight":
        buf = ChartService.plot_weight(days)
        caption = "Динамика веса за 30 дней"
    elif chart_type == "sleep":
        buf = ChartService.plot_sleep(days)
        caption = "Сон за 30 дней"
    elif chart_type == "protein":
        buf = ChartService.plot_protein(days)
        caption = "Белок по дням за 30 дней (норма 120г)"
    elif chart_type == "climb":
        buf = ChartService.plot_climbing_volume(days)
        caption = "Объём лазания за 30 дней"
    elif chart_type == "steps":
        buf = ChartService.plot_steps(days)
        caption = "Шаги за 30 дней"
    
    if buf:
        photo = BufferedInputFile(buf.getvalue(), filename=f"{chart_type}.png")
        await callback.message.answer_photo(photo, caption=caption)
    else:
        await callback.message.answer("Нет данных для графика")
    
    await callback.answer()


@router.callback_query(F.data.startswith("stats_"))
async def stats_period(callback: CallbackQuery):
    period = callback.data.split('_')[1]
    today = date.today()
    
    if period == "week":
        start = today - timedelta(days=7)
        period_name = "неделю"
    elif period == "month":
        start = today - timedelta(days=30)
        period_name = "месяц"
    elif period == "year":
        start = today - timedelta(days=365)
        period_name = "год"
    else:
        start = today - timedelta(days=7)
        period_name = "неделю"
    
    async with async_session() as session:
        days = await crud.get_days_range(session, start, today)
    
    if not days:
        await callback.message.answer(f"За {period_name} данных нет")
        await callback.answer()
        return
    
    text = f"📊 <b>Статистика за {period_name}</b>\n\n"
    text += f"Дней с записями: {len(days)}\n\n"
    
    # Weight
    weights = [d.weight for d in days if d.weight]
    if weights:
        text += f"⚖️ <b>Вес:</b> ср. {sum(weights)/len(weights):.1f} кг, мин {min(weights):.1f}, макс {max(weights):.1f}\n"
    
    # Sleep
    sleeps = [d.sleep_hours for d in days if d.sleep_hours]
    if sleeps:
        text += f"😴 <b>Сон:</b> ср. {sum(sleeps)/len(sleeps):.1f} ч.\n"
    
    # Steps
    steps_list = [d.steps for d in days if d.steps]
    if steps_list:
        text += f"👟 <b>Шаги:</b> ср. {int(sum(steps_list)/len(steps_list))}\n"
    
    # Protein
    total_proteins = []
    for d in days:
        if d.meals:
            total_proteins.append(sum(m.protein_g for m in d.meals))
    if total_proteins:
        avg_prot = sum(total_proteins)/len(total_proteins)
        text += f"🍽 <b>Белок:</b> ср. {avg_prot:.1f} г/день\n"
    
    # Training days
    train_days = sum(1 for d in days if d.exercises or d.climbing_routes or d.hangs)
    text += f"\n💪 Дней с активностью: {train_days}/{len(days)}\n"
    
    await callback.message.answer(text, parse_mode='HTML')
    
    # Send charts
    if period in ['week', 'month']:
        chart_buf = ChartService.plot_weight(days)
        if chart_buf:
            photo = BufferedInputFile(chart_buf.getvalue(), filename="weight.png")
            await callback.message.answer_photo(photo)
        
        chart_buf = ChartService.plot_protein(days)
        if chart_buf:
            photo = BufferedInputFile(chart_buf.getvalue(), filename="protein.png")
            await callback.message.answer_photo(photo)
    
    await callback.answer()
