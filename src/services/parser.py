"""Разбор свободных строк дневника в структурированные записи.

Бот принимает текст как в заметках, например:

    7:30
    Сон 7/10
    78.1
    Творог 250г, кешью 20г
    Лфк с резинкой
    Висы 10мм 10кг 5х10/50
    5 6а, 4 6б, 6с флеш
    Креатин, коллаген
    Сон 00:30

Каждая строка классифицируется, из неё извлекаются метрики.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# --- категории ---
DAY_HEADER = "day_header"
WAKE = "wake"
SLEEP_TIME = "sleep_time"
SLEEP_QUALITY = "sleep_quality"
WEIGHT = "weight"
STEPS = "steps"
MOOD = "mood"
ENERGY = "energy"
PULSE = "pulse"
WATER = "water"
MEAL = "meal"
EXERCISE = "exercise"
CLIMBING = "climbing"
HANG = "hang"
SUPPLEMENT = "supplement"
POOL = "pool"
LFK = "lfk"
NOTE = "note"

_CFG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")

_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
_WEEKDAY_RE = r"(пн|вт|ср|чт|пт|сб|вс|пон|втор|сред|чет|пят|суб|воскр)"
DAY_HEADER_RE = re.compile(
    r"^\s*" + _WEEKDAY_RE + r"\.?\s+(\d{1,2})[.\s](\d{1,2})(?:[.\s](\d{2,4}))?\s*$",
    re.IGNORECASE,
)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.](\d{2})\b")
BARE_TIME_RE = re.compile(r"^\s*([01]?\d|2[0-3])[:.](\d{2})\s*$")
BARE_DECIMAL_RE = re.compile(r"^\s*(\d{2,3})[.,](\d{1,2})\s*(?:кг|kg)?\s*$")
QUALITY_RE = re.compile(r"(\d{1,2})\s*/\s*10")
GRAMS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:мл|ml|г|гр|грамм|g)\b", re.IGNORECASE)
NUM_AFTER_RE = re.compile(r"^[^\d]{0,30}?(\d+(?:[.,]\d+)?)")
GRADE_RE = re.compile(r"(?<![a-zа-я0-9])([678])\s*([abcабс])", re.IGNORECASE)
GRADE_COUNT_RE = re.compile(r"(\d+)?\s*([678])\s*([abc])", re.IGNORECASE)
SETS_REPS_RE = re.compile(r"(\d+)\s*[хx]\s*(\d+)")
WEIGHT_X_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*кг\s*[хx]\s*(\d+)", re.IGNORECASE)
HOLD_MM_RE = re.compile(r"(\d{1,2})\s*мм")
PROTOCOL_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{2,3})")
DURATION_MIN_RE = re.compile(r"(\d+)\s*мин", re.IGNORECASE)
DURATION_SEC_RE = re.compile(r"(\d+)\s*сек", re.IGNORECASE)
DISTANCE_KM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*км", re.IGNORECASE)

_GRADE_TRANS = str.maketrans({"а": "a", "б": "b", "с": "c", "в": "d", "А": "A", "Б": "B", "С": "C"})

_NUM_WORDS = {
    "один": 1, "одно": 1, "одна": 1, "два": 2, "две": 2, "три": 3,
    "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
}

_SUPPLEMENT_HINTS = [
    "креатин", "витамин", "омега", "протеин", "магний", "коллаген",
    "рыбий жир", "цинк", "железо", "b12", "d3",
]

# Слитые в одну добавки: разные названия -> одно каноническое (коллаген).
_SUPPLEMENT_MERGE = {
    "раствор для связок": "коллаген",
    "добавки для суставов": "коллаген",
    "добавка для суставов": "коллаген",
    "для суставов": "коллаген",
    "для связок": "коллаген",
    "коллаген": "коллаген",
    "связки/суставы": "коллаген",
    "связки": "коллаген",
    "суставы": "коллаген",
}

_LFK_HINTS = ["лфк", "лечебн", "суставная гимнастика"]

_POOL_HINTS = ["бассейн", "басс ", "плаван", "басс"]
_HANG_HINTS = ["фингер", "10/50", "вис", "пасс", "пассик", "пассив", "мм"]

_EXERCISE_HINTS = [
    "разминка", "велик", "велосипед", "бег", "гиря", "гантел", "подтяг", "становая",
    "кольца", "отжим", "подъем ног", "подьем ног", "стойка", "бодибар", "резинк", "резин",
    "параллетс", "парадлетс", "параллетсы", "турник", "револьвер", "офп", "растяжк",
    "ходьба", "присед", "жим", "тяга", "планка", "складк", "креветка", "мост", "уголк",
    "горизонт", "гориз", "подводящ", "подвод", "разводк", "лук", "трицепс", "бицепс",
    "подход", "повтор", "негатив", "вис ",
]

_WEIGHT_STANDALONE_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*кг(?:\s*[хx]?\s*\d+)?\s*$", re.IGNORECASE)


@dataclass
class ParsedLine:
    category: str
    data: dict = field(default_factory=dict)
    raw: str = ""
    display: str = ""

    def as_dict(self) -> dict:
        return {"category": self.category, "data": self.data, "raw": self.raw}


# ------------------------------------------------------------------ config
_foods_cache: Optional[list] = None


def _load_foods() -> list:
    global _foods_cache
    if _foods_cache is not None:
        return _foods_cache
    try:
        with open(os.path.join(_CFG_DIR, "foods.json"), encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
    except Exception:
        products = []
    # плоский список (regex alias -> product), длинные алиасы раньше
    flat = []
    for p in products:
        for alias in p.get("aliases", [p.get("name", "")]):
            a = alias.lower()
            # граница только слева: не даём "кола" совпасть внутри "шоколад",
            # но разрешаем основы слов ("печеньк" -> "печеньки")
            rx = re.compile(r"(?<![а-яёa-z0-9])" + re.escape(a))
            flat.append((len(a), rx, p))
    flat.sort(key=lambda x: -x[0])
    _foods_cache = flat
    return flat


def _load_routines() -> dict:
    try:
        with open(os.path.join(_CFG_DIR, "routines.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"supplements": [], "routines": []}


def known_supplements() -> list[str]:
    seen = []
    for s in _load_routines().get("supplements", []) + _SUPPLEMENT_HINTS:
        s = s.lower()
        if s not in seen:
            seen.append(s)
    return seen


# ------------------------------------------------------------------ helpers
def normalize_grades(text: str) -> str:
    return text.translate(_GRADE_TRANS)


def _fmt_time(h: str, m: str) -> str:
    return f"{int(h):02d}:{m}"


def _parse_time_in(text: str) -> Optional[str]:
    m = TIME_RE.search(text)
    if m:
        return _fmt_time(m.group(1), m.group(2))
    return None


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def compute_sleep_hours(wake: Optional[str], sleep: Optional[str]) -> Optional[float]:
    if not wake or not sleep:
        return None
    try:
        wh, wm = map(int, wake.split(":"))
        sh, sm = map(int, sleep.split(":"))
        minutes = (wh * 60 + wm) - (sh * 60 + sm)
        if minutes < 0:
            minutes += 24 * 60
        if minutes == 0:
            return None
        return round(minutes / 60, 2)
    except Exception:
        return None


# ------------------------------------------------------------------ food
def _grams_near(line: str, idx: int, alias_len: int) -> Optional[float]:
    tail = line[idx + alias_len: idx + alias_len + 34]
    m = GRAMS_RE.search(tail)
    if m:
        return _num(m.group(1))
    m = NUM_AFTER_RE.match(tail)
    if m:
        val = _num(m.group(1))
        if 5 <= val <= 2000:
            return val
    return None


def extract_foods(line: str) -> list[dict]:
    low = line.lower()
    found = []
    used = set()
    consumed: list[tuple[int, int]] = []
    for _, rx, product in _load_foods():
        if product["name"] in used:
            continue
        m = rx.search(low)
        if not m:
            continue
        s, e = m.start(), m.end()
        if any(not (e <= cs or s >= ce) for cs, ce in consumed):
            continue
        grams = _grams_near(line, s, e - s)
        if product["name"] == "яйцо":
            grams = _egg_grams(low, grams)
        if grams is None:
            grams = product.get("default_grams", 100)
        found.append({
            "food_name": product["name"],
            "amount_grams": round(grams, 1),
            "protein_g": round(product.get("protein_per_100g", 0) * grams / 100, 1),
            "alcohol": bool(product.get("alcohol")),
        })
        used.add(product["name"])
        consumed.append((s, e))
    return found


def _egg_grams(low: str, grams: Optional[float]) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:шт|яйц|яйца|яиц)", low)
    if m:
        try:
            return _num(m.group(1)) * 60
        except Exception:
            pass
    for word, n in _NUM_WORDS.items():
        if re.search(rf"\b{word}\b", low):
            return n * 60
    if grams:
        return grams
    return 60


# ------------------------------------------------------------------ detectors
def detect_day_header(text: str):
    m = DAY_HEADER_RE.match(text)
    if not m:
        return None
    day, month = int(m.group(2)), int(m.group(3))
    year = int(m.group(4)) if m.group(4) else None
    if year and year < 100:
        year += 2000
    return {"day": day, "month": month, "year": year}


def detect_sleep_quality(low: str):
    if "сон" in low or low.strip().endswith("/10") or "/10" in low:
        m = QUALITY_RE.search(low)
        if m:
            q = int(m.group(1))
            if 1 <= q <= 10:
                return q
    return None


def detect_weight(low: str):
    m = re.search(r"вес\s*:?\s*(\d{2,3}(?:[.,]\d{1,2})?)", low)
    if m:
        return _num(m.group(1))
    m = BARE_DECIMAL_RE.match(low)
    if m:
        val = _num(f"{m.group(1)}.{m.group(2)}")
        if 30 <= val <= 300:
            return val
    return None


def detect_steps(low: str):
    if "шаг" not in low:
        return None
    m = re.search(r"шаг\w*\D{0,12}?(\d+)\s*(тыс|к|k|к\.)?", low)
    if not m:
        return None
    val = int(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit.startswith("тыс") or unit in ("к", "k"):
        val *= 1000
    elif val < 500:
        val *= 1000
    return val


def _detect_supplements(low: str) -> list[str]:
    out = []
    for s in known_supplements():
        if s in low and s not in out:
            out.append(s)
    # слитые названия приводим к одному каноническому
    for alias, canon in _SUPPLEMENT_MERGE.items():
        if alias in low and canon not in out:
            out.append(canon)
    return out


def _looks_like_hang(low: str) -> bool:
    if "гориз" in low:
        return False
    if "револьвер" in low and "мм" not in low:
        return False
    return bool(
        HOLD_MM_RE.search(low)
        or "10/50" in low
        or "фингер" in low
        or "пасс" in low
        or "пассик" in low
        or ("вис" in low and ("кг" in low or "мин" in low or "сек" in low))
    )


def _detect_climbing(low: str) -> bool:
    if GRADE_RE.search(normalize_grades(low)):
        return True
    return any(k in low for k in ["флеш", "перепролаз", "попытк", "трасс", "детский финал", "софт", "залез"])


def _detect_exercise(low: str) -> bool:
    if "креветка" in low and SETS_REPS_RE.search(low):
        return True
    if WEIGHT_X_RE.search(low) or _WEIGHT_STANDALONE_RE.match(low):
        return True
    return any(k in low for k in _EXERCISE_HINTS)


def _detect_lfk(low: str) -> bool:
    return any(k in low for k in _LFK_HINTS)


def _detect_pool(low: str) -> bool:
    return any(k in low for k in _POOL_HINTS)


# ------------------------------------------------------------------ main
def parse_line(text: str, has_wake: bool = False, has_sleep: bool = False) -> list[ParsedLine]:
    raw = text.strip()
    if not raw:
        return []
    low = raw.lower()

    # 1. заголовок дня
    header = detect_day_header(raw)
    if header:
        return [ParsedLine(DAY_HEADER, header, raw, "📅 Заголовок дня")]

    # 2. качество сна / настроение / энергия / пульс / вода
    m = QUALITY_RE.search(low)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 10:
            if "настроени" in low:
                return [ParsedLine(MOOD, {"mood": val}, raw, f"🙂 Настроение {val}/10")]
            if "энерг" in low or "самочувств" in low or "бодрост" in low:
                return [ParsedLine(ENERGY, {"energy": val}, raw, f"⚡ Самочувствие {val}/10")]
            if "сон" in low or "/10" in low:
                return [ParsedLine(SLEEP_QUALITY, {"sleep_quality": val}, raw, f"😴 Качество сна {val}/10")]

    m = re.search(r"пульс\s*(?:покоя)?\s*:?\s*(\d{2,3})", low)
    if m:
        return [ParsedLine(PULSE, {"resting_hr": int(m.group(1))}, raw, f"❤️ Пульс покоя {m.group(1)}")]

    m = re.search(r"вода\s*:?\s*(\d+(?:[.,]\d+)?)\s*(л|l)?", low)
    if m:
        return [ParsedLine(WATER, {"water_l": _num(m.group(1))}, raw, f"💧 Вода {m.group(1)} л")]

    # 3. время пробуждения / засыпания
    explicit_wake = re.search(r"(?:пробужд|подъ[её]м|встал|встаю)", low)
    if explicit_wake:
        t = _parse_time_in(low)
        if t:
            return [ParsedLine(WAKE, {"wake_time": t}, raw, f"⏰ Пробуждение {t}")]

    explicit_sleep = re.search(r"(?:засыпан|отбой|заснул|лёг|лег спать|сон\s+в)", low)
    if explicit_sleep or (low.startswith("сон") and TIME_RE.search(low)):
        t = _parse_time_in(low)
        if t:
            return [ParsedLine(SLEEP_TIME, {"sleep_time": t}, raw, f"🌙 Засыпание {t}")]

    if BARE_TIME_RE.match(low):
        t = _parse_time_in(low)
        if has_wake and not has_sleep:
            return [ParsedLine(SLEEP_TIME, {"sleep_time": t}, raw, f"🌙 Засыпание {t}")]
        return [ParsedLine(WAKE, {"wake_time": t}, raw, f"⏰ Пробуждение {t}")]

    # 4. вес
    w = detect_weight(low)
    if w is not None:
        return [ParsedLine(WEIGHT, {"weight": w}, raw, f"⚖️ Вес {w} кг")]

    # 5. шаги
    s = detect_steps(low)
    if s is not None:
        return [ParsedLine(STEPS, {"steps": s}, raw, f"👟 Шаги {s}")]

    # 6. добавки/рутины (могут идти вместе с едой)
    results: list[ParsedLine] = []
    supplements = _detect_supplements(low)
    if supplements:
        for sup in supplements:
            results.append(ParsedLine(SUPPLEMENT, {"name": sup}, raw, f"✅ {sup}"))
        # если в строке ещё и еда с граммами — добавим
        foods = extract_foods(raw)
        if foods and GRAMS_RE.search(raw):
            for f in foods:
                results.append(_meal_line(f, raw))
        if results:
            return results

    # 7. бассейн (объединяем с тренировками)
    if _detect_pool(low):
        dur = DURATION_MIN_RE.search(low)
        minutes = int(dur.group(1)) if dur else None
        if re.search(r"час", low) and not minutes:
            minutes = 60
        name = "Бассейн" + (f" {minutes}мин" if minutes else "")
        return [ParsedLine(EXERCISE, {"name": name, "detail": raw}, raw, f"🏊 {name}")]

    # 8. висы
    if _looks_like_hang(low):
        return [_hang_line(low, raw)]

    # 9. лазание
    if _detect_climbing(low):
        return _climb_lines(low, raw)

    # 10. упражнения
    if _detect_lfk(low):
        return [_lfk_line(raw)]

    # 10b. упражнения
    if _detect_exercise(low):
        return [_exercise_line(low, raw)]

    # 11. еда
    foods = extract_foods(raw)
    if foods:
        return [_meal_line(f, raw) for f in foods]

    # 12. всё остальное — заметка
    return [ParsedLine(NOTE, {"text": raw}, raw, f"📝 {raw}")]


def _meal_line(food: dict, raw: str) -> ParsedLine:
    return ParsedLine(
        MEAL,
        {"food_name": food["food_name"], "amount_grams": food["amount_grams"],
         "protein_g": food["protein_g"], "alcohol": food.get("alcohol", False)},
        raw,
        f"🍽 {food['food_name']} {food['amount_grams']:g}г (+{food['protein_g']:g}г белка)",
    )


def _hang_line(low: str, raw: str) -> ParsedLine:
    holds = HOLD_MM_RE.findall(low)
    hold = "/".join(f"{h}мм" for h in holds) if holds else None
    weight = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", low)
    if m:
        weight = _num(m.group(1))
    proto = PROTOCOL_RE.search(low)
    protocol = f"{proto.group(1)}/{proto.group(2)}" if proto else None
    dur_min = DURATION_MIN_RE.search(low)
    total_min = int(dur_min.group(1)) if dur_min else None
    if not total_min and re.search(r"час", low):
        total_min = 60
    parts = ["🤸 Вис"]
    if hold:
        parts.append(hold)
    if weight:
        parts.append(f"+{weight:g}кг")
    if total_min:
        parts.append(f"{total_min}мин")
    if protocol:
        parts.append(protocol)
    return ParsedLine(HANG, {
        "hold_size": hold, "added_weight": weight, "total_time_min": total_min,
        "protocol": protocol, "detail": raw,
    }, raw, " ".join(parts))


def _climb_lines(low: str, raw: str) -> list[ParsedLine]:
    """Строка может содержать несколько трасс: '5 6а, 4 6б, 6с флеш'."""
    segments = re.split(r"[,;]", low)
    out: list[ParsedLine] = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        norm = normalize_grades(seg)
        matches = list(GRADE_COUNT_RE.finditer(norm))
        if matches:
            for m in matches:
                count = int(m.group(1)) if m.group(1) else None
                grade = f"{m.group(2)}{m.group(3)}"
                out.append(_climb_item(grade, count, seg, raw))
        elif any(k in seg for k in ["финал", "трасс", "залез", "перепролаз"]):
            out.append(_climb_item(None, None, seg, raw))
    if not out:
        out.append(_climb_item(None, None, low, raw))
    return out


def _climb_item(grade: str, count: int | None, seg: str, raw: str) -> ParsedLine:
    kind = "attempts"
    if "флеш" in seg:
        kind = "flash"
    elif "не залез" in seg or "не пролез" in seg or "не вышел" in seg or "неудач" in seg:
        kind = "fail"
    elif "перепролаз" in seg or "залез" in seg or "софт" in seg:
        kind = "send"
    attempts = None
    m = re.search(r"(\d+)\s*попыт", seg)
    if m:
        attempts = int(m.group(1))
    if count is None:
        m2 = re.search(r"(\d+)\s*(?:шт|раз)", seg)
        if m2:
            count = int(m2.group(1))
    if count is None and attempts is None and kind == "attempts":
        count = 1
    sends = 1 if kind in ("send", "flash") else None
    label = grade or "трасса"
    suffix = f", {count}шт" if count and count != 1 else ""
    return ParsedLine(CLIMBING, {
        "grade": grade, "kind": kind, "attempts": attempts, "count": count,
        "sends": sends, "detail": raw,
    }, raw, f"🧗 {label} ({kind}{suffix})")


def _lfk_line(raw: str) -> ParsedLine:
    name = raw[:120]
    return ParsedLine(LFK, {"name": name}, raw, f"🤸‍♂️ ЛФК: {raw[:40]}")


def _exercise_line(low: str, raw: str) -> ParsedLine:
    name = raw
    # уберём числа для имени
    sets = reps = weight = None
    m = WEIGHT_X_RE.search(low)
    if m:
        weight = _num(m.group(1))
        reps = int(m.group(2))
    m = SETS_REPS_RE.search(low)
    if m and weight is None:
        sets = int(m.group(1))
        reps = int(m.group(2))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", low)
    if m and weight is None:
        weight = _num(m.group(1))
    volume = None
    if sets and reps and weight:
        volume = round(sets * reps * weight, 1)
    return ParsedLine(EXERCISE, {
        "name": name[:120], "sets": sets, "reps": reps, "weight": weight,
        "volume": volume, "detail": raw,
    }, raw, f"💪 {name[:40]}")


# ------------------------------------------------------------------ button helpers
# Используются кнопочным интерфейсом: строят ParsedLine из значений,
# введённых пользователем через кнопки/подсказки.

def parse_time_value(text: str) -> Optional[str]:
    return _parse_time_in(text.strip())


def parse_weight_value(text: str) -> Optional[float]:
    m = re.search(r"(\d{2,3}(?:[.,]\d{1,2})?)", text.strip())
    if not m:
        return None
    v = _num(m.group(1))
    return v if 30 <= v <= 300 else None


def parse_steps_value(text: str) -> Optional[int]:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(тыс|к|k)?", text.strip().lower())
    if not m:
        return None
    v = _num(m.group(1))
    unit = (m.group(2) or "")
    if unit.startswith("тыс") or unit in ("к", "k") or v < 500:
        v *= 1000
    return int(v)


def parse_quality_value(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,2})", text)
    if m:
        q = int(m.group(1))
        if 1 <= q <= 10:
            return q
    return None


def line_wake(t: str) -> ParsedLine:
    return ParsedLine(WAKE, {"wake_time": t}, t, f"⏰ Пробуждение {t}")


def line_sleep_time(t: str) -> ParsedLine:
    return ParsedLine(SLEEP_TIME, {"sleep_time": t}, t, f"🌙 Засыпание {t}")


def line_sleep_quality(q: int) -> ParsedLine:
    return ParsedLine(SLEEP_QUALITY, {"sleep_quality": q}, str(q), f"😴 Качество сна {q}/10")


def line_weight(w: float) -> ParsedLine:
    return ParsedLine(WEIGHT, {"weight": w}, str(w), f"⚖️ Вес {w} кг")


def line_steps(s: int) -> ParsedLine:
    return ParsedLine(STEPS, {"steps": s}, str(s), f"👟 Шаги {s}")


def line_exercise(raw: str) -> ParsedLine:
    raw = raw.strip()
    return _exercise_line(raw.lower(), raw)


def line_exercise_name(name: str) -> ParsedLine:
    return ParsedLine(EXERCISE, {"name": name, "detail": name}, name, f"💪 {name}")


def line_lfk(raw: str) -> ParsedLine:
    raw = raw.strip()
    return _lfk_line(raw)


def line_hang(hold: Optional[str], weight: Optional[float], raw: str) -> ParsedLine:
    parts = ["🤸 Вис"]
    if hold:
        parts.append(hold)
    if weight:
        parts.append(f"+{weight:g}кг")
    return ParsedLine(HANG, {
        "hold_size": hold, "added_weight": weight, "total_time_min": None,
        "protocol": None, "detail": raw,
    }, raw, " ".join(parts))


def line_climb(grade: Optional[str], count: Optional[int], attempts: Optional[int],
               kind: str, raw: str) -> ParsedLine:
    suffix = f", {count}шт" if count and count != 1 else ""
    return ParsedLine(CLIMBING, {
        "grade": grade, "kind": kind, "attempts": attempts, "count": count,
        "sends": 1 if kind in ("send", "flash") else None, "detail": raw,
    }, raw, f"🧗 {grade or 'трасса'} ({kind}{suffix})")


def line_climb_route(grade: str, attempts: int, sent: bool) -> ParsedLine:
    """Трасса, введённая кнопками: категория + число попыток + результат."""
    res = "залез" if sent else "не залез"
    raw = f"{grade} {attempts} попыт. — {res}"
    return ParsedLine(CLIMBING, {
        "grade": grade, "kind": "send" if sent else "fail",
        "attempts": attempts, "sends": 1 if sent else 0, "count": 1,
        "detail": raw,
    }, raw, f"🧗 {grade}: {attempts} попыт. — {res}")


def line_meal(food: dict, raw: str) -> ParsedLine:
    return _meal_line(food, raw)


def parse_food(raw: str) -> list[ParsedLine]:
    return [_meal_line(f, raw) for f in extract_foods(raw)]


def food_defaults(name: str) -> Optional[dict]:
    for _, _, product in _load_foods():
        if product["name"].lower() == name.lower():
            return product
    return None


def line_quick_food(name: str) -> Optional[ParsedLine]:
    product = food_defaults(name)
    if not product:
        return None
    grams = float(product.get("default_grams", 100))
    food = {
        "food_name": product["name"],
        "amount_grams": grams,
        "protein_g": round(product.get("protein_per_100g", 0) * grams / 100, 1),
        "alcohol": bool(product.get("alcohol")),
    }
    return _meal_line(food, product["name"])


def config_supplements() -> list[str]:
    return list(_load_routines().get("supplements", []))


def config_routines() -> list[str]:
    return list(_load_routines().get("routines", []))
