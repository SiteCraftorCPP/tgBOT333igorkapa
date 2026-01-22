#!/bin/bash

# Скрипт для деплоя бота на VPS
# Использование: ./deploy_vps.sh

echo "🚀 Деплой бота на VPS..."

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env на основе .env.example"
    exit 1
fi

# Установка зависимостей
echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt

# Инициализация БД
echo "🗄️ Инициализация базы данных..."
python3 -c "import database; database.init_db()"

# Проверка конфигурации
echo "🔍 Проверка конфигурации..."
python3 -c "import config; config.validate_config()"

# Создание systemd сервисов
echo "⚙️ Настройка systemd сервисов..."

# Получаем текущую директорию
CURRENT_DIR=$(pwd)
USER=$(whoami)

# Создаём сервис для бота
sudo tee /etc/systemd/system/enguerrados-bot.service > /dev/null <<EOF
[Unit]
Description=ENGUERRADOS Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Создаём сервис для автопроверки
sudo tee /etc/systemd/system/enguerrados-autocheck.service > /dev/null <<EOF
[Unit]
Description=ENGUERRADOS Auto Check
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/auto_check.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Создаём сервис для webhook сервера (если используется)
sudo tee /etc/systemd/system/enguerrados-webhook.service > /dev/null <<EOF
[Unit]
Description=ENGUERRADOS Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable enguerrados-bot.service
sudo systemctl enable enguerrados-autocheck.service
# sudo systemctl enable enguerrados-webhook.service  # Раскомментируй если нужен webhook

# Запускаем сервисы
sudo systemctl start enguerrados-bot.service
sudo systemctl start enguerrados-autocheck.service
# sudo systemctl start enguerrados-webhook.service  # Раскомментируй если нужен webhook

echo "✅ Деплой завершён!"
echo ""
echo "📋 Управление сервисами:"
echo "  sudo systemctl status enguerrados-bot      # Статус бота"
echo "  sudo systemctl restart enguerrados-bot     # Перезапуск бота"
echo "  sudo systemctl stop enguerrados-bot        # Остановка бота"
echo "  sudo journalctl -u enguerrados-bot -f      # Логи бота"
echo ""
echo "  sudo systemctl status enguerrados-autocheck      # Статус автопроверки"
echo "  sudo systemctl restart enguerrados-autocheck     # Перезапуск автопроверки"
echo ""
