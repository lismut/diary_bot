from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_to_none(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str

    # Чаты
    MAIN_CHAT_ID: Optional[int] = None          # личный чат с ботом
    REPORT_CHAT_ID: Optional[int] = None        # чат-форум для отчетов
    ADMIN_IDS: str = ""                          # через запятую, кому разрешено

    # Топики отчетного чата (thread_id)
    TOPIC_DIARY_ID: Optional[int] = None         # сырой дневник / история
    TOPIC_SLEEP_ID: Optional[int] = None
    TOPIC_WEIGHT_ID: Optional[int] = None
    TOPIC_TRAINING_ID: Optional[int] = None
    TOPIC_CLIMBING_ID: Optional[int] = None
    TOPIC_HANGS_ID: Optional[int] = None
    TOPIC_STEPS_ID: Optional[int] = None
    TOPIC_NUTRITION_ID: Optional[int] = None
    TOPIC_ROUTINES_ID: Optional[int] = None
    TOPIC_ANALYTICS_ID: Optional[int] = None

    # База
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/diary.db"

    # Логи
    LOG_LEVEL: str = "INFO"
    TZ: str = "Europe/Moscow"

    # Питание
    PROTEIN_NORM_PER_DAY: int = 120

    # Отчёты
    AUTO_REPORT: bool = True                     # автоотчёт за прошедший день
    REPORT_HOUR: int = 9                         # во сколько постить
    REPORT_MINUTE: int = 0

    @field_validator(
        "MAIN_CHAT_ID", "REPORT_CHAT_ID",
        "TOPIC_DIARY_ID", "TOPIC_SLEEP_ID", "TOPIC_WEIGHT_ID", "TOPIC_TRAINING_ID",
        "TOPIC_CLIMBING_ID", "TOPIC_HANGS_ID", "TOPIC_STEPS_ID", "TOPIC_NUTRITION_ID",
        "TOPIC_ROUTINES_ID", "TOPIC_ANALYTICS_ID",
        mode="before",
    )
    @classmethod
    def _none_if_empty(cls, v):
        return _empty_to_none(v)

    @property
    def admin_ids(self) -> list[int]:
        out = []
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part:
                try:
                    out.append(int(part))
                except ValueError:
                    pass
        return out

    def topic_for(self, category: str) -> Optional[int]:
        return {
            "diary": self.TOPIC_DIARY_ID,
            "wake": self.TOPIC_SLEEP_ID,
            "sleep_time": self.TOPIC_SLEEP_ID,
            "sleep_quality": self.TOPIC_SLEEP_ID,
            "weight": self.TOPIC_WEIGHT_ID,
            "steps": self.TOPIC_STEPS_ID,
            "meal": self.TOPIC_NUTRITION_ID,
            "exercise": self.TOPIC_TRAINING_ID,
            "climbing": self.TOPIC_CLIMBING_ID,
            "hang": self.TOPIC_HANGS_ID,
            "supplement": self.TOPIC_ROUTINES_ID,
            "routines": self.TOPIC_ROUTINES_ID,
            "analytics": self.TOPIC_ANALYTICS_ID,
        }.get(category)


settings = Settings()
