# -*- coding: utf-8 -*-
import logging
from flask import Flask, request, jsonify
from telegram import Bot
import json
import asyncio
from datetime import datetime, timedelta

import config
import database as db
from stripe_integration import get_checkout_session, get_subscription, verify_webhook_signature

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Создаём экземпляр бота для отправки уведомлений
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

def get_duration_from_price_id(price_id: str) -> int:
    """Определить длительность подписки по Price ID"""
    for period, pid in config.STRIPE_PRICES.items():
        if pid == price_id:
            if '1_month' in period:
                return 1
            elif '6_months' in period:
                return 6
            elif '12_months' in period:
                return 12
    return 1  # По умолчанию 1 месяц

async def send_telegram_message(chat_id: int, text: str, parse_mode: str = None):
    """Отправить сообщение пользователю"""
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        logger.info(f"Сообщение отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения {chat_id}: {e}")

async def create_and_send_invite_link(telegram_id: int):
    """Создать инвайт-ссылку и отправить пользователю"""
    try:
        # Создаём одноразовую инвайт-ссылку
        invite_link = await bot.create_chat_invite_link(
            chat_id=config.CHANNEL_ID,
            member_limit=1,
            name=f"User_{telegram_id}",
            expire_date=datetime.now() + timedelta(hours=24)
        )
        
        message = config.MESSAGES['payment_success'].format(
            invite_link=invite_link.invite_link
        )
        
        await send_telegram_message(telegram_id, message)
        logger.info(f"Инвайт-ссылка отправлена пользователю {telegram_id}")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка создания инвайт-ссылки для {telegram_id}: {e}")
        return False

async def kick_user_from_channel(telegram_id: int):
    """Удалить пользователя из канала"""
    try:
        # Баним пользователя
        await bot.ban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
        # Сразу разбаниваем (кик)
        await bot.unban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
        
        logger.info(f"Пользователь {telegram_id} удалён из канала")
        
        # Уведомляем пользователя
        message = config.MESSAGES['subscription_expired']
        await send_telegram_message(telegram_id, message)
        return True
    
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {telegram_id} из канала: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Обработчик webhook от Stripe"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    
    # Проверяем подпись (если настроен webhook secret)
    if not verify_webhook_signature(payload, sig_header):
        logger.error("Неверная подпись webhook")
        return jsonify({'error': 'Invalid signature'}), 400
    
    try:
        event = json.loads(payload)
        event_type = event['type']
        
        logger.info(f"Получен webhook: {event_type}")
        
        # Обработка успешной оплаты Checkout Session
        if event_type == 'checkout.session.completed':
            asyncio.run(handle_checkout_completed(event['data']['object']))
        
        # Обработка успешного платежа по подписке
        elif event_type == 'invoice.paid':
            asyncio.run(handle_invoice_paid(event['data']['object']))
        
        # Обработка провала платежа
        elif event_type == 'invoice.payment_failed':
            asyncio.run(handle_invoice_failed(event['data']['object']))
        
        # Обработка отмены подписки
        elif event_type == 'customer.subscription.deleted':
            asyncio.run(handle_subscription_deleted(event['data']['object']))
        
        # Обработка обновления подписки
        elif event_type == 'customer.subscription.updated':
            asyncio.run(handle_subscription_updated(event['data']['object']))
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return jsonify({'error': str(e)}), 500

async def handle_checkout_completed(session):
    """Обработка завершения Checkout Session"""
    logger.info(f"Checkout Session завершён: {session['id']}")
    
    # Получаем Telegram ID из метаданных
    metadata = session.get('metadata', {})
    telegram_id = metadata.get('telegram_id')
    
    if not telegram_id:
        logger.error("Telegram ID не найден в метаданных сессии")
        return
    
    telegram_id = int(telegram_id)
    
    # Получаем информацию о подписке
    subscription_id = session.get('subscription')
    customer_id = session.get('customer')
    
    if not subscription_id:
        logger.error("Subscription ID не найден в сессии")
        return
    
    # Получаем детали подписки из Stripe
    subscription = get_subscription(subscription_id)
    
    if not subscription:
        logger.error(f"Не удалось получить подписку {subscription_id}")
        return
    
    # Получаем Price ID
    items = subscription.get('items', {}).get('data', [])
    if not items:
        logger.error("Нет items в подписке")
        return
    
    price_id = items[0].get('price', {}).get('id')
    duration = get_duration_from_price_id(price_id)
    
    # Создаём подписку в БД
    db.create_subscription(
        telegram_id=telegram_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        stripe_price_id=price_id,
        duration_months=duration
    )
    
    # Обновляем статус платежа
    db.add_payment(
        telegram_id=telegram_id,
        stripe_payment_id=session.get('payment_intent', ''),
        stripe_checkout_session_id=session['id'],
        amount=session.get('amount_total', 0),
        currency=session.get('currency', 'eur'),
        status='succeeded'
    )
    
    # Отправляем инвайт-ссылку
    await create_and_send_invite_link(telegram_id)

async def handle_invoice_paid(invoice):
    """Обработка успешной оплаты счёта (продление подписки)"""
    logger.info(f"Инвойс оплачен: {invoice['id']}")
    
    subscription_id = invoice.get('subscription')
    
    if not subscription_id:
        return
    
    # Обновляем статус подписки в БД
    db.update_subscription_status(subscription_id, 'active')
    
    # Получаем подписку из БД
    subscription = db.get_subscription_by_stripe_id(subscription_id)
    
    if subscription:
        telegram_id = subscription['telegram_id']
        
        # Проверяем, есть ли пользователь в канале
        # Если нет - отправляем новую инвайт-ссылку
        try:
            member = await bot.get_chat_member(config.CHANNEL_ID, telegram_id)
            if member.status in ['left', 'kicked']:
                await create_and_send_invite_link(telegram_id)
            else:
                # Уведомляем о продлении
                await send_telegram_message(
                    telegram_id,
                    "✅ Tu suscripción ha sido renovada con éxito.\n\nTu acceso al canal continúa activo."
                )
        except Exception as e:
            logger.error(f"Ошибка проверки статуса пользователя: {e}")

async def handle_invoice_failed(invoice):
    """Обработка провала оплаты счёта"""
    logger.info(f"Инвойс не оплачен: {invoice['id']}")
    
    subscription_id = invoice.get('subscription')
    
    if not subscription_id:
        return
    
    # Обновляем статус подписки
    db.update_subscription_status(subscription_id, 'payment_failed')
    
    # Получаем подписку из БД
    subscription = db.get_subscription_by_stripe_id(subscription_id)
    
    if subscription:
        telegram_id = subscription['telegram_id']
        logger.info(f"Оплата не прошла для пользователя {telegram_id}")

async def handle_subscription_deleted(subscription):
    """Обработка удаления/отмены подписки"""
    logger.info(f"Подписка отменена: {subscription['id']}")
    
    subscription_id = subscription['id']
    
    # Обновляем статус в БД
    db.update_subscription_status(subscription_id, 'cancelled')
    
    # Получаем подписку из БД
    sub_data = db.get_subscription_by_stripe_id(subscription_id)
    
    if sub_data:
        telegram_id = sub_data['telegram_id']
        
        # Удаляем из канала
        await kick_user_from_channel(telegram_id)

async def handle_subscription_updated(subscription):
    """Обработка обновления подписки"""
    logger.info(f"Подписка обновлена: {subscription['id']}")
    
    subscription_id = subscription['id']
    status = subscription.get('status')
    
    # Обновляем статус в БД
    db.update_subscription_status(subscription_id, status)
    
    # Если подписка деактивирована - удаляем из канала
    if status in ['canceled', 'unpaid', 'past_due']:
        sub_data = db.get_subscription_by_stripe_id(subscription_id)
        if sub_data:
            telegram_id = sub_data['telegram_id']
            await kick_user_from_channel(telegram_id)

@app.route('/success')
def payment_success():
    """Страница успешной оплаты"""
    return """
    <html>
        <head>
            <meta charset="utf-8">
            <title>Оплата успешна</title>
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; }
                h1 { color: #4CAF50; }
            </style>
        </head>
        <body>
            <h1>✅ Оплата успешна!</h1>
            <p>Ваша подписка активирована.</p>
            <p>Вы получите сообщение в Telegram со ссылкой на закрытый канал.</p>
            <p><a href="https://t.me/YourBotUsername">Вернуться к боту</a></p>
        </body>
    </html>
    """

@app.route('/cancel')
def payment_cancel():
    """Страница отмены оплаты"""
    return """
    <html>
        <head>
            <meta charset="utf-8">
            <title>Оплата отменена</title>
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; }
                h1 { color: #f44336; }
            </style>
        </head>
        <body>
            <h1>❌ Оплата отменена</h1>
            <p>Платёж был отменён.</p>
            <p>Если возникли проблемы, свяжитесь с поддержкой.</p>
            <p><a href="https://t.me/YourBotUsername">Вернуться к боту</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

def main():
    """Запуск webhook сервера"""
    # Валидация конфигурации
    config.validate_config()
    
    # Инициализация БД
    db.init_db()
    
    logger.info(f"Webhook сервер запущен на порту {config.PORT}")
    app.run(host='0.0.0.0', port=config.PORT, debug=False)

if __name__ == '__main__':
    main()
