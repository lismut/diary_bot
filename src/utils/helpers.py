from datetime import datetime, date, timedelta
import json
import os


def get_date_from_text(text: str) -> date:
    """Try to parse date from text"""
    text = text.strip().lower()
    today = date.today()
    
    if text in ['сегодня', 'today']:
        return today
    elif text in ['вчера', 'yesterday']:
        return today - timedelta(days=1)
    elif text in ['позавчера']:
        return today - timedelta(days=2)
    
    # Try formats like DD.MM.YYYY or DD.MM
    try:
        if '.' in text:
            parts = text.split('.')
            if len(parts) == 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                return date(year, month, day)
            elif len(parts) == 2:
                day, month = int(parts[0]), int(parts[1])
                return date(today.year, month, day)
    except:
        pass
    
    return today


def format_date_russian(d: date) -> str:
    months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
    return f"{d.day} {months[d.month-1]} {d.year}"


def load_foods_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'foods.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"products": {}}


def load_routines_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'routines.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"routines": []}


def calculate_protein(food_name: str, amount_grams: float) -> float:
    foods = load_foods_config()
    food_name_lower = food_name.lower()
    for product, data in foods.get('products', {}).items():
        if product.lower() in food_name_lower or food_name_lower in product.lower():
            return round((data['protein_per_100g'] * amount_grams) / 100, 2)
    # Default guess if not found
    return round(amount_grams * 0.1, 2)  # 10% default
