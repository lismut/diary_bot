from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date, datetime
from typing import Optional, List
from src.db import models


async def get_or_create_day(session: AsyncSession, day_date: date) -> models.DayRecord:
    result = await session.execute(select(models.DayRecord).where(models.DayRecord.date == day_date))
    day_record = result.scalar_one_or_none()
    if not day_record:
        day_record = models.DayRecord(date=day_date)
        session.add(day_record)
        await session.commit()
        await session.refresh(day_record)
    return day_record


async def update_sleep(session: AsyncSession, day_date: date, wake_up: str = None, sleep_time: str = None, sleep_quality: int = None):
    day_record = await get_or_create_day(session, day_date)
    if wake_up:
        day_record.wake_up_time = wake_up
    if sleep_time:
        day_record.sleep_time = sleep_time
    if sleep_quality:
        day_record.sleep_quality = sleep_quality
    # Calculate sleep hours if both times provided
    if day_record.wake_up_time and day_record.sleep_time:
        try:
            # Simple calculation - could be improved
            wh = int(day_record.wake_up_time.split(':')[0])
            wm = int(day_record.wake_up_time.split(':')[1])
            sh = int(day_record.sleep_time.split(':')[0])
            sm = int(day_record.sleep_time.split(':')[1])
            # Assume sleep was previous day if sleep_time > wake_up_time conceptually
            sleep_minutes = (wh * 60 + wm) - (sh * 60 + sm)
            if sleep_minutes < 0:
                sleep_minutes += 24 * 60
            day_record.sleep_hours = round(sleep_minutes / 60, 2)
        except:
            pass
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def update_weight(session: AsyncSession, day_date: date, weight: float):
    day_record = await get_or_create_day(session, day_date)
    day_record.weight = weight
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def add_exercise(session: AsyncSession, day_date: date, name: str, sets: int = None, reps: int = None, weight: float = None):
    day_record = await get_or_create_day(session, day_date)
    exercise = models.Exercise(day_record_id=day_record.id, name=name, sets=sets, reps=reps, weight=weight)
    if sets and reps and weight:
        exercise.load_volume = sets * reps * weight
    session.add(exercise)
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def add_climbing_route(session: AsyncSession, day_date: date, route_name: str, grade: str = None, attempts: int = None, sends: int = None):
    day_record = await get_or_create_day(session, day_date)
    route = models.ClimbingRoute(day_record_id=day_record.id, route_name=route_name, grade=grade, attempts=attempts, sends=sends)
    session.add(route)
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def add_hang(session: AsyncSession, day_date: date, hold_size: str, weight: float = None, duration_seconds: int = None, sets: int = None):
    day_record = await get_or_create_day(session, day_date)
    hang = models.Hang(day_record_id=day_record.id, hold_size=hold_size, weight=weight, duration_seconds=duration_seconds, sets=sets)
    session.add(hang)
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def add_meal(session: AsyncSession, day_date: date, food_name: str, amount_grams: float, meal_type: str = "snack", protein_g: float = 0.0):
    day_record = await get_or_create_day(session, day_date)
    meal = models.Meal(day_record_id=day_record.id, meal_type=meal_type, food_name=food_name, amount_grams=amount_grams, protein_g=protein_g)
    session.add(meal)
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def update_steps(session: AsyncSession, day_date: date, steps: int):
    day_record = await get_or_create_day(session, day_date)
    day_record.steps = steps
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def set_routine(session: AsyncSession, day_date: date, routine_name: str, completed: bool):
    day_record = await get_or_create_day(session, day_date)
    # Check if exists
    result = await session.execute(select(models.RoutineCompletion).where(
        and_(models.RoutineCompletion.day_record_id == day_record.id, 
             models.RoutineCompletion.routine_name == routine_name)
    ))
    routine = result.scalar_one_or_none()
    if routine:
        routine.completed = completed
    else:
        routine = models.RoutineCompletion(day_record_id=day_record.id, routine_name=routine_name, completed=completed)
        session.add(routine)
    await session.commit()
    await session.refresh(day_record)
    return day_record


async def get_day(session: AsyncSession, day_date: date) -> Optional[models.DayRecord]:
    result = await session.execute(select(models.DayRecord).where(models.DayRecord.date == day_date))
    return result.scalar_one_or_none()


async def get_days_range(session: AsyncSession, start_date: date, end_date: date) -> List[models.DayRecord]:
    result = await session.execute(select(models.DayRecord).where(
        and_(models.DayRecord.date >= start_date, models.DayRecord.date <= end_date)
    ).order_by(models.DayRecord.date))
    return list(result.scalars().all())
