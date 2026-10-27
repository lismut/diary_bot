import sqlite3
import json
from datetime import datetime
from config import DB_PATH
import os

class DB:
    def __init__(self, path=DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        self.init()

    def conn(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def init(self):
        con = self.conn()
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS days(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            wake_time TEXT,
            sleep_time TEXT,
            sleep_quality INTEGER,
            morning_weight REAL,
            steps INTEGER,
            general_load INTEGER,
            notes TEXT,
            updated_at TEXT,
            UNIQUE(user_id, entry_date)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS exercises(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            name TEXT,
            sets_reps TEXT,
            weight_kg REAL,
            rpe INTEGER,
            notes TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS climbs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            route_name TEXT,
            grade TEXT,
            attempts INTEGER,
            sends INTEGER,
            flashes INTEGER,
            notes TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS hangboard(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            hold_size TEXT,
            hold_type TEXT,
            reps INTEGER,
            hang_sec INTEGER,
            added_weight_kg REAL,
            body_weight_kg REAL,
            notes TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS meals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            meal_time TEXT,
            description TEXT,
            protein_g REAL DEFAULT 0
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS routines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS routine_done(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            routine_id INTEGER NOT NULL,
            done INTEGER DEFAULT 0,
            UNIQUE(user_id, entry_date, routine_id)
        )''')
        con.commit()
        con.close()

    def upsert_day(self, user_id, entry_date, **kw):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT id FROM days WHERE user_id=? AND entry_date=?", (user_id, entry_date))
        row = cur.fetchone()
        data = dict(kw)
        data['updated_at'] = datetime.now().isoformat()
        if row:
            sets = ','.join([f"{k}=?" for k in data])
            vals = list(data.values()) + [user_id, entry_date]
            cur.execute(f"UPDATE days SET {sets} WHERE user_id=? AND entry_date=?", vals)
        else:
            cols = ['user_id', 'entry_date'] + list(data.keys())
            qmarks = ','.join(['?'] * len(cols))
            vals = [user_id, entry_date] + list(data.values())
            cur.execute(f"INSERT INTO days({','.join(cols)}) VALUES({qmarks})", vals)
        con.commit()
        con.close()

    def get_day(self, user_id, entry_date):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM days WHERE user_id=? AND entry_date=?", (user_id, entry_date))
        r = cur.fetchone()
        con.close()
        return dict(r) if r else None

    def get_days_range(self, user_id, from_d, to_d):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM days WHERE user_id=? AND entry_date BETWEEN ? AND ? ORDER BY entry_date ASC",
                    (user_id, from_d, to_d))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

    def add_meal(self, user_id, entry_date, meal_time, description, protein_g=0):
        con = self.conn()
        cur = con.cursor()
        cur.execute('''INSERT INTO meals(user_id, entry_date, meal_time, description, protein_g)
                       VALUES(?,?,?,?,?)''', (user_id, entry_date, meal_time, description, protein_g))
        con.commit()
        con.close()

    def get_meals(self, user_id, entry_date):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM meals WHERE user_id=? AND entry_date=? ORDER BY id", (user_id, entry_date))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

    def get_meals_range(self, user_id, from_d, to_d):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM meals WHERE user_id=? AND entry_date BETWEEN ? AND ? ORDER BY entry_date, id",
                    (user_id, from_d, to_d))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

    def add_exercise(self, user_id, entry_date, name, sets_reps, weight_kg=None, rpe=None, notes=None):
        con = self.conn()
        cur = con.cursor()
        cur.execute('''INSERT INTO exercises(user_id, entry_date, name, sets_reps, weight_kg, rpe, notes)
                       VALUES(?,?,?,?,?,?,?)''', (user_id, entry_date, name, sets_reps, weight_kg, rpe, notes))
        con.commit()
        con.close()

    def get_exercises(self, user_id, entry_date):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM exercises WHERE user_id=? AND entry_date=? ORDER BY id", (user_id, entry_date))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

    def add_climb(self, user_id, entry_date, route_name, grade, attempts=0, sends=0, flashes=0, notes=None):
        con = self.conn()
        cur = con.cursor()
        cur.execute('''INSERT INTO climbs(user_id, entry_date, route_name, grade, attempts, sends, flashes, notes)
                       VALUES(?,?,?,?,?,?,?,?)''', (user_id, entry_date, route_name, grade, attempts, sends, flashes, notes))
        con.commit()
        con.close()

    def get_climbs(self, user_id, entry_date):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM climbs WHERE user_id=? AND entry_date=? ORDER BY id", (user_id, entry_date))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

    def add_hang(self, user_id, entry_date, hold_size, hold_type, reps=None, hang_sec=None, added_weight_kg=None, body_weight_kg=None, notes=None):
        con = self.conn()
        cur = con.cursor()
        cur.execute('''INSERT INTO hangboard(user_id, entry_date, hold_size, hold_type, reps, hang_sec, added_weight_kg, body_weight_kg, notes)
                       VALUES(?,?,?,?,?,?,?,?,?)''', (user_id, entry_date, hold_size, hold_type, reps, hang_sec, added_weight_kg, body_weight_kg, notes))
        con.commit()
        con.close()

    def get_hangs(self, user_id, entry_date):
        con = self.conn()
        cur = con.cursor()
        cur.execute("SELECT * FROM hangboard WHERE user_id=? AND entry_date=? ORDER BY id", (user_id, entry_date))
        rs = cur.fetchall()
        con.close()
        return [dict(x) for x in rs]

db = DB()
