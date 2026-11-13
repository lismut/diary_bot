#!/usr/bin/env python3
"""Импорт дневника из текстового файла в базу.

Примеры:
    python scripts/import_diary.py diary
    python scripts/import_diary.py diary --reset
    python scripts/import_diary.py diary --dry-run
    python scripts/import_diary.py diary --year 2025
"""
import argparse
import asyncio
import logging
import os
import sys

# config требует BOT_TOKEN, для импорта он не нужен
os.environ.setdefault("BOT_TOKEN", "import-placeholder")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.base import init_db, async_session  # noqa: E402
from src.services.importer import import_diary_file  # noqa: E402


async def run(args):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    await init_db()
    async with async_session() as session:
        stats = await import_diary_file(
            session, args.file, year=args.year, reset=args.reset, dry_run=args.dry_run,
        )
    print("\n=== Импорт завершён ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


def main():
    p = argparse.ArgumentParser(description="Импорт дневника в базу")
    p.add_argument("file", help="путь к файлу дневника")
    p.add_argument("--year", type=int, default=None, help="год для дат без года")
    p.add_argument("--reset", action="store_true", help="очистить базу перед импортом")
    p.add_argument("--dry-run", action="store_true", help="только показать разбор, не сохранять")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
