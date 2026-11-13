from datetime import date, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)

from src.config import settings
from src.db.base import async_session
from src.db import crud
from src.services.charts import ChartService
from src.services.reporter import ReportService

router = Router()

PERIODS = {
    "week": ("за неделю", 7),
    "month": ("за месяц", 30),
    "year": ("за год", 365),
    "all": ("за всё время", 100000),
}


def periods_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Неделя", callback_data="st:week"),
            InlineKeyboardButton(text="Месяц", callback_data="st:month"),
        ],
        [
            InlineKeyboardButton(text="Год", callback_data="st:year"),
            InlineKeyboardButton(text="Всё", callback_data="st:all"),
        ],
        [InlineKeyboardButton(text="📤 Выложить в отчётный чат", callback_data="pub:month")],
    ])


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer("📈 <b>Статистика</b>\nВыбери период:", reply_markup=periods_keyboard(), parse_mode="HTML")


async def _load(period: str):
    _, days_n = PERIODS[period]
    end = date.today()
    start = end - timedelta(days=days_n)
    async with async_session() as session:
        days = await crud.get_days_range(session, start, end)
    return days


def _summary_text(days, period_name: str) -> str:
    if not days:
        return f"За {period_name} нет данных."
    t = f"📊 <b>Статистика {period_name}</b>\n\n"
    t += f"Дней с записями: {len(days)}\n\n"

    weights = [d.weight for d in days if d.weight]
    if weights:
        t += f"⚖️ Вес: ср {sum(weights)/len(weights):.1f} кг, {min(weights):.1f}–{max(weights):.1f}\n"
    sleeps = [d.sleep_hours for d in days if d.sleep_hours]
    if sleeps:
        t += f"😴 Сон: ср {sum(sleeps)/len(sleeps):.1f} ч\n"
    quals = [d.sleep_quality for d in days if d.sleep_quality]
    if quals:
        t += f"🛏 Качество сна: ср {sum(quals)/len(quals):.1f}/10\n"
    steps = [d.steps for d in days if d.steps]
    if steps:
        t += f"👟 Шаги: ср {int(sum(steps)/len(steps))}\n"
    proteins = [d.protein_total() for d in days if d.meals]
    if proteins:
        norm = settings.PROTEIN_NORM_PER_DAY
        hit = sum(1 for p in proteins if p >= norm)
        t += f"🍽 Белок: ср {sum(proteins)/len(proteins):.0f} г, норма выполнена {hit}/{len(proteins)} дней\n"
    train = sum(1 for d in days if d.exercises or d.climbing_routes or d.hangs)
    t += f"\n💪 Дней с активностью: {train}/{len(days)}\n"
    climbs = sum(sum(r.attempts or 0 for r in d.climbing_routes) for d in days)
    if climbs:
        t += f"🧗 Всего попыток лазания: {climbs}\n"
    return t


@router.callback_query(F.data.startswith("st:"))
async def on_stats(callback: CallbackQuery):
    period = callback.data.split(":")[1]
    period_name, _ = PERIODS[period]
    days = await _load(period)
    await callback.message.answer(_summary_text(days, period_name), parse_mode="HTML")

    charts = [
        (ChartService.weight, "Динамика веса"),
        (ChartService.protein, "Белок"),
        (ChartService.sleep_hours, "Сон"),
        (ChartService.climbing, "Лазание"),
        (ChartService.hangs, "Висы"),
        (ChartService.routines, "Регулярность"),
        (ChartService.steps, "Шаги"),
    ]
    for fn, caption in charts:
        try:
            buf = fn(days)
        except Exception:
            buf = None
        if buf:
            await callback.message.answer_photo(
                BufferedInputFile(buf.getvalue(), filename="chart.png"), caption=caption,
            )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:"))
async def on_publish(callback: CallbackQuery):
    period = callback.data.split(":")[1]
    period_name, _ = PERIODS[period]
    if not settings.REPORT_CHAT_ID:
        await callback.answer("REPORT_CHAT_ID не настроен", show_alert=True)
        return
    days = await _load(period)
    await ReportService(callback.bot).post_analytics(days, period_name)
    await callback.answer("Выложено в отчётный чат ✅")


@router.message(Command("publish"))
async def cmd_publish(message: Message):
    args = message.text.split(maxsplit=1)
    period = "month"
    if len(args) > 1 and args[1].strip() in PERIODS:
        period = args[1].strip()
    if not settings.REPORT_CHAT_ID:
        await message.answer("REPORT_CHAT_ID не настроен.")
        return
    period_name, _ = PERIODS[period]
    days = await _load(period)
    await ReportService(message.bot).post_analytics(days, period_name)
    await message.answer(f"📤 Выложил графики {period_name} в отчётный чат.")
