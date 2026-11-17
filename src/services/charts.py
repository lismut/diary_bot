import io
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from src.config import settings
from src.db import models
from src.services import parser as P

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False

GREEN = "#2e9e4f"
YELLOW = "#e0b400"
RED = "#d64545"
BLUE = "#3b78c3"
ORANGE = "#e08a2b"
PURPLE = "#8a5cc3"


def _to_buf(fig: Figure) -> io.BytesIO:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=110)
    buf.seek(0)
    plt.close(fig)
    return buf


def _dates_labels(days: list[date], rotation: int = 45):
    return [d.strftime("%d.%m") for d in days]


def _route_sends(r) -> int:
    """Число пролазов трассы (учитывает старый формат, где sends — флаг)."""
    if r.sends is not None:
        return int(r.sends)
    return 1 if r.kind in ("send", "flash") else 0


class ChartService:

    @staticmethod
    def weight(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        ds = [(d.date, d.weight) for d in days if d.weight is not None]
        if not ds:
            return None
        dates, vals = zip(*ds)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, vals, marker="o", linewidth=2, color=BLUE)
        ax.set_title("Динамика веса", fontweight="bold")
        ax.set_ylabel("кг")
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=45)
        if len(vals) > 1:
            ax.axhline(sum(vals) / len(vals), color="gray", ls="--", alpha=0.6, label="среднее")
            ax.legend()
        return _to_buf(fig)

    @staticmethod
    def sleep_hours(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        ds = [(d.date, d.sleep_hours) for d in days if d.sleep_hours is not None]
        if not ds:
            return None
        dates, vals = zip(*ds)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, vals, color=PURPLE)
        ax.axhline(7, color=RED, ls="--", alpha=0.7, label="норма 7ч")
        ax.set_title("Продолжительность сна", fontweight="bold")
        ax.set_ylabel("часы")
        ax.grid(True, alpha=0.3, axis="y")
        ax.tick_params(axis="x", rotation=45)
        ax.legend()
        return _to_buf(fig)

    @staticmethod
    def sleep_quality(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        ds = [(d.date, d.sleep_quality) for d in days if d.sleep_quality is not None]
        if not ds:
            return None
        dates, vals = zip(*ds)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, vals, marker="s", linewidth=2, color=PURPLE)
        ax.set_ylim(0, 10)
        ax.set_title("Качество сна", fontweight="bold")
        ax.set_ylabel("баллы (1-10)")
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=45)
        return _to_buf(fig)

    @staticmethod
    def protein(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        norm = settings.PROTEIN_NORM_PER_DAY
        ds = [(d.date, d.protein_total()) for d in days if d.meals]
        if not ds:
            return None
        dates, vals = zip(*ds)
        colors = [GREEN if v >= norm else YELLOW for v in vals]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, vals, color=colors)
        ax.axhline(norm, color=RED, ls="--", label=f"норма {norm}г")
        ax.set_title("Белок по дням", fontweight="bold")
        ax.set_ylabel("г")
        ax.grid(True, alpha=0.3, axis="y")
        ax.tick_params(axis="x", rotation=45)
        ax.legend()
        return _to_buf(fig)

    @staticmethod
    def steps(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        ds = [(d.date, d.steps) for d in days if d.steps is not None]
        if not ds:
            return None
        dates, vals = zip(*ds)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, vals, color="#2a9d8f")
        ax.set_title("Шаги по дням", fontweight="bold")
        ax.set_ylabel("шагов")
        ax.grid(True, alpha=0.3, axis="y")
        ax.tick_params(axis="x", rotation=45)
        return _to_buf(fig)

    @staticmethod
    def climbing(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        data = []
        for d in days:
            attempts = sum(r.attempts or 0 for r in d.climbing_routes)
            routes = sum(_route_sends(r) for r in d.climbing_routes)
            if d.climbing_routes:
                data.append((d.date, attempts, routes))
        if not data:
            return None
        dates = [x[0] for x in data]
        attempts = [x[1] for x in data]
        routes = [x[2] for x in data]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, attempts, color=ORANGE, label="попытки")
        ax.plot(dates, routes, marker="o", color=BLUE, label="пройдено трасс")
        ax.set_title("Объём лазания", fontweight="bold")
        ax.set_ylabel("количество")
        ax.grid(True, alpha=0.3, axis="y")
        ax.tick_params(axis="x", rotation=45)
        ax.legend()
        return _to_buf(fig)

    @staticmethod
    def climbing_distribution(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        """Распределение попыток и пролазов по категориям."""
        order = ["5", "6a", "6b", "6c", "7a", "7b", "7c", "8a"]
        attempts: dict[str, int] = {}
        sends: dict[str, int] = {}
        for d in days:
            for r in d.climbing_routes:
                g = (r.grade or "?").lower()
                attempts[g] = attempts.get(g, 0) + (r.attempts or 0)
                sends[g] = sends.get(g, 0) + _route_sends(r)
        if not attempts:
            return None
        grades = [g for g in order if g in attempts] + \
                 sorted(g for g in attempts if g not in order)
        xs = list(range(len(grades)))
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar([x - 0.2 for x in xs], [attempts[g] for g in grades],
               width=0.4, color=ORANGE, label="попытки")
        ax.bar([x + 0.2 for x in xs], [sends[g] for g in grades],
               width=0.4, color=GREEN, label="пролазы")
        ax.set_xticks(xs)
        ax.set_xticklabels(grades)
        ax.set_title("Распределение попыток и пролазов по категориям", fontweight="bold")
        ax.set_ylabel("количество")
        ax.grid(True, alpha=0.3, axis="y")
        ax.legend()
        return _to_buf(fig)

    @staticmethod
    def hangs(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        data = []
        for d in days:
            if not d.hangs:
                continue
            max_w = max((h.added_weight or 0) for h in d.hangs)
            minutes = sum(h.total_time_min or 0 for h in d.hangs)
            data.append((d.date, max_w, minutes))
        if not data:
            return None
        dates = [x[0] for x in data]
        weights = [x[1] for x in data]
        minutes = [x[2] for x in data]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, weights, marker="o", color=RED, label="макс. отягощение, кг")
        ax.set_ylabel("кг", color=RED)
        ax.tick_params(axis="y", labelcolor=RED)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=45)
        ax2 = ax.twinx()
        ax2.bar(dates, minutes, alpha=0.25, color=BLUE, label="время, мин")
        ax2.set_ylabel("мин", color=BLUE)
        ax2.tick_params(axis="y", labelcolor=BLUE)
        ax.set_title("Прогресс висов на зацепках", fontweight="bold")
        return _to_buf(fig)

    @staticmethod
    def routines(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        totals: dict[str, int] = {}
        counts: dict[str, int] = {}
        for d in days:
            for r in d.routines:
                if r.completed:
                    counts[r.routine_name] = counts.get(r.routine_name, 0) + 1
        n_days = len([d for d in days if d.routines]) or 1
        if not counts:
            return None
        names = sorted(counts.keys())
        pct = [100 * counts[n] / n_days for n in names]
        fig, ax = plt.subplots(figsize=(9, max(3, 0.5 * len(names) + 2)))
        ax.barh(names, pct, color=GREEN)
        ax.set_xlim(0, 100)
        ax.set_xlabel("% дней")
        ax.set_title("Регулярность добавок и рутин", fontweight="bold")
        ax.grid(True, alpha=0.3, axis="x")
        return _to_buf(fig)

    @staticmethod
    def lfk_regularity(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        """Регулярность упражнений ЛФК: % дней периода, когда упражнение делалось."""
        if not days:
            return None
        counts: dict[str, int] = {}
        for d in days:
            names = {
                P.lfk_exercise_name(ln.raw_text)
                for ln in (d.log_lines or [])
                if ln.category == P.LFK
            }
            for n in names:
                if n:
                    counts[n] = counts.get(n, 0) + 1
        if not counts:
            return None
        n_days = len(days)
        names = sorted(counts.keys(), key=lambda n: (-counts[n], n))
        pct = [100 * counts[n] / n_days for n in names]
        fig, ax = plt.subplots(figsize=(9, max(3, 0.5 * len(names) + 2)))
        ax.barh(names, pct, color=PURPLE)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("% дней")
        ax.set_title("Регулярность упражнений ЛФК", fontweight="bold")
        ax.grid(True, alpha=0.3, axis="x")
        return _to_buf(fig)

    @staticmethod
    def training_activity(days: list[models.DayRecord]) -> Optional[io.BytesIO]:
        if not days:
            return None
        dates, vals = [], []
        for d in days:
            active = bool(
                d.exercises or d.climbing_routes or d.hangs
                or any(ln.category == P.LFK for ln in (d.log_lines or []))
            )
            vals.append(1 if active else 0)
            dates.append(d.date)
        if not any(vals):
            return None
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.bar(dates, vals, color=[GREEN if v else "#dddddd" for v in vals])
        ax.set_yticks([])
        ax.set_title("Дни с тренировкой", fontweight="bold")
        ax.tick_params(axis="x", rotation=45)
        return _to_buf(fig)
