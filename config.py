import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "")
DB_PATH = os.getenv("DB_PATH", "/data/diary.db")

TOPIC_SUMMARY_ID = os.getenv("TOPIC_SUMMARY_ID") or None
TOPIC_SLEEP_ID = os.getenv("TOPIC_SLEEP_ID") or None
TOPIC_WEIGHT_ID = os.getenv("TOPIC_WEIGHT_ID") or None
TOPIC_TRAINING_ID = os.getenv("TOPIC_TRAINING_ID") or None
TOPIC_CLIMBING_ID = os.getenv("TOPIC_CLIMBING_ID") or None
TOPIC_HANGBOARD_ID = os.getenv("TOPIC_HANGBOARD_ID") or None
TOPIC_NUTRITION_ID = os.getenv("TOPIC_NUTRITION_ID") or None
TOPIC_ROUTINES_ID = os.getenv("TOPIC_ROUTINES_ID") or None

PROTEIN_TARGET_G = float(os.getenv("PROTEIN_TARGET_G", "150"))

# Конфиг продуктов и белка на 100 г
PROTEIN_TABLE = {
    "курица": 23.0,
    "индейка": 21.0,
    "говядина": 18.0,
    "свинина": 16.0,
    "рыба": 20.0,
    "лосось": 20.0,
    "тунец": 24.0,
    "яйцо": 12.7,
    "яйца": 12.7,
    "творог": 18.0,
    "сыр": 25.0,
    "молоко": 3.2,
    "кефир": 3.0,
    "йогурт": 5.0,
    "гречка": 12.6,
    "рис": 7.0,
    "овсянка": 12.3,
    "картофель": 2.0,
    "макароны": 10.4,
    "хлеб": 8.0,
    "орехи": 20.0,
    "миндаль": 21.0,
    "фасоль": 21.0,
    "чечевица": 24.0,
    "горох": 23.0,
    "тофу": 12.0,
    "протеин": 80.0,
    "протеиновый коктейль": 25.0,
}
