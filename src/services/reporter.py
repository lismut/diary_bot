import asyncio
import io
import logging
import time
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile

from src.config import settings
from src.db import models
from src.db.base import async_session
from src.db import crud
from src.services.charts import ChartService
from src.services import sections

logger = logging.getLogger(__name__)

MAX_SEND_ATTEMPTS = 8


class ReportService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._last_send_at: float = 0.0
        self._throttle_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(settings.REPORT_CHAT_ID)

    async def _throttle(self) -> None:
        """Держит паузу между отправками, чтобы не ловить 429 от Telegram."""
        interval = max(0.0, settings.REPORT_SEND_INTERVAL)
        async with self._throttle_lock:
            wait = self._last_send_at + interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_send_at = time.monotonic()

    async def _call_with_retry(self, label: str, fn, *args, **kwargs):
        """Вызывает Telegram-метод с учётом 429 (retry_after).

        Возвращает результат вызова или None, если доставить не удалось.
        """
        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            await self._throttle()
            try:
                return await fn(*args, **kwargs)
            except TelegramRetryAfter as e:
                wait = (e.retry_after or 1) + 1
                logger.warning(
                    "429 при отправке (%s): пауза %s с, попытка %s/%s",
                    label, wait, attempt, MAX_SEND_ATTEMPTS,
                )
                await asyncio.sleep(wait)
            except TelegramAPIError as e:
                logger.error("Не удалось отправить (%s): %s", label, e)
                return None
            except Exception as e:  # noqa: BLE001
                logger.error("Не удалось отправить (%s): %s", label, e)
                return None
        logger.error("Не удалось отправить (%s): исчерпаны попытки", label)
        return None

    async def _send(self, text: str, topic: Optional[int]) -> bool:
        if not self.enabled:
            return True
        return await self._send_message(text, topic) is not None

    async def _send_message(self, text: str, topic: Optional[int]):
        if not self.enabled:
            return None
        return await self._call_with_retry(
            "текст", self.bot.send_message,
            settings.REPORT_CHAT_ID, text, parse_mode="HTML",
            message_thread_id=topic, disable_web_page_preview=True,
        )

    async def _edit_message(self, message_id: int, text: str) -> bool:
        """Правит ранее отправленное сообщение. True — доставлено/уже такое же."""
        if not self.enabled:
            return True
        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            await self._throttle()
            try:
                await self.bot.edit_message_text(
                    chat_id=settings.REPORT_CHAT_ID, message_id=message_id,
                    text=text, parse_mode="HTML", disable_web_page_preview=True,
                )
                return True
            except TelegramRetryAfter as e:
                wait = (e.retry_after or 1) + 1
                logger.warning("429 при правке: пауза %s с, попытка %s/%s",
                               wait, attempt, MAX_SEND_ATTEMPTS)
                await asyncio.sleep(wait)
            except TelegramBadRequest as e:
                if "not modified" in str(e).lower():
                    return True
                logger.warning("Не удалось изменить сообщение %s: %s", message_id, e)
                return False
            except TelegramAPIError as e:
                logger.warning("Не удалось изменить сообщение %s: %s", message_id, e)
                return False
        return False

    async def _delete_message(self, message_id: int) -> bool:
        if not self.enabled:
            return True
        try:
            await self.bot.delete_message(chat_id=settings.REPORT_CHAT_ID, message_id=message_id)
            return True
        except TelegramAPIError as e:
            logger.warning("Не удалось удалить сообщение %s: %s", message_id, e)
            return False

    async def _send_photo(self, buf: io.BytesIO, caption: str, topic: Optional[int]) -> bool:
        if not self.enabled:
            return True
        photo = BufferedInputFile(buf.getvalue(), filename="chart.png")
        return await self._call_with_retry(
            "график", self.bot.send_photo,
            settings.REPORT_CHAT_ID, photo, caption=caption,
            message_thread_id=topic,
        ) is not None

    # ---------------------------------------------------------- sections
    async def publish_section(self, day: models.DayRecord, section: str) -> bool:
        """Публикует/правит сообщение одного раздела.

        Если сообщение уже есть — редактирует его, иначе отправляет новое и
        запоминает message_id. Пустой раздел — удаляет ранее отправленное.
        """
        if not self.enabled or not day:
            return True
        text = sections.build_section_text(day, section)
        topic = settings.topic_for_section(section)
        async with async_session() as session:
            post = await crud.get_section_post(session, day.id, section)
            if not text:
                if post and post.message_id:
                    await self._delete_message(post.message_id)
                    await crud.clear_section_post(session, day.id, section)
                return True
            if post and post.message_id:
                if await self._edit_message(post.message_id, text):
                    return True
            msg = await self._send_message(text, topic)
            if msg is not None:
                await crud.set_section_post(session, day.id, section, msg.message_id)
                return True
            return False

    # ---------------------------------------------------------- day
    async def post_day(self, day: models.DayRecord) -> bool:
        if not self.enabled:
            return True
        ok = True
        for section in sections.SECTIONS:
            try:
                ok &= await self.publish_section(day, section)
            except Exception as e:  # noqa: BLE001
                logger.error("Ошибка публикации раздела %s: %s", section, e)
                ok = False
        return ok

    # ---------------------------------------------------------- analytics
    async def post_analytics(self, days: list[models.DayRecord], period_name: str) -> bool:
        if not self.enabled:
            return True
        ok = True
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
            if not buf:
                continue
            targets = [topic]
            analytics_topic = settings.TOPIC_ANALYTICS_ID
            if analytics_topic and analytics_topic not in targets:
                targets.append(analytics_topic)
            for tp in targets:
                ok &= await self._send_photo(buf, f"{caption_prefix} — {label}", tp)
        return ok
