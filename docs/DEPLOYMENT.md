# Инструкция по деплою и запуску

## Подготовка

1. Получить токен бота у @BotFather в Telegram
2. Создать бота и получить токен
3. Настроить бота как форум/группу если нужно (для топиков)

## Локальный запуск

```bash
# Клонировать репозиторий
git clone <repo_url>
cd diary_2

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Настроить .env
cp .env.example .env
nano .env  # заполнить токен и ID чатов

# Запустить бота
python run.py
```

## Настройка чатов и топиков

1. Добавить бота в личный чат и в отчетный чат (форум)
2. В личном чате написать `/get_chat_info` - получить MAIN_CHAT_ID
3. В отчетном чате (форуме) написать `/get_chat_info` - получить REPORT_CHAT_ID
4. Перейти в нужный топик форума и написать `/get_chat_info` - получить ID топика
5. Добавить все полученные ID в `.env`

## Запуск через Docker

```bash
# Собрать и запустить
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Перезапуск после обновления
docker-compose up -d --build
```

## Запуск через systemctl на VPS

1. Скопировать проект на сервер, например в `/opt/sports-diary/`

```bash
sudo mkdir -p /opt/sports-diary
sudo cp -r . /opt/sports-diary/
cd /opt/sports-diary
```

2. Настроить виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

3. Создать systemd unit файл

```bash
sudo nano /etc/systemd/system/sports-diary.service
```

Содержимое:
```ini
[Unit]
Description=Sports Diary Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/sports-diary
Environment=PATH=/opt/sports-diary/venv/bin
ExecStart=/opt/sports-diary/venv/bin/python /opt/sports-diary/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. Запустить сервис

```bash
sudo systemctl daemon-reload
sudo systemctl enable sports-diary
sudo systemctl start sports-diary

# Проверить статус
sudo systemctl status sports-diary

# Логи
journalctl -u sports-diary -f
```

## Обновление бота

### Через Docker
```bash
git pull
docker-compose up -d --build
```

### Через systemctl
```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sports-diary
```

## База данных

База данных SQLite хранится в `./data/diary.db`. При использовании Docker она монтируется как volume, поэтому данные сохраняются между перезапусками.

Для бэкапа:
```bash
cp data/diary.db data/diary.db.backup_$(date +%Y%m%d)
```
