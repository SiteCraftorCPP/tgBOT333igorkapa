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
            [KeyboardButton("📱 Obtener enlace")],
            [KeyboardButton("📋 Mi suscripción")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🚀 Comprar suscripción")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_plans_keyboard():
    """Клавиатура выбора тарифа"""
    keyboard = [
        [KeyboardButton("📅 1 mes - 4.99 EUR")],
        [KeyboardButton("📅 3 meses - 24.99 EUR (1 mes gratis)")],
        [KeyboardButton("📅 12 meses - 44.99 EUR (3 meses gratis)")],
        [KeyboardButton("« Atrás")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = [
        [KeyboardButton("💳 Suscripciones activas")],
        [KeyboardButton("« Menú principal")]
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
        message = f"{config.MESSAGES['welcome']}\n\n✅ Tu suscripción está activa hasta {expiry_date}"
    else:
        message = config.MESSAGES['welcome']
    
    await update.message.reply_text(message, reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user = update.effective_user
    
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ No tienes acceso al panel de administración")
        return
    
    keyboard = get_admin_keyboard()
    await update.message.reply_text(config.MESSAGES['admin_menu'], reply_markup=keyboard)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок)"""
    text = update.message.text
    user = update.effective_user
    
    # Главное меню
    if text == "🚀 Comprar suscripción":
        await show_plans(update, context)
    
    elif text == "📱 Obtener enlace":
        await get_link(update, context)
    
    elif text == "📋 Mi suscripción":
        await show_subscription(update, context)
    
    elif text == "« Atrás" or text == "« Menú principal":
        await start_command(update, context)
    
    # Выбор тарифа
    elif "mes" in text.lower() and "EUR" in text:
        await plan_selected(update, context, text)
    
    # Админ-панель
    elif text == "💳 Suscripciones activas":
        await admin_active_subscriptions(update, context)
    
    else:
        await update.message.reply_text("Selecciona una opción del menú 👇")

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать тарифные планы"""
    keyboard = get_plans_keyboard()
    await update.message.reply_text(config.MESSAGES['choose_plan'], reply_markup=keyboard)

async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_text: str):
    """Обработка выбора тарифа"""
    user = update.effective_user
    
    # Определяем price_id по тексту (смотрим на начало строки, чтобы избежать ошибок с описанием)
    if plan_text.startswith("📅 1 mes"):
        price_id = config.STRIPE_PRICES['1_month']
        plan = '1_month'
    elif plan_text.startswith("📅 3 meses"):
        price_id = config.STRIPE_PRICES['6_months']
        plan = '6_months'
    elif plan_text.startswith("📅 12 meses"):
        price_id = config.STRIPE_PRICES['12_months']
        plan = '12_months'
    else:
        await update.message.reply_text("❌ Plan no válido")
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
            
            message = """✅ ¡El enlace de pago ha sido creado!

Haz clic en el botón de abajo para realizar un pago seguro a través de Stripe.

Después de completar el pago, recibirás automáticamente acceso al canal.

👇 Haz clic para pagar:"""
            
            # Инлайн кнопка для оплаты (используем короткую ссылку если доступна)
            payment_url = session.get('short_url', session['url'])
            inline_keyboard = [
                [InlineKeyboardButton("💳 Pagar", url=payment_url)]
            ]
            inline_markup = InlineKeyboardMarkup(inline_keyboard)
            
            await update.message.reply_text(message, reply_markup=inline_markup)
        else:
            await update.message.reply_text("❌ Error al crear sesión de pago. Inténtalo de nuevo.")
    
    except Exception as e:
        logger.error(f"Ошибка создания Checkout Session: {e}")
        await update.message.reply_text("❌ Error al crear sesión de pago. Inténtalo de nuevo.")

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ссылку на канал"""
    user = update.effective_user
    
    # Проверяем активную подписку
    subscription = db.get_active_subscription(user.id)
    
    if not subscription:
        message = "❌ No tienes una suscripción activa.\n\nCompra una suscripción para obtener acceso."
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
        
        message = f"""✅ ¡Tu suscripción está activa!

Accede al canal privado a través del siguiente enlace:

{invite_link.invite_link}

Este enlace es personal y válido solo para ti."""
        
        keyboard = get_main_keyboard(is_subscribed=True)
        await update.message.reply_text(message, reply_markup=keyboard, disable_web_page_preview=True)
    
    except Exception as e:
        logger.error(f"Ошибка создания invite link: {e}")
        await update.message.reply_text("❌ Error al crear el enlace. Inténtalo de nuevo.")

async def show_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о подписке"""
    user = update.effective_user
    subscription = db.get_active_subscription(user.id)
    
    if not subscription:
        message = "❌ No tienes una suscripción activa."
        keyboard = get_main_keyboard(is_subscribed=False)
    else:
        start_date = datetime.fromisoformat(subscription['start_date']).strftime('%d.%m.%Y')
        end_date = datetime.fromisoformat(subscription['end_date']).strftime('%d.%m.%Y')
        
        # Сколько дней осталось
        days_left = (datetime.fromisoformat(subscription['end_date']) - datetime.now()).days
        
        message = f"""📋 Tu suscripción

Estado: ✅ Activa
Inicio: {start_date}
Válida hasta: {end_date}
Días restantes: {days_left}

Tu acceso al canal privado está garantizado hasta la fecha de finalización."""
        
        keyboard = get_main_keyboard(is_subscribed=True)
    
    await update.message.reply_text(message, reply_markup=keyboard)

# === АДМИНСКИЕ ФУНКЦИИ ===

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
        await update.message.reply_text("📭 No hay suscripciones activas")
        return
    
    message = f"💳 Suscripciones activas ({len(subs)}):\n\n"
    
    for idx, s in enumerate(subs, 1):
        user_id = s['telegram_id']
        username = f"@{s['username']}" if s['username'] else "sin username"
        name = s['first_name'] or "Sin nombre"
        start = datetime.fromisoformat(s['start_date']).strftime('%d.%m.%Y %H:%M')
        end = datetime.fromisoformat(s['end_date']).strftime('%d.%m.%Y %H:%M')
        
        message += f"👤 User ID: {user_id}\n"
        message += f"📝 Cuenta: {name} ({username})\n"
        message += f"📅 Activación: {start}\n"
        message += f"⏰ Finalización: {end}\n"
        message += f"{'─' * 30}\n\n"
    
    await update.message.reply_text(message)

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
    
    # Обработчик текстовых сообщений (кнопок)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Запуск бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
