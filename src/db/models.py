from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship

from src.db.base import Base


class DayRecord(Base):
    """Один день дневника."""
    __tablename__ = "day_records"

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, index=True, nullable=False)

    # Сон
    wake_time = Column(String)          # время пробуждения, "07:30"
    sleep_time = Column(String)         # время засыпания, "00:30"
    sleep_hours = Column(Float)         # рассчитывается
    sleep_quality = Column(Integer)     # 1..10

    # Тело
    weight = Column(Float)
    resting_hr = Column(Integer)        # пульс покоя
    mood = Column(Integer)              # настроение 1..10
    energy = Column(Integer)            # самочувствие 1..10

    # Активность
    steps = Column(Integer)
    water_l = Column(Float)             # вода, литры
    alcohol = Column(Boolean)           # был алкоголь

    # Заметки
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    log_lines = relationship("LogLine", back_populates="day_record", cascade="all, delete-orphan")
    exercises = relationship("Exercise", back_populates="day_record", cascade="all, delete-orphan")
    climbing_routes = relationship("ClimbingRoute", back_populates="day_record", cascade="all, delete-orphan")
    hangs = relationship("Hang", back_populates="day_record", cascade="all, delete-orphan")
    meals = relationship("Meal", back_populates="day_record", cascade="all, delete-orphan")
    routines = relationship("RoutineCompletion", back_populates="day_record", cascade="all, delete-orphan")

    def protein_total(self) -> float:
        return round(sum(m.protein_g or 0 for m in self.meals), 1)


class LogLine(Base):
    """Сырая строка дневника (как в заметках) + распознанная категория."""
    __tablename__ = "log_lines"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="log_lines")

    category = Column(String, index=True)   # weight/sleep/meal/exercise/...
    raw_text = Column(Text, nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="exercises")

    name = Column(String, nullable=False)
    sets = Column(Integer)
    reps = Column(Integer)
    weight = Column(Float)
    volume = Column(Float)          # sets*reps*weight, если применимо
    detail = Column(Text)           # исходная строка


class ClimbingRoute(Base):
    __tablename__ = "climbing_routes"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="climbing_routes")

    grade = Column(String)          # 6a, 6b, 7a ...
    kind = Column(String)           # flash / send / attempts
    attempts = Column(Integer)
    sends = Column(Integer)
    count = Column(Integer)         # сколько трасс этого грейда
    detail = Column(Text)


class Hang(Base):
    __tablename__ = "hangs"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="hangs")

    hold_size = Column(String)      # "20мм"
    added_weight = Column(Float)    # кг отягощения
    duration_seconds = Column(Integer)
    total_time_min = Column(Float)  # время виса
    protocol = Column(String)       # "10/50"
    detail = Column(Text)


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="meals")

    food_name = Column(String)
    amount_grams = Column(Float)
    protein_g = Column(Float)
    detail = Column(Text)


class RoutineCompletion(Base):
    __tablename__ = "routine_completions"

    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"), index=True)
    day_record = relationship("DayRecord", back_populates="routines")

    routine_name = Column(String)
    completed = Column(Boolean, default=True)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
