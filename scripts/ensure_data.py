#!/usr/bin/env python3
"""При первом запуске (пустая база) автоматически заливает дневник из файла `diary`.

Управляется переменной AUTO_IMPORT (по умолчанию true).
"""
import asyncio
import os
import sys

os.environ.setdefault("BOT_TOKEN", "auto-import")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from src.db.base import init_db, async_session  # noqa: E402
from src.db import models  # noqa: E402
from src.services.importer import import_diary_file  # noqa: E402

DIARY_FILE = os.environ.get("DIARY_FILE", "diary")


async def main():
    if os.environ.get("AUTO_IMPORT", "true").lower() not in ("1", "true", "yes"):
        return
    if not os.path.exists(DIARY_FILE):
        return
    await init_db()
    async with async_session() as session:
        count = (await session.execute(select(func.count()).select_from(models.DayRecord))).scalar()
        if count:
            print(f"В базе уже {count} дней — автоимпорт пропущен")
            return
        print(f"База пуста — импортирую {DIARY_FILE}...")
        stats = await import_diary_file(session, DIARY_FILE)
        print("Импорт:", stats)


if __name__ == "__main__":
    asyncio.run(main())
