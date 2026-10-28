import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
from datetime import date, timedelta
from typing import List
import numpy as np

from src.db import models


class ChartService:
    @staticmethod
    def plot_weight(days: List[models.DayRecord]):
        dates = []
        weights = []
        for d in sorted(days, key=lambda x: x.date):
            if d.weight is not None:
                dates.append(d.date)
                weights.append(d.weight)
        
        if not weights:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, weights, marker='o', linewidth=2, markersize=6)
        ax.set_title('Динамика веса', fontsize=14, fontweight='bold')
        ax.set_xlabel('Дата')
        ax.set_ylabel('Вес, кг')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
    
    @staticmethod
    def plot_sleep(days: List[models.DayRecord]):
        dates = []
        hours = []
        for d in sorted(days, key=lambda x: x.date):
            if d.sleep_hours is not None:
                dates.append(d.date)
                hours.append(d.sleep_hours)
        
        if not hours:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, hours, marker='s', linewidth=2, markersize=6, color='purple')
        ax.set_title('Продолжительность сна', fontsize=14, fontweight='bold')
        ax.set_xlabel('Дата')
        ax.set_ylabel('Часы')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
    
    @staticmethod
    def plot_protein(days: List[models.DayRecord]):
        dates = []
        proteins = []
        for d in sorted(days, key=lambda x: x.date):
            total = sum(m.protein_g for m in d.meals) if d.meals else 0
            if total > 0 or len([x for x in days if x.meals]) > 0:
                dates.append(d.date)
                proteins.append(total)
        
        if not dates:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar(range(len(dates)), proteins, color=['green' if p >= 120 else 'yellow' for p in proteins])
        ax.set_title('Потребление белка по дням', fontsize=14, fontweight='bold')
        ax.set_xlabel('Дата')
        ax.set_ylabel('Белок, г')
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels([d.strftime('%d.%m') for d in dates], rotation=45)
        ax.axhline(y=120, color='red', linestyle='--', label='Норма 120г')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
    
    @staticmethod
    def plot_climbing_volume(days: List[models.DayRecord]):
        dates = []
        counts = []
        for d in sorted(days, key=lambda x: x.date):
            total = sum(r.attempts or 0 for r in d.climbing_routes) if d.climbing_routes else 0
            if total > 0 or d.climbing_routes:
                dates.append(d.date)
                counts.append(total)
        
        if not dates:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, counts, marker='^', linewidth=2, markersize=6, color='orange')
        ax.set_title('Объём лазания (попытки)', fontsize=14, fontweight='bold')
        ax.set_xlabel('Дата')
        ax.set_ylabel('Попыток')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
    
    @staticmethod
    def plot_steps(days: List[models.DayRecord]):
        dates = []
        steps_list = []
        for d in sorted(days, key=lambda x: x.date):
            if d.steps is not None:
                dates.append(d.date)
                steps_list.append(d.steps)
        
        if not steps_list:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, steps_list, color='teal')
        ax.set_title('Шаги за день', fontsize=14, fontweight='bold')
        ax.set_xlabel('Дата')
        ax.set_ylabel('Шагов')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()
        return buf
