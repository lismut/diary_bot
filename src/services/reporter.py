from aiogram import Bot
from aiogram.types import FSInputFile
from src.config import settings
from src.db import models
from src.utils.helpers import format_date_russian
from src.services.charts import ChartService
import io


class ReportService:
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def post_day_summary(self, day_record: models.DayRecord):
        if not settings.REPORT_CHAT_ID:
            return
        
        date_str = format_date_russian(day_record.date)
        text = f"📊 <b>Отчет за {date_str}</b>\n\n"
        
        if day_record.wake_up_time or day_record.sleep_time:
            text += f"😴 <b>Сон:</b> засыпание {day_record.sleep_time or '-'}, пробуждение {day_record.wake_up_time or '-'}"
            if day_record.sleep_hours:
                text += f", {day_record.sleep_hours} ч."
            if day_record.sleep_quality:
                text += f", качество {day_record.sleep_quality}/10"
            text += "\n\n"
        
        if day_record.weight:
            text += f"⚖️ <b>Вес:</b> {day_record.weight} кг\n\n"
        
        if day_record.steps:
            text += f"👟 <b>Шаги:</b> {day_record.steps}\n\n"
        
        if day_record.exercises:
            text += f"💪 <b>Тренировка:</b>\n"
            for ex in day_record.exercises:
                line = f"  • {ex.name}"
                if ex.sets and ex.reps:
                    line += f" {ex.sets}x{ex.reps}"
                if ex.weight:
                    line += f" {ex.weight} кг"
                text += line + "\n"
            text += "\n"
        
        if day_record.climbing_routes:
            text += f"🧗 <b>Скалодром:</b>\n"
            for route in day_record.climbing_routes:
                line = f"  • {route.route_name or 'Трасса'}"
                if route.grade:
                    line += f" [{route.grade}]"
                if route.attempts:
                    line += f" попыток: {route.attempts}"
                if route.sends:
                    line += f", успешных: {route.sends}"
                text += line + "\n"
            text += "\n"
        
        if day_record.hangs:
            text += f"🤸 <b>Висы:</b>\n"
            for hang in day_record.hangs:
                line = f"  • Зацеп {hang.hold_size}"
                if hang.weight:
                    line += f", вес {hang.weight} кг"
                if hang.duration_seconds:
                    line += f", {hang.duration_seconds} сек"
                if hang.sets:
                    line += f", {hang.sets} подходов"
                text += line + "\n"
            text += "\n"
        
        if day_record.meals:
            total_protein = sum(m.protein_g for m in day_record.meals)
            text += f"🍽 <b>Питание:</b> всего белка {total_protein:.1f} г\n"
            for meal in day_record.meals:
                text += f"  • {meal.food_name}: {meal.amount_grams}г (+{meal.protein_g}г белка)\n"
            text += "\n"
        
        if day_record.routines:
            completed = [r for r in day_record.routines if r.completed]
            if completed:
                text += f"✅ <b>Рутины:</b> {', '.join([r.routine_name for r in completed])}\n\n"
        
        # Post to appropriate topic if configured
        topic_id = None
        if day_record.sleep_hours is not None or day_record.sleep_quality is not None:
            topic_id = settings.TOPIC_SLEEP_ID
        elif day_record.weight is not None:
            topic_id = settings.TOPIC_WEIGHT_ID
        elif day_record.exercises:
            topic_id = settings.TOPIC_TRAINING_ID
        elif day_record.climbing_routes:
            topic_id = settings.TOPIC_CLIMBING_ID
        elif day_record.hangs:
            topic_id = settings.TOPIC_HANGS_ID
        elif day_record.steps is not None:
            topic_id = settings.TOPIC_STEPS_ID
        elif day_record.meals:
            topic_id = settings.TOPIC_NUTRITION_ID
        elif day_record.routines:
            topic_id = settings.TOPIC_ROUTINES_ID
        
        try:
            if topic_id:
                await self.bot.send_message(settings.REPORT_CHAT_ID, text, parse_mode='HTML', message_thread_id=topic_id)
            else:
                await self.bot.send_message(settings.REPORT_CHAT_ID, text, parse_mode='HTML')
        except Exception as e:
            print(f"Error posting to report chat: {e}")
