import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
from config import PROTEIN_TARGET_G

class Charts:
    def __init__(self, out_dir='assets'):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def plot_weight(self, entries_days, user_id):
        dates = []
        weights = []
        for e in entries_days:
            if e.get('morning_weight'):
                dates.append(datetime.strptime(e['entry_date'], '%Y-%m-%d'))
                weights.append(float(e['morning_weight']))
        if not dates:
            return None
        plt.figure(figsize=(8,4))
        plt.plot(dates, weights, marker='o')
        plt.title('Morning weight')
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        plt.tight_layout()
        path = os.path.join(self.out_dir, f'weight_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.png')
        plt.savefig(path)
        plt.close()
        return path

    def plot_protein(self, meals_by_date, target=PROTEIN_TARGET_G, user_id=0):
        if not meals_by_date:
            return None
        dates = []
        vals = []
        for d in sorted(meals_by_date.keys()):
            dates.append(datetime.strptime(d, '%Y-%m-%d'))
            s = sum(x.get('protein_g', 0) for x in meals_by_date[d])
            vals.append(s)
        if not dates:
            return None
        plt.figure(figsize=(8,4))
        colors = ['green' if v >= target else 'orange' for v in vals]
        plt.bar(dates, vals, color=colors, alpha=0.7)
        plt.axhline(y=target, color='red', linestyle='--', label=f'Цель {target}г')
        plt.title('Белок по дням')
        plt.ylabel('г')
        plt.legend()
        plt.grid(True, axis='y', alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        plt.tight_layout()
        path = os.path.join(self.out_dir, f'protein_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.png')
        plt.savefig(path)
        plt.close()
        return path

charts = Charts()
