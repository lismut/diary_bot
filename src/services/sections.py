"""Реестр разделов дневника: какие строки в какой топик и как собрать текст сообщения.

Раздел — это «тема» отчётного чата (сон, питание, тренировка, ЛФК и т.д.).
По каждому разделу в отчётном чате живёт одно сообщение, которое бот
создаёт при первой публикации и потом правит (edit), а не шлёт заново.
"""
from __future__ import annotations

import html
from typing import Optional

from src.config import settings
from src.db import models
from src.services import parser as P
from src.utils.helpers import format_date_ru

# Порядок публикации разделов в отчётный чат.
SECTIONS = [
    "diary", "sleep", "weight", "steps", "nutrition",
    "training", "climbing", "hangs", "routines", "lfk",
]

SECTION_TITLES = {
    "diary": "📝 Записи дня",
    "sleep": "😴 Сон",
    "weight": "⚖️ Вес и тело",
    "steps": "👟 Шаги",
    "nutrition": "🍽 Питание",
    "training": "💪 Тренировка",
    "climbing": "🧗 Скалодром",
    "hangs": "🤸 Висы",
    "routines": "✅ Добавки/рутины",
    "lfk": "🤸‍♂️ ЛФК",
}

# Категории строк, относящиеся к разделу (None — все строки дня).
SECTION_CATEGORIES: dict[str, Optional[set[str]]] = {
    "diary": None,
    "sleep": {P.WAKE, P.SLEEP_TIME, P.SLEEP_QUALITY},
    "weight": {P.WEIGHT, P.PULSE, P.MOOD, P.ENERGY, P.WATER},
    "steps": {P.STEPS},
    "nutrition": {P.MEAL},
    "training": {P.EXERCISE, P.POOL, P.LFK, P.HANG},
    "climbing": {P.CLIMBING},
    "hangs": {P.HANG},
    "routines": {P.SUPPLEMENT},
    "lfk": {P.LFK},
}

_CATEGORY_SECTION = {
    P.WAKE: "sleep", P.SLEEP_TIME: "sleep", P.SLEEP_QUALITY: "sleep",
    P.WEIGHT: "weight", P.PULSE: "weight", P.MOOD: "weight",
    P.ENERGY: "weight", P.WATER: "weight",
    P.STEPS: "steps",
    P.MEAL: "nutrition",
    P.EXERCISE: "training", P.POOL: "training",
    P.CLIMBING: "climbing",
    P.HANG: "hangs",
    P.SUPPLEMENT: "routines",
    P.LFK: "lfk",
    P.NOTE: "diary",
}


def section_for_category(category: str) -> Optional[str]:
    """Раздел, в который попадает строка данной категории."""
    return _CATEGORY_SECTION.get(category)


def related_sections(section: str) -> list[str]:
    """Разделы, которые нужно обновить вместе с данным.

    Тренировка включает ЛФК и висы, поэтому при публикации тренировки
    нужно обновить и их отдельные разделы (и наоборот).
    """
    cats = SECTION_CATEGORIES.get(section)
    if not cats:
        return [section]
    out = [section]
    for other, other_cats in SECTION_CATEGORIES.items():
        if other != section and other_cats and (other_cats & cats):
            out.append(other)
    return out


def section_log_lines(day: models.DayRecord, section: str) -> list[models.LogLine]:
    """Строки дня, относящиеся к разделу (по возрастанию id, без дублей).

    Одна введённая строка может дать несколько log_lines (например,
    «Творог 250г, кешью 20г» → 2 записи). Для показа/удаления схлопываем
    одинаковые строки в одну.
    """
    if not day or not day.log_lines:
        return []
    lines = sorted(day.log_lines, key=lambda x: x.id)
    cats = SECTION_CATEGORIES.get(section)
    if cats is not None:
        lines = [ln for ln in lines if ln.category in cats]
    seen: set[str] = set()
    out: list[models.LogLine] = []
    for ln in lines:
        if ln.raw_text in seen:
            continue
        seen.add(ln.raw_text)
        out.append(ln)
    return out


def _title(day: models.DayRecord) -> str:
    return f"📆 <b>{format_date_ru(day.date)}</b>"


def _g(v) -> str:
    if v is None:
        return "0"
    return f"{v:g}"


def build_section_text(day: models.DayRecord, section: str) -> str:
    """HTML-текст сообщения раздела. Пустая строка — публиковать нечего."""
    if not day:
        return ""
    if section == "sleep":
        return _sleep_text(day)
    if section == "weight":
        return _weight_text(day)
    if section == "steps":
        if not day.steps:
            return ""
        return f"{_title(day)}\n\n👟 Шаги: <b>{day.steps}</b>"
    if section == "nutrition":
        return _nutrition_text(day)
    if section == "routines":
        return _routines_text(day)
    return _log_text(day, section)


def _sleep_text(day: models.DayRecord) -> str:
    if not (day.wake_time or day.sleep_time or day.sleep_quality):
        return ""
    t = f"{_title(day)}\n\n😴 <b>Сон</b>\n"
    if day.sleep_time:
        t += f"Засыпание: {day.sleep_time}\n"
    if day.wake_time:
        t += f"Пробуждение: {day.wake_time}\n"
    if day.sleep_hours:
        t += f"Длительность: {day.sleep_hours} ч\n"
    if day.sleep_quality:
        t += f"Качество: {day.sleep_quality}/10"
    return t.rstrip()


def _weight_text(day: models.DayRecord) -> str:
    if not (day.weight or day.resting_hr or day.mood or day.energy or day.water_l):
        return ""
    t = f"{_title(day)}\n\n"
    if day.weight:
        t += f"⚖️ Вес: <b>{day.weight} кг</b>\n"
    if day.resting_hr:
        t += f"❤️ Пульс покоя: {day.resting_hr}\n"
    if day.mood:
        t += f"🙂 Настроение: {day.mood}/10\n"
    if day.energy:
        t += f"⚡ Самочувствие: {day.energy}/10\n"
    if day.water_l:
        t += f"💧 Вода: {day.water_l} л\n"
    return t.rstrip()


def _nutrition_text(day: models.DayRecord) -> str:
    if not day.meals:
        return ""
    total = day.protein_total()
    norm = settings.PROTEIN_NORM_PER_DAY
    mark = "🟢" if total >= norm else "🟡"
    t = f"{_title(day)}\n\n🍽 <b>Питание</b>\n"
    for m in day.meals:
        t += f"• {html.escape(m.food_name or '')} {_g(m.amount_grams)}г (+{_g(m.protein_g)}г)\n"
    t += f"\n{mark} Белок: <b>{total}г</b> из {norm}г"
    return t


def _routines_text(day: models.DayRecord) -> str:
    done = [r.routine_name for r in day.routines if r.completed]
    if not done:
        return ""
    t = f"{_title(day)}\n\n✅ <b>Добавки/рутины:</b>\n"
    t += "\n".join(f"• {html.escape(n)}" for n in done)
    return t


def climb_counts(day: models.DayRecord) -> dict[str, int]:
    """Сколько раз в дне встретилась каждая трасса (по исходному тексту).

    Одинаковые строки схлопываются для показа, но каждая кнопка — отдельная
    трасса, поэтому показываем «×5», а статистику считаем по всем записям.
    """
    out: dict[str, int] = {}
    if not day:
        return out
    for r in (day.climbing_routes or []):
        key = r.detail or ""
        out[key] = out.get(key, 0) + 1
    return out


def _log_text(day: models.DayRecord, section: str) -> str:
    lines = section_log_lines(day, section)
    if not lines:
        return ""
    t = f"{_title(day)}\n\n{SECTION_TITLES.get(section, '')}\n"
    counts = climb_counts(day) if section == "climbing" else {}
    for ln in lines:
        n = counts.get(ln.raw_text, 1)
        suffix = f" <b>×{n}</b>" if n > 1 else ""
        t += f"• {html.escape(ln.raw_text)}{suffix}\n"
    if section == "climbing":
        by_grade: dict[str, list[int]] = {}
        # Считаем по ВСЕМ трассам дня, а не по схлопнутым строкам лога.
        route_data: list[tuple] = []
        for r in (day.climbing_routes or []):
            route_data.append((r.grade, r.kind, r.attempts, r.sends))
        if not route_data:
            # fallback для записей без структурных строк (старый формат)
            for ln in (day.log_lines or []):
                if ln.category == P.CLIMBING:
                    d = ln.payload or {}
                    route_data.append((d.get("grade"), d.get("kind"),
                                       d.get("attempts"), d.get("sends")))
        for g, kind, att, sent in route_data:
            g = (g or "?").lower()
            if sent is None:
                sent = 1 if kind in ("send", "flash") else 0
            e = by_grade.setdefault(g, [0, 0])
            e[0] += att or 0
            e[1] += int(sent)
        if by_grade:
            order = ["5", "6a", "6b", "6c", "7a", "7b", "7c"]
            grades = [g for g in order if g in by_grade] + \
                     sorted(g for g in by_grade if g not in order)
            t += "\n<b>По категориям:</b>\n"
            for g in grades:
                att, sent = by_grade[g]
                t += f"• {g}: {att} попыт., {sent} пролазов\n"
    return t.rstrip()
