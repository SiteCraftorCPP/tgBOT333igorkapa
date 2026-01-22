# 🤖 ENGUERRADOS Telegram Bot

Телеграм-бот для продажи подписок на закрытый канал через Stripe.

## 📋 Возможности

- ✅ Приём платежей через Stripe
- ✅ Автоматическое добавление пользователей в канал
- ✅ Автоматическое удаление при окончании подписки
- ✅ Уведомления админам об истекающих подписках
- ✅ Админ-панель для управления подписками
- ✅ Персональные инвайт-ссылки (1 человек, 24 часа)

## 🚀 Быстрый старт на VPS

### 1. Клонирование репозитория

```bash
git clone https://github.com/SiteCraftorCPP/tgBOT333igorkapa.git
cd tgBOT333igorkapa
```

### 2. Создание .env файла

```bash
nano .env
```

Вставьте конфигурацию (см. раздел "Конфигурация .env" ниже).

### 3. Установка и запуск

```bash
chmod +x deploy_vps.sh
./deploy_vps.sh
```

### 4. Проверка статуса

```bash
sudo systemctl status enguerrados-bot
sudo journalctl -u enguerrados-bot -f
```

## ⚙️ Конфигурация .env

**НЕ ПУБЛИКУЙТЕ ЭТОТ ФАЙЛ В GIT!**

Создайте файл `.env` в корне проекта:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here
ADMIN_IDS=admin_id_1,admin_id_2

# Stripe Configuration
STRIPE_API_KEY=your_stripe_api_key_here
STRIPE_WEBHOOK_SECRET=your_webhook_secret_here

# Server Configuration
WEBHOOK_URL=http://localhost:8080/webhook
PORT=8080
```

## 📦 Требования

- Python 3.8+
- pip
- systemd (для автозапуска на VPS)

## 🔧 Управление сервисами

```bash
# Бот
sudo systemctl status enguerrados-bot
sudo systemctl restart enguerrados-bot
sudo systemctl stop enguerrados-bot
sudo journalctl -u enguerrados-bot -f

# Автопроверка
sudo systemctl status enguerrados-autocheck
sudo systemctl restart enguerrados-autocheck
sudo journalctl -u enguerrados-autocheck -f
```

## 📝 Структура проекта

```
├── bot.py                    # Основной бот
├── webhook_server.py         # Webhook сервер для Stripe
├── check_subscriptions.py    # Проверка истёкших подписок
├── notify_expiring.py        # Уведомления об истекающих подписках
├── auto_check.py            # Авто-проверка каждые 30 сек
├── database.py              # Работа с БД
├── config.py                # Конфигурация
├── stripe_integration.py    # Интеграция со Stripe
├── deploy_vps.sh            # Скрипт деплоя на VPS
└── requirements.txt         # Зависимости
```

## 🔐 Безопасность

- ✅ `.env` файл в `.gitignore`
- ✅ Используется Stripe Restricted API Key
- ✅ База данных не публикуется в Git
- ✅ Персональные инвайт-ссылки

## 📊 Тарифы

- 1 месяц — 4.99 EUR
- 6 месяцев — 24.99 EUR
- 12 месяцев — 44.99 EUR

## 🆘 Поддержка

Для вопросов и помощи обращайтесь к администраторам.

## 📄 Лицензия

Private project.
