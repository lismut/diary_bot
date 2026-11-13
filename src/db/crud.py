from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import models
from src.services import parser as P


LOAD_OPTIONS = (
    selectinload(models.DayRecord.log_lines),
    selectinload(models.DayRecord.exercises),
    selectinload(models.DayRecord.climbing_routes),
    selectinload(models.DayRecord.hangs),
    selectinload(models.DayRecord.meals),
    selectinload(models.DayRecord.routines),
)


# --------------------------------------------------------------- days
async def get_or_create_day(session: AsyncSession, day_date: date) -> models.DayRecord:
    res = await session.execute(
        select(models.DayRecord).where(models.DayRecord.date == day_date)
        .execution_options(populate_existing=True)
    )
    day = res.scalar_one_or_none()
    if not day:
        day = models.DayRecord(date=day_date)
        session.add(day)
        await session.commit()
        await session.refresh(day)
    return day


async def get_day(session: AsyncSession, day_date: date) -> Optional[models.DayRecord]:
    res = await session.execute(
        select(models.DayRecord).options(*LOAD_OPTIONS)
        .where(models.DayRecord.date == day_date)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()


async def get_days_range(session: AsyncSession, start: date, end: date) -> list[models.DayRecord]:
    res = await session.execute(
        select(models.DayRecord).options(*LOAD_OPTIONS)
        .where(and_(models.DayRecord.date >= start, models.DayRecord.date <= end))
        .order_by(models.DayRecord.date)
    )
    return list(res.scalars().all())


async def list_days(session: AsyncSession, limit: int = 30) -> list[models.DayRecord]:
    res = await session.execute(
        select(models.DayRecord).order_by(models.DayRecord.date.desc()).limit(limit)
    )
    return list(res.scalars().all())


async def get_all_days(session: AsyncSession) -> list[models.DayRecord]:
    """Все дни по возрастанию даты, со связанными записями."""
    res = await session.execute(
        select(models.DayRecord).options(*LOAD_OPTIONS).order_by(models.DayRecord.date)
    )
    return list(res.scalars().all())


async def completed_routines(session: AsyncSession, day: models.DayRecord) -> set[str]:
    res = await session.execute(
        select(models.RoutineCompletion).where(and_(
            models.RoutineCompletion.day_record_id == day.id,
            models.RoutineCompletion.completed.is_(True),
        ))
    )
    return {r.routine_name for r in res.scalars().all()}


# --------------------------------------------------------------- apply parsed
async def apply_parsed(session: AsyncSession, day: models.DayRecord, items: list[P.ParsedLine]) -> list[P.ParsedLine]:
    """Применяет разобранные строки к дню, создаёт структурные записи и LogLine."""
    applied: list[P.ParsedLine] = []
    for it in items:
        if it.category == P.DAY_HEADER:
            continue
        session.add(models.LogLine(
            day_record_id=day.id, category=it.category, raw_text=it.raw, payload=it.data,
        ))
        d = it.data
        if it.category == P.WAKE:
            day.wake_time = d.get("wake_time")
        elif it.category == P.SLEEP_TIME:
            day.sleep_time = d.get("sleep_time")
        elif it.category == P.SLEEP_QUALITY:
            day.sleep_quality = d.get("sleep_quality")
        elif it.category == P.WEIGHT:
            day.weight = d.get("weight")
        elif it.category == P.STEPS:
            day.steps = d.get("steps")
        elif it.category == P.MOOD:
            day.mood = d.get("mood")
        elif it.category == P.ENERGY:
            day.energy = d.get("energy")
        elif it.category == P.PULSE:
            day.resting_hr = d.get("resting_hr")
        elif it.category == P.WATER:
            day.water_l = d.get("water_l")
        elif it.category == P.MEAL:
            session.add(models.Meal(
                day_record_id=day.id, food_name=d.get("food_name"),
                amount_grams=d.get("amount_grams"), protein_g=d.get("protein_g"), detail=it.raw,
            ))
            if d.get("alcohol"):
                day.alcohol = True
        elif it.category == P.EXERCISE:
            session.add(models.Exercise(
                day_record_id=day.id, name=d.get("name"), sets=d.get("sets"),
                reps=d.get("reps"), weight=d.get("weight"), volume=d.get("volume"), detail=it.raw,
            ))
        elif it.category == P.POOL:
            session.add(models.Exercise(
                day_record_id=day.id, name="Бассейн", detail=it.raw,
            ))
        elif it.category == P.CLIMBING:
            session.add(models.ClimbingRoute(
                day_record_id=day.id, grade=d.get("grade"), kind=d.get("kind"),
                attempts=d.get("attempts"), count=d.get("count"), detail=it.raw,
            ))
        elif it.category == P.HANG:
            session.add(models.Hang(
                day_record_id=day.id, hold_size=d.get("hold_size"),
                added_weight=d.get("added_weight"), total_time_min=d.get("total_time_min"),
                protocol=d.get("protocol"), detail=it.raw,
            ))
        elif it.category == P.SUPPLEMENT:
            name = d.get("name")
            if name:
                await _set_routine(session, day, name, True, commit=False)
        elif it.category == P.NOTE:
            day.notes = (day.notes + "\n" if day.notes else "") + it.raw
        applied.append(it)

    day.sleep_hours = P.compute_sleep_hours(day.wake_time, day.sleep_time)
    await session.commit()
    return applied


async def _set_routine(session: AsyncSession, day: models.DayRecord, name: str, completed: bool, commit: bool = True):
    res = await session.execute(select(models.RoutineCompletion).where(and_(
        models.RoutineCompletion.day_record_id == day.id,
        models.RoutineCompletion.routine_name == name,
    )))
    r = res.scalar_one_or_none()
    if r:
        r.completed = completed
    else:
        session.add(models.RoutineCompletion(day_record_id=day.id, routine_name=name, completed=completed))
    if commit:
        await session.commit()


async def set_routine(session: AsyncSession, day: models.DayRecord, name: str, completed: bool):
    await _set_routine(session, day, name, completed)
    await session.refresh(day)


async def toggle_routine(session: AsyncSession, day: models.DayRecord, name: str) -> bool:
    """Переключает отметку добавки/рутины. Возвращает новое состояние."""
    res = await session.execute(select(models.RoutineCompletion).where(and_(
        models.RoutineCompletion.day_record_id == day.id,
        models.RoutineCompletion.routine_name == name,
    )))
    r = res.scalar_one_or_none()
    if r:
        r.completed = not r.completed
        new_state = bool(r.completed)
    else:
        session.add(models.RoutineCompletion(day_record_id=day.id, routine_name=name, completed=True))
        new_state = True
    await session.commit()
    return new_state


async def delete_log_line(session: AsyncSession, day: models.DayRecord, index: int) -> bool:
    """Удаляет строку по её порядковому номеру (1-based) среди log_lines дня
    и связанные структурные записи этого дня."""
    res = await session.execute(
        select(models.LogLine).where(models.LogLine.day_record_id == day.id)
        .order_by(models.LogLine.id)
    )
    lines = list(res.scalars().all())
    if index < 1 or index > len(lines):
        return False
    line = lines[index - 1]
    cat = line.category
    d = line.payload or {}

    model_by_cat = {
        P.MEAL: models.Meal, P.EXERCISE: models.Exercise, P.POOL: models.Exercise,
        P.CLIMBING: models.ClimbingRoute, P.HANG: models.Hang,
    }
    if cat in model_by_cat:
        model = model_by_cat[cat]
        rows = await session.execute(select(model).where(and_(
            model.day_record_id == day.id, model.detail == line.raw_text,
        )))
        for obj in rows.scalars().all():
            await session.delete(obj)
    elif cat == P.SUPPLEMENT:
        name = d.get("name")
        rows = await session.execute(select(models.RoutineCompletion).where(and_(
            models.RoutineCompletion.day_record_id == day.id,
            models.RoutineCompletion.routine_name == name,
        )))
        for r in rows.scalars().all():
            await session.delete(r)

    await session.delete(line)
    await session.commit()

    await _recompute_day_fields(session, day)
    return True


async def _recompute_day_fields(session: AsyncSession, day: models.DayRecord):
    res = await session.execute(
        select(models.LogLine).where(models.LogLine.day_record_id == day.id)
        .order_by(models.LogLine.id)
    )
    simple = {}
    for line in res.scalars().all():
        if line.category in (P.WAKE, P.SLEEP_TIME, P.SLEEP_QUALITY, P.WEIGHT, P.STEPS,
                             P.MOOD, P.ENERGY, P.PULSE, P.WATER):
            simple[line.category] = (line.payload or {})

    day.wake_time = simple.get(P.WAKE, {}).get("wake_time")
    day.sleep_time = simple.get(P.SLEEP_TIME, {}).get("sleep_time")
    day.sleep_quality = simple.get(P.SLEEP_QUALITY, {}).get("sleep_quality")
    day.weight = simple.get(P.WEIGHT, {}).get("weight")
    day.steps = simple.get(P.STEPS, {}).get("steps")
    day.mood = simple.get(P.MOOD, {}).get("mood")
    day.energy = simple.get(P.ENERGY, {}).get("energy")
    day.resting_hr = simple.get(P.PULSE, {}).get("resting_hr")
    day.water_l = simple.get(P.WATER, {}).get("water_l")
    day.sleep_hours = P.compute_sleep_hours(day.wake_time, day.sleep_time)
    await session.commit()


# --------------------------------------------------------------- user settings
async def get_setting(session: AsyncSession, key: str) -> Optional[str]:
    res = await session.execute(select(models.UserSettings).where(models.UserSettings.key == key))
    s = res.scalar_one_or_none()
    return s.value if s else None


async def set_setting(session: AsyncSession, key: str, value: str):
    res = await session.execute(select(models.UserSettings).where(models.UserSettings.key == key))
    s = res.scalar_one_or_none()
    if s:
        s.value = value
    else:
        session.add(models.UserSettings(key=key, value=value))
    await session.commit()
