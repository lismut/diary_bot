from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from src.db.base import Base


class DayRecord(Base):
    __tablename__ = "day_records"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Sleep
    wake_up_time = Column(String)
    sleep_time = Column(String)
    sleep_hours = Column(Float)
    sleep_quality = Column(Integer)  # 1-10
    
    # Weight
    weight = Column(Float)
    
    # Steps
    steps = Column(Integer)
    
    # Notes
    notes = Column(Text)
    
    # Relations
    exercises = relationship("Exercise", back_populates="day_record", cascade="all, delete-orphan")
    climbing_routes = relationship("ClimbingRoute", back_populates="day_record", cascade="all, delete-orphan")
    hangs = relationship("Hang", back_populates="day_record", cascade="all, delete-orphan")
    meals = relationship("Meal", back_populates="day_record", cascade="all, delete-orphan")
    routines = relationship("RoutineCompletion", back_populates="day_record", cascade="all, delete-orphan")


class Exercise(Base):
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"))
    day_record = relationship("DayRecord", back_populates="exercises")
    
    name = Column(String, nullable=False)
    sets = Column(Integer)
    reps = Column(Integer)
    weight = Column(Float)
    load_volume = Column(Float)  # calculated or entered
    notes = Column(Text)


class ClimbingRoute(Base):
    __tablename__ = "climbing_routes"
    
    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"))
    day_record = relationship("DayRecord", back_populates="climbing_routes")
    
    route_name = Column(String)
    grade = Column(String)  # difficulty category
    attempts = Column(Integer)
    sends = Column(Integer)  # completed
    notes = Column(Text)


class Hang(Base):
    __tablename__ = "hangs"
    
    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"))
    day_record = relationship("DayRecord", back_populates="hangs")
    
    hold_size = Column(String)
    weight = Column(Float)
    duration_seconds = Column(Integer)
    sets = Column(Integer)
    notes = Column(Text)


class Meal(Base):
    __tablename__ = "meals"
    
    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"))
    day_record = relationship("DayRecord", back_populates="meals")
    
    meal_type = Column(String)  # breakfast, lunch, dinner, snack
    food_name = Column(String)
    amount_grams = Column(Float)
    protein_g = Column(Float)
    notes = Column(Text)


class RoutineCompletion(Base):
    __tablename__ = "routine_completions"
    
    id = Column(Integer, primary_key=True)
    day_record_id = Column(Integer, ForeignKey("day_records.id"))
    day_record = relationship("DayRecord", back_populates="routines")
    
    routine_name = Column(String)
    completed = Column(Boolean, default=False)


class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
