# -*- coding: utf-8 -*-
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from datetime import datetime, timedelta
import requests

import config
import database as db
from stripe_integration import create_checkout_session, get_price_info

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_main_keyboard(is_subscribed=False):
    """Клавиатура главного меню"""
    if is_subscribed:
        keyboard = [
            [KeyboardButton("📱 Получить ссылку")],
            [KeyboardButton("📋 Моя подписка")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🚀 Купить подписку")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_plans_keyboard():
    """Клавиатура выбора тарифа"""
    keyboard = [
        [KeyboardButton("📅 1 месяц - 4.99 EUR")],
        [KeyboardButton("📅 6 месяцев - 24.99 EUR (1 месяц в подарок)")],
        [KeyboardButton("📅 12 месяцев - 44.99 EUR (3 месяца в подарок)")],
        [KeyboardButton("« Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = [
        [KeyboardButton("💳 Активные подписки")],
        [KeyboardButton("« Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Сохраняем пользователя в БД
    db.add_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Проверяем активную подписку
    subscription = db.get_active_subscription(user.id)
    
    keyboard = get_main_keyboard(is_subscribed=bool(subscription))
    
    if subscription:
        expiry_date = datetime.fromisoformat(subscription['end_date']).strftime('%d.%m.%Y')
        message = f"{config.MESSAGES['welcome']}\n\n✅ Ваша подписка активна до {expiry_date}"
    else:
        message = config.MESSAGES['welcome']
    
    await update.message.reply_text(message, reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user = update.effective_user
    
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к админ-панели")
        return
    
    keyboard = get_admin_keyboard()
    await update.message.reply_text(config.MESSAGES['admin_menu'], reply_markup=keyboard)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок)"""
    text = update.message.text
    user = update.effective_user
    
    # Главное меню
    if text == "🚀 Купить подписку":
        await show_plans(update, context)
    
    elif text == "📱 Получить ссылку":
        await get_link(update, context)
    
    elif text == "📋 Моя подписка":
        await show_subscription(update, context)
    
    elif text == "« Назад" or text == "« Главное меню":
        await start_command(update, context)
    
    # Выбор тарифа
    elif "месяц" in text.lower() and "EUR" in text:
        await plan_selected(update, context, text)
    
    # Админ-панель
    elif text == "💳 Активные подписки":
        await admin_active_subscriptions(update, context)
    
    else:
        await update.message.reply_text("Выберите действие из меню ниже 👇")

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать тарифные планы"""
    keyboard = get_plans_keyboard()
    await update.message.reply_text(config.MESSAGES['choose_plan'], reply_markup=keyboard)

async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_text: str):
    """Обработка выбора тарифа"""
    user = update.effective_user
    
    # Определяем price_id по тексту (смотрим на начало строки, чтобы избежать ошибок с описанием)
    if plan_text.startswith("📅 1 месяц"):
        price_id = config.STRIPE_PRICES['1_month']
        plan = '1_month'
    elif plan_text.startswith("📅 6 месяцев"):
        price_id = config.STRIPE_PRICES['6_months']
        plan = '6_months'
    elif plan_text.startswith("📅 12 месяцев"):
        price_id = config.STRIPE_PRICES['12_months']
        plan = '12_months'
    else:
        await update.message.reply_text("❌ Неверный план")
        return
    
    try:
        # Создаём Checkout Session в Stripe
        session = create_checkout_session(
            price_id=price_id,
            customer_email=f"{user.id}@telegram.user",
            metadata={
                'telegram_id': user.id,
                'telegram_username': user.username or '',
                'plan': plan
            }
        )
        
        if session and 'url' in session:
            # Сохраняем информацию о начале платежа
            db.add_payment(
                telegram_id=user.id,
                stripe_payment_id='',
                stripe_checkout_session_id=session['id'],
                amount=session.get('amount_total', 0),
                currency=session.get('currency', 'eur'),
                status='pending'
            )
            
            message = """✅ Ссылка для оплаты создана!

Нажмите кнопку ниже для безопасной оплаты через Stripe.

После оплаты вы автоматически получите доступ к каналу.

👇 Нажмите для оплаты:"""
            
            # Инлайн кнопка для оплаты (используем короткую ссылку если доступна)
            payment_url = session.get('short_url', session['url'])
            inline_keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=payment_url)]
            ]
            inline_markup = InlineKeyboardMarkup(inline_keyboard)
            
            await update.message.reply_text(message, reply_markup=inline_markup)
        else:
            await update.message.reply_text("❌ Ошибка создания сессии оплаты. Попробуйте снова.")
    
    except Exception as e:
        logger.error(f"Ошибка создания Checkout Session: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ссылку на канал"""
    user = update.effective_user
    
    # Проверяем активную подписку
    subscription = db.get_active_subscription(user.id)
    
    if not subscription:
        message = "❌ У вас нет активной подписки.\n\nДля получения доступа купите подписку."
        keyboard = get_main_keyboard(is_subscribed=False)
        await update.message.reply_text(message, reply_markup=keyboard)
        return
    
    try:
        # Создаём одноразовую инвайт-ссылку
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=config.CHANNEL_ID,
            member_limit=1,
            name=f"User_{user.id}",
            expire_date=datetime.now() + timedelta(hours=24)
        )
        
        message = f"""✅ Ваша подписка активна!

Перейдите по ссылке для доступа к закрытому каналу:

{invite_link.invite_link}

Эта ссылка персональная и действительна только для вас."""
        
        keyboard = get_main_keyboard(is_subscribed=True)
        await update.message.reply_text(message, reply_markup=keyboard, disable_web_page_preview=True)
    
    except Exception as e:
        logger.error(f"Ошибка создания invite link: {e}")
        await update.message.reply_text(f"❌ Ошибка создания ссылки: {str(e)}")

async def show_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о подписке"""
    user = update.effective_user
    subscription = db.get_active_subscription(user.id)
    
    if not subscription:
        message = "❌ У вас нет активной подписки."
        keyboard = get_main_keyboard(is_subscribed=False)
    else:
        start_date = datetime.fromisoformat(subscription['start_date']).strftime('%d.%m.%Y')
        end_date = datetime.fromisoformat(subscription['end_date']).strftime('%d.%m.%Y')
        
        # Сколько дней осталось
        days_left = (datetime.fromisoformat(subscription['end_date']) - datetime.now()).days
        
        message = f"""📋 Ваша подписка

Статус: ✅ Активна
Начало: {start_date}
Действительна до: {end_date}
Осталось дней: {days_left}

Ваш доступ к закрытому каналу гарантирован до даты окончания."""
        
        keyboard = get_main_keyboard(is_subscribed=True)
    
    await update.message.reply_text(message, reply_markup=keyboard)

async def test_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовый доступ ТОЛЬКО ДЛЯ АДМИНОВ"""
    user = update.effective_user
    
    # Только для админов
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    try:
        # Создаём тестовую подписку на 2 минуты
        from datetime import datetime, timedelta
        
        # Удаляем старые тестовые подписки этого пользователя
        with db.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM subscriptions 
                WHERE telegram_id = ? 
                AND stripe_subscription_id LIKE 'test_%'
            """, (user.id,))
        
        # Создаём подписку вручную (на 30 секунд)
        start_date = datetime.now()
        end_date = start_date + timedelta(seconds=30)
        
        try:
            with db.get_db() as conn:
                cursor = conn.cursor()
                sub_id = f'test_sub_{user.id}_{int(datetime.now().timestamp())}'
                cursor.execute("""
                    INSERT INTO subscriptions 
                    (telegram_id, stripe_customer_id, stripe_subscription_id, stripe_price_id, 
                     status, start_date, end_date)
                    VALUES (?, ?, ?, ?, 'active', ?, ?)
                """, (user.id, 'test_customer', sub_id, 
                      'test_price', start_date.isoformat(), end_date.isoformat()))
                logger.info(f"Подписка {sub_id} сохранена в БД для пользователя {user.id}")
        except Exception as e:
            logger.error(f"Ошибка сохранения подписки в БД: {e}")
        
        # Создаём инвайт-ссылку
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=config.CHANNEL_ID,
            member_limit=1,
            name=f"Test_{user.id}",
            expire_date=datetime.now() + timedelta(hours=1)
        )
        
        keyboard = get_main_keyboard(is_subscribed=True)
        
        message = f"""🧪 ТЕСТОВЫЙ ДОСТУП

Ваша ссылка на канал:
{invite_link.invite_link}

⏱ Доступ действителен: 30 СЕКУНД

⚠️ Через 30 секунд вы будете автоматически удалены из канала.

Это тест для проверки работы бота."""
        
        await update.message.reply_text(message, reply_markup=keyboard, disable_web_page_preview=True)
        
        logger.info(f"Тестовый доступ выдан пользователю {user.id} на 30 секунд")
    
    except Exception as e:
        logger.error(f"Ошибка тестового доступа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def check_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить доступ бота к каналу"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    try:
        # Получаем информацию о канале
        chat = await context.bot.get_chat(config.CHANNEL_ID)
        
        # Получаем информацию о боте в канале
        bot_member = await context.bot.get_chat_member(config.CHANNEL_ID, context.bot.id)
        
        message = f"""🔍 Проверка канала

ID канала: {config.CHANNEL_ID}
Название: {chat.title}
Тип: {chat.type}

Статус бота: {bot_member.status}
Может приглашать: {"✅" if bot_member.can_invite_users else "❌"}
Может банить: {"✅" if bot_member.can_restrict_members else "❌"}

{"✅ Всё настроено правильно!" if bot_member.status == "administrator" else "⚠️ Бот должен быть администратором!"}"""
        
        await update.message.reply_text(message)
    
    except Exception as e:
        message = f"""❌ Ошибка доступа к каналу

ID канала: {config.CHANNEL_ID}
Ошибка: {str(e)}

Возможные причины:
1. Бот не добавлен в канал
2. Неправильный ID канала
3. Бот не является администратором

Как исправить:
1. Откройте канал
2. Добавьте бота как администратора
3. Дайте права: Invite users, Ban users"""
        
        await update.message.reply_text(message)

# === АДМИНСКИЕ ФУНКЦИИ ===

async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех пользователей"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.telegram_id, u.username, u.first_name, 
                   s.status, s.end_date
            FROM users u
            LEFT JOIN subscriptions s ON u.telegram_id = s.telegram_id 
                AND s.status = 'active' 
                AND s.end_date > CURRENT_TIMESTAMP
            ORDER BY u.created_at DESC
            LIMIT 50
        """)
        users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("📭 Пользователей пока нет")
        return
    
    message = "👥 Список пользователей (последние 50):\n\n"
    
    for u in users:
        username = f"@{u['username']}" if u['username'] else "Нет username"
        name = u['first_name'] or "Без имени"
        status = "✅ Активна" if u['status'] == 'active' else "❌ Нет подписки"
        
        end_date = ""
        if u['end_date']:
            end_date = f" до {datetime.fromisoformat(u['end_date']).strftime('%d.%m.%Y')}"
        
        message += f"{u['telegram_id']} | {name} ({username})\n{status}{end_date}\n\n"
    
    await update.message.reply_text(message)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    with db.get_db() as conn:
        cursor = conn.cursor()
        
        # Всего пользователей
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Активные подписки
        cursor.execute("""
            SELECT COUNT(*) as count FROM subscriptions
            WHERE status = 'active' AND end_date > CURRENT_TIMESTAMP
        """)
        active_subs = cursor.fetchone()['count']
        
        # Всего платежей
        cursor.execute("SELECT COUNT(*) as count, SUM(amount) as total FROM payments WHERE status = 'succeeded'")
        payments = cursor.fetchone()
        total_payments = payments['count']
        total_revenue = (payments['total'] or 0) / 100
        
        # Истекающие за 7 дней
        cursor.execute("""
            SELECT COUNT(*) as count FROM subscriptions
            WHERE status = 'active' 
            AND end_date > CURRENT_TIMESTAMP
            AND end_date <= datetime(CURRENT_TIMESTAMP, '+7 days')
        """)
        expiring_soon = cursor.fetchone()['count']
    
    message = f"""📊 Статистика бота

👥 Всего пользователей: {total_users}
✅ Активных подписок: {active_subs}
💰 Всего платежей: {total_payments}
💵 Общий доход: {total_revenue:.2f} EUR

⏰ Истекают в течение 7 дней: {expiring_soon}"""
    
    await update.message.reply_text(message)

async def admin_active_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активные подписки"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    from datetime import datetime
    
    with db.get_db() as conn:
        cursor = conn.cursor()
        current_time = datetime.now().isoformat()
        cursor.execute("""
            SELECT u.telegram_id, u.username, u.first_name,
                   s.start_date, s.end_date
            FROM subscriptions s
            JOIN users u ON s.telegram_id = u.telegram_id
            WHERE s.status = 'active' AND s.end_date > ?
            ORDER BY s.end_date ASC
        """, (current_time,))
        subs = cursor.fetchall()
    
    if not subs:
        await update.message.reply_text("📭 Нет активных подписок")
        return
    
    message = f"💳 Активные подписки ({len(subs)}):\n\n"
    
    for idx, s in enumerate(subs, 1):
        user_id = s['telegram_id']
        username = f"@{s['username']}" if s['username'] else "нет username"
        name = s['first_name'] or "Без имени"
        start = datetime.fromisoformat(s['start_date']).strftime('%d.%m.%Y %H:%M')
        end = datetime.fromisoformat(s['end_date']).strftime('%d.%m.%Y %H:%M')
        
        message += f"👤 User ID: {user_id}\n"
        message += f"📝 Аккаунт: {name} ({username})\n"
        message += f"📅 Активация: {start}\n"
        message += f"⏰ Окончание: {end}\n"
        message += f"{'─' * 30}\n\n"
    
    await update.message.reply_text(message)

async def admin_expiring_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Истекающие подписки"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.telegram_id, u.username, u.first_name,
                   s.end_date
            FROM subscriptions s
            JOIN users u ON s.telegram_id = u.telegram_id
            WHERE s.status = 'active' 
            AND s.end_date > CURRENT_TIMESTAMP
            AND s.end_date <= datetime(CURRENT_TIMESTAMP, '+7 days')
            ORDER BY s.end_date ASC
        """)
        subs = cursor.fetchall()
    
    if not subs:
        await update.message.reply_text("✅ Нет истекающих подписок в ближайшие 7 дней")
        return
    
    message = f"⏰ Истекают в течение 7 дней ({len(subs)}):\n\n"
    
    for s in subs:
        username = f"@{s['username']}" if s['username'] else "Нет username"
        name = s['first_name'] or "Без имени"
        end = datetime.fromisoformat(s['end_date']).strftime('%d.%m.%Y')
        days_left = (datetime.fromisoformat(s['end_date']) - datetime.now()).days
        
        message += f"{name} ({username})\nИстекает: {end} (через {days_left} дн.)\n\n"
    
    await update.message.reply_text(message)

async def test_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест: выдать доступ админу"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    try:
        # Создаём тестовую подписку на 1 месяц
        db.create_subscription(
            telegram_id=user.id,
            stripe_customer_id='test_customer',
            stripe_subscription_id=f'test_sub_{user.id}_{datetime.now().timestamp()}',
            stripe_price_id='test_price',
            duration_months=1
        )
        
        # Создаём инвайт-ссылку
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=config.CHANNEL_ID,
            member_limit=1,
            name=f"Test_{user.id}",
            expire_date=datetime.now() + timedelta(hours=1)
        )
        
        message = f"""✅ Тестовая подписка создана!

Ваша ссылка на канал:
{invite_link.invite_link}

Подписка действительна 1 месяц."""
        
        await update.message.reply_text(message, disable_web_page_preview=True)
    
    except Exception as e:
        logger.error(f"Ошибка теста доступа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def test_revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест: удалить доступ админа"""
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        return
    
    try:
        # Удаляем из канала
        await context.bot.ban_chat_member(chat_id=config.CHANNEL_ID, user_id=user.id)
        await context.bot.unban_chat_member(chat_id=config.CHANNEL_ID, user_id=user.id)
        
        message = """✅ Вы удалены из канала (тест)

Для повторного доступа используйте:
🧪 Тест: выдать доступ"""
        
        await update.message.reply_text(message)
    
    except Exception as e:
        logger.error(f"Ошибка теста удаления: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    """Запуск бота"""
    # Валидация конфигурации
    config.validate_config()
    
    # Инициализация БД
    db.init_db()
    
    # Создание приложения
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("testaccess", test_access_command))
    
    # Обработчик текстовых сообщений (кнопок)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Запуск бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
