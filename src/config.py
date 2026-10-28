from pydantic_settings import BaseSettings
from typing import Optional
import json
import os


class Settings(BaseSettings):
    BOT_TOKEN: str
    MAIN_CHAT_ID: Optional[int] = None
    REPORT_CHAT_ID: Optional[int] = None
    
    TOPIC_SLEEP_ID: Optional[int] = None
    TOPIC_WEIGHT_ID: Optional[int] = None
    TOPIC_TRAINING_ID: Optional[int] = None
    TOPIC_CLIMBING_ID: Optional[int] = None
    TOPIC_HANGS_ID: Optional[int] = None
    TOPIC_STEPS_ID: Optional[int] = None
    TOPIC_NUTRITION_ID: Optional[int] = None
    TOPIC_ROUTINES_ID: Optional[int] = None
    TOPIC_ANALYTICS_ID: Optional[int] = None
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/diary.db"
    LOG_LEVEL: str = "INFO"
    
    PROTEIN_NORM_PER_DAY: int = 120
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
