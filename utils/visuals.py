import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os

class Visualizer:
    def __init__(self, out_dir='assets'):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
    
    def plot_mood(self, entries, user_id):
        if not entries:
            return None
        dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries if e['mood'] is not None]
        moods = [e['mood'] for e in entries if e['mood'] is not None]
        if not dates:
            return None
        plt.figure(figsize=(8, 4))
        plt.plot(dates, moods, marker='o', linestyle='-', color='#4a90e2')
        plt.title('Mood over time')
        plt.xlabel('Date')
        plt.ylabel('Mood (1-10)')
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        path = os.path.join(self.out_dir, f'mood_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.png')
        plt.savefig(path)
        plt.close()
        return path
    
    def plot_sleep_energy(self, entries, user_id):
        if not entries:
            return None
        dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries 
                 if e['sleep_hours'] is not None or e['energy'] is not None]
        sleep = [e['sleep_hours'] if e['sleep_hours'] is not None else None for e in entries 
                 if e['sleep_hours'] is not None or e['energy'] is not None]
        energy = [e['energy'] if e['energy'] is not None else None for e in entries 
                  if e['sleep_hours'] is not None or e['energy'] is not None]
        if not dates:
            return None
        fig, ax1 = plt.subplots(figsize=(8, 4))
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Sleep (hours)', color='tab:blue')
        ax1.plot(dates, sleep, marker='s', color='tab:blue', label='Sleep')
        ax1.tick_params(axis='y', labelcolor='tab:blue')
        ax2 = ax1.twinx()
        ax2.set_ylabel('Energy (1-10)', color='tab:orange')
        ax2.plot(dates, energy, marker='^', color='tab:orange', label='Energy')
        ax2.tick_params(axis='y', labelcolor='tab:orange')
        plt.title('Sleep and Energy')
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        fig.tight_layout()
        path = os.path.join(self.out_dir, f'sleep_energy_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.png')
        plt.savefig(path)
        plt.close()
        return path

visualizer = Visualizer()
