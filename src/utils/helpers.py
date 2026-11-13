import re
from datetime import date, timedelta
from typing import Optional

_MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def format_date_ru(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def format_date_short(d: date) -> str:
    return d.strftime("%d.%m")


def parse_date(text: str, default_year: Optional[int] = None) -> Optional[date]:
    """Разбирает 'сегодня', 'вчера', '05.11', '5.11.2025'."""
    if not text:
        return None
    t = text.strip().lower()
    today = date.today()
    default_year = default_year or today.year

    if t in ("сегодня", "today", "с"):
        return today
    if t in ("вчера", "yesterday", "в"):
        return today - timedelta(days=1)
    if t in ("позавчера",):
        return today - timedelta(days=2)

    m = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?", t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else default_year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None
