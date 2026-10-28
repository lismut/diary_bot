#!/bin/bash

PROJECT_DIR="/opt/sports-diary"
SERVICE_NAME="sports-diary"

echo "Установка Sports Diary Bot..."
sudo mkdir -p $PROJECT_DIR
sudo cp -r . $PROJECT_DIR/ 2>/dev/null || true
sudo chown -R $USER:$USER $PROJECT_DIR

cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан .env файл. Не забудь его настроить!"
fi

SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Sports Diary Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo cp /tmp/${SERVICE_NAME}.service $SERVICE_FILE

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo "Готово! Статус:"
sudo systemctl status $SERVICE_NAME --no-pager
