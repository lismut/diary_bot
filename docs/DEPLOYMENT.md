# Деплой и запуск

## 1. Получить токен бота

У [@BotFather](https://t.me/BotFather): `/newbot` → скопировать `BOT_TOKEN`.

## 2. Настроить .env

```bash
cp .env.example .env
nano .env
```

Минимум — `BOT_TOKEN`. Остальные ID узнаются в п.4.

## 3. Запуск локально (для проверки)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 4. Узнать ID чатов и топиков

1. Напиши боту в личку `/get_chat_info` → получишь `MAIN_CHAT_ID`.
2. Создай группу, включи в ней **темы (Topics)** — это будет отчётный чат.
3. Добавь бота в группу, дай права администратора.
4. Напиши `/get_chat_info` в группе → получишь `REPORT_CHAT_ID`.
5. Открой нужную тему и напиши там `/get_chat_info` → получишь `thread_id` этой темы.
6. Впиши полученные ID в `.env`:

```
MAIN_CHAT_ID=-1001234567890
REPORT_CHAT_ID=-1009876543210
TOPIC_DIARY_ID=2
TOPIC_SLEEP_ID=3
TOPIC_WEIGHT_ID=4
TOPIC_TRAINING_ID=5
TOPIC_CLIMBING_ID=6
TOPIC_HANGS_ID=7
TOPIC_STEPS_ID=8
TOPIC_NUTRITION_ID=9
TOPIC_ROUTINES_ID=10
TOPIC_ANALYTICS_ID=11
```

Если какой-то топик не задан — соответствующие данные просто не постятся.

## 5. Импорт старого дневника

```bash
python scripts/import_diary.py diary --reset
```

Файл `diary` — твой дневник в формате заметок. Скрипт сам разберёт дни
(заголовки вида `Сб 11.10`), строки, еду, тренировки, лазание, висы и т.д.

Опции:
- `--reset` — очистить базу перед импортом;
- `--dry-run` — показать разбор без сохранения;
- `--year 2025` — год для дат без года (по умолчанию текущий).

## 5.1. Разовая выгрузка истории в отчётный чат

При первом запуске бот один раз выгружает всю загруженную историю в отчётный
чат: по каждому прошлому дню данные уходят последовательно и раскладываются
по темам (топикам), в конце — общая аналитика за всё время.

Прогресс сохраняется в базе (настройка `history_last_date`), поэтому
перезапуск/обновление бота **не приводит к повторной отправке** уже выгруженных
дней. Сегодняшний день в выгрузку истории не попадает — он уходит штатно.

Убедись, что перед первым запуском заданы `REPORT_CHAT_ID` и нужные
`TOPIC_*_ID` (см. п.4), иначе выгрузка не состоится.

## 6. Как пользоваться

Основной интерфейс — кнопочное меню внизу: 😴 Сон · ⚖️ Вес · 💪 Тренировка ·
🧗 Лазание · 🤸 Висы · 🍽 Питание · 💊 Добавки · 👟 Шаги · 📋 Сводка дня ·
📊 Статистика · 📤 В отчёт · 📅 День.

Каждый ввод сохраняется за активный день и сразу уходит в отчётный чат.
Свободный ввод строками остаётся как запасной вариант (см. `/help`).

---

## Запуск через Docker

```bash
docker compose up -d --build      # собрать и запустить
docker compose logs -f            # логи
docker compose restart            # перезапуск
docker compose down               # остановить
```

База (`./data`) и настройки (`./config`) смонтированы как тома — данные
сохраняются между перезапусками и обновлениями кода.

Импорт дневника внутри контейнера:

```bash
docker compose run --rm bot python scripts/import_diary.py diary --reset
```

Обновление:

```bash
git pull
docker compose up -d --build
```

---

## Запуск на VPS через systemd

1. Скопировать проект на сервер:

```bash
sudo mkdir -p /opt/sports-diary
sudo cp -r . /opt/sports-diary/
cd /opt/sports-diary
```

2. Виртуальное окружение и зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
```

3. Установить сервис (готовый unit лежит в `deploy/sports-diary.service`):

```bash
sudo cp deploy/sports-diary.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sports-diary
```

Либо автоматически (скрипт подставит путь и пользователя):

```bash
sudo bash scripts/install_service.sh
```

4. Проверка:

```bash
systemctl status sports-diary
journalctl -u sports-diary -f
```

Обновление:

```bash
cd /opt/sports-diary
git pull
source venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart sports-diary
```

---

## Резервные копии

SQLite-база лежит в `./data/diary.db`. Бэкап:

```bash
cp data/diary.db "backups/diary_$(date +%Y%m%d).db"
```

## PostgreSQL (опционально)

Замени `DATABASE_URL` в `.env`:

```
DATABASE_URL=postgresql+asyncpg://diary:password@host:5432/diary
```

и перезапусти сервис. Схема создастся автоматически.

## Настройка продуктов и рутин

- `config/foods.json` — продукты и содержание белка на 100 г (`protein_per_100g`),
  алиасы и порция по умолчанию (`default_grams`).
- `config/routines.json` — списки добавок и рутин.
- Норма белка — переменная `PROTEIN_NORM_PER_DAY`.

После правки файлов перезапусти бота (в Docker конфиг смонтирован, но
перезапуск нужен, чтобы перечитать).
