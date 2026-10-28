# Быстрый старт

## 1. Получить токен
У @BotFather: /newbot -> получить BOT_TOKEN

## 2. Настроить .env
```bash
cp .env.example .env
nano .env
```

Заполнить BOT_TOKEN минимум.

## 3. Запустить бота
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 4. Настроить чаты
1. Написать боту в ЛС `/get_chat_info` -> скопировать ID
2. Создать группу/форум для отчетов, добавить бота, в нужных топиках писать `/get_chat_info`
3. Обновить .env всеми ID

## Команды бота
- `/start` - начало
- `/add` - добавить данные за день
- `/view` - посмотреть данные
- `/stats` - статистика и графики
- `/get_chat_info` - инфо о чате/топике

Готово!
