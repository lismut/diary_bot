"""Импорт существующего дневника (файла в формате заметок) в базу."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import crud, models
from src.services import parser as P

logger = logging.getLogger(__name__)


async def reset_all(session: AsyncSession):
    for table in (
        models.LogLine, models.Meal, models.Exercise, models.ClimbingRoute,
        models.Hang, models.RoutineCompletion, models.DayRecord,
    ):
        await session.execute(delete(table))
    await session.commit()


async def import_diary_file(
    session: AsyncSession,
    path: str,
    year: Optional[int] = None,
    reset: bool = False,
    dry_run: bool = False,
) -> dict:
    with open(path, encoding="utf-8") as f:
        raw_lines = f.read().splitlines()

    year = year or date.today().year
    if reset and not dry_run:
        await reset_all(session)

    stats = {"days": 0, "lines": 0, "meals": 0, "exercises": 0,
             "climbing": 0, "hangs": 0, "supplements": 0, "skipped_days": 0}

    current_day: Optional[models.DayRecord] = None
    current_date: Optional[date] = None
    has_wake = False
    has_sleep = False

    for raw in raw_lines:
        text = raw.strip()
        if not text:
            continue

        header = P.detect_day_header(text)
        if header:
            y = header.get("year") or year
            try:
                current_date = date(y, header["month"], header["day"])
            except ValueError:
                logger.warning("Некорректная дата в заголовке: %r", text)
                continue
            current_day = await crud.get_or_create_day(session, current_date)
            await session.refresh(current_day, ["log_lines"])
            if current_day.log_lines and not reset:
                stats["skipped_days"] += 1
                current_day = None
                continue
            stats["days"] += 1
            has_wake = bool(current_day.wake_time)
            has_sleep = bool(current_day.sleep_time)
            continue

        if current_day is None:
            continue

        items = P.parse_line(text, has_wake=has_wake, has_sleep=has_sleep)
        if dry_run:
            for it in items:
                logger.info("%s | %s", current_date, it.display)
            continue

        await crud.apply_parsed(session, current_day, items)
        for it in items:
            stats["lines"] += 1
            if it.category == P.WAKE:
                has_wake = True
            elif it.category == P.SLEEP_TIME:
                has_sleep = True
            elif it.category == P.MEAL:
                stats["meals"] += 1
            elif it.category == P.EXERCISE or it.category == P.POOL:
                stats["exercises"] += 1
            elif it.category == P.CLIMBING:
                stats["climbing"] += 1
            elif it.category == P.HANG:
                stats["hangs"] += 1
            elif it.category == P.SUPPLEMENT:
                stats["supplements"] += 1

    return stats
