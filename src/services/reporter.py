import io
import logging
from datetime import date
from typing import Optional

from aiogram import Bot
from aiogram.types import BufferedInputFile

from src.config import settings
from src.db import models
from src.services.charts import ChartService

logger = logging.getLogger(__name__)


def _fmt_date(d: date) -> str:
    months = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    return f"{d.day} {months[d.month - 1]} {d.year}"


class ReportService:
    def __init__(self, bot: Bot):
        self.bot = bot

    @property
    def enabled(self) -> bool:
        return bool(settings.REPORT_CHAT_ID)

    async def _send(self, text: str, topic: Optional[int]):
        if not self.enabled:
            return
        try:
            await self.bot.send_message(
                settings.REPORT_CHAT_ID, text, parse_mode="HTML",
                message_thread_id=topic, disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error("Не удалось отправить в отчётный чат: %s", e)

    async def _send_photo(self, buf: io.BytesIO, caption: str, topic: Optional[int]):
        if not self.enabled:
            return
        try:
            photo = BufferedInputFile(buf.getvalue(), filename="chart.png")
            await self.bot.send_photo(
                settings.REPORT_CHAT_ID, photo, caption=caption,
                message_thread_id=topic,
            )
        except Exception as e:
            logger.error("Не удалось отправить график: %s", e)

    # ---------------------------------------------------------- live updates
    async def post_updates(self, day: models.DayRecord, applied: list):
        """Пишет в отчётный чат только что добавленные строки, раскладывая по топикам."""
        if not self.enabled or not applied:
            return
        title = f"📆 {_fmt_date(day.date)}"

        # 1. сырая история дня -> топик дневника
        raw = "\n".join(f"• {it.raw}" for it in applied)
        await self._send(f"{title}\n{raw}", settings.TOPIC_DIARY_ID)

        # 2. структурированно по топикам
        groups: dict = {}
        for it in applied:
            topic = settings.topic_for(it.category)
            groups.setdefault(topic, []).append(it)
        for topic, items in groups.items():
            if topic == settings.TOPIC_DIARY_ID:
                continue
            text = title + "\n" + "\n".join(it.display for it in items)
            await self._send(text, topic)

    # ---------------------------------------------------------- day
    async def post_day(self, day: models.DayRecord):
        if not self.enabled:
            return
        title = f"📆 <b>{_fmt_date(day.date)}</b>"

        # 1. сырой дневник
        if day.log_lines:
            lines = "\n".join(f"• {ln.raw_text}" for ln in sorted(day.log_lines, key=lambda x: x.id))
            await self._send(f"{title}\n\n<b>Записи дня</b>\n{lines}", settings.TOPIC_DIARY_ID)

        # 2. сон
        if day.wake_time or day.sleep_time or day.sleep_quality:
            t = f"{title}\n\n😴 <b>Сон</b>\n"
            if day.sleep_time:
                t += f"Засыпание: {day.sleep_time}\n"
            if day.wake_time:
                t += f"Пробуждение: {day.wake_time}\n"
            if day.sleep_hours:
                t += f"Длительность: {day.sleep_hours} ч\n"
            if day.sleep_quality:
                t += f"Качество: {day.sleep_quality}/10"
            await self._send(t, settings.TOPIC_SLEEP_ID)

        # 3. вес и тело
        if day.weight or day.resting_hr or day.mood or day.energy:
            t = f"{title}\n\n"
            if day.weight:
                t += f"⚖️ Вес: <b>{day.weight} кг</b>\n"
            if day.resting_hr:
                t += f"❤️ Пульс покоя: {day.resting_hr}\n"
            if day.mood:
                t += f"🙂 Настроение: {day.mood}/10\n"
            if day.energy:
                t += f"⚡ Самочувствие: {day.energy}/10\n"
            await self._send(t, settings.TOPIC_WEIGHT_ID)

        # 4. шаги
        if day.steps:
            await self._send(f"{title}\n\n👟 Шаги: <b>{day.steps}</b>", settings.TOPIC_STEPS_ID)

        # 5. питание
        if day.meals:
            total = day.protein_total()
            norm = settings.PROTEIN_NORM_PER_DAY
            mark = "🟢" if total >= norm else "🟡"
            t = f"{title}\n\n🍽 <b>Питание</b>\n"
            for m in day.meals:
                t += f"• {m.food_name} {m.amount_grams:g}г (+{m.protein_g:g}г)\n"
            t += f"\n{mark} Белок: <b>{total}г</b> из {norm}г"
            await self._send(t, settings.TOPIC_NUTRITION_ID)

        # 6. тренировка
        if day.exercises:
            t = f"{title}\n\n💪 <b>Тренировка</b>\n"
            for e in day.exercises:
                t += f"• {e.detail or e.name}\n"
            await self._send(t, settings.TOPIC_TRAINING_ID)

        # 7. скалодром
        if day.climbing_routes:
            t = f"{title}\n\n🧗 <b>Скалодром</b>\n"
            for r in day.climbing_routes:
                t += f"• {r.detail or (r.grade or 'трасса')}\n"
            attempts = sum(r.attempts or 0 for r in day.climbing_routes)
            if attempts:
                t += f"\nВсего попыток: {attempts}"
            await self._send(t, settings.TOPIC_CLIMBING_ID)

        # 8. висы
        if day.hangs:
            t = f"{title}\n\n🤸 <b>Висы</b>\n"
            for h in day.hangs:
                t += f"• {h.detail or (h.hold_size or '')}\n"
            await self._send(t, settings.TOPIC_HANGS_ID)

        # 9. рутины
        done = [r.routine_name for r in day.routines if r.completed]
        if done:
            await self._send(f"{title}\n\n✅ <b>Добавки/рутины:</b>\n" + "\n".join(f"• {n}" for n in done),
                             settings.TOPIC_ROUTINES_ID)

    # ---------------------------------------------------------- analytics
    async def post_analytics(self, days: list[models.DayRecord], period_name: str):
        if not self.enabled:
            return
        caption_prefix = f"📊 {period_name}"

        charts = [
            ("weight", ChartService.weight, settings.TOPIC_WEIGHT_ID, "⚖️ Вес"),
            ("sleep_hours", ChartService.sleep_hours, settings.TOPIC_SLEEP_ID, "😴 Сон, часы"),
            ("sleep_quality", ChartService.sleep_quality, settings.TOPIC_SLEEP_ID, "😴 Качество сна"),
            ("protein", ChartService.protein, settings.TOPIC_NUTRITION_ID, "🍽 Белок"),
            ("steps", ChartService.steps, settings.TOPIC_STEPS_ID, "👟 Шаги"),
            ("climbing", ChartService.climbing, settings.TOPIC_CLIMBING_ID, "🧗 Объём лазания"),
            ("climbing_by_grade", ChartService.climbing_by_grade, settings.TOPIC_CLIMBING_ID, "🧗 Трассы по категориям"),
            ("hangs", ChartService.hangs, settings.TOPIC_HANGS_ID, "🤸 Висы"),
            ("routines", ChartService.routines, settings.TOPIC_ROUTINES_ID, "✅ Регулярность"),
            ("training_activity", ChartService.training_activity, settings.TOPIC_TRAINING_ID, "💪 Активность"),
        ]
        for _, fn, topic, label in charts:
            try:
                buf = fn(days)
            except Exception as e:
                logger.error("Ошибка графика %s: %s", label, e)
                continue
            if buf:
                await self._send_photo(buf, f"{caption_prefix} — {label}", topic)
