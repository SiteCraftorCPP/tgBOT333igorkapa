#!/bin/bash
# Скрипт для развёртывания redirect сервера как systemd service

set -e

echo "🚀 Установка redirect сервера..."

# Проверяем, что мы в правильной директории
if [ ! -f "redirect_server.py" ]; then
    echo "❌ Файл redirect_server.py не найден!"
    exit 1
fi

# Создаём systemd service для redirect сервера
sudo tee /etc/systemd/system/enguerrados-redirect.service > /dev/null <<EOF
[Unit]
Description=ENGUERRADOS Redirect Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 redirect_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service файл создан"

# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable enguerrados-redirect

# Запускаем сервис
sudo systemctl start enguerrados-redirect

echo "✅ Redirect сервер запущен!"

# Показываем статус
sudo systemctl status enguerrados-redirect --no-pager

echo ""
echo "📋 Полезные команды:"
echo "  sudo systemctl status enguerrados-redirect    - статус сервера"
echo "  sudo systemctl restart enguerrados-redirect   - перезапуск"
echo "  sudo systemctl stop enguerrados-redirect      - остановка"
echo "  sudo journalctl -u enguerrados-redirect -f    - логи в реальном времени"
echo ""
echo "🌐 Redirect сервер работает на порту 8001"
