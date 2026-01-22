# -*- coding: utf-8 -*-
"""
Скрипт для отправки уведомлений об истекающих подписках.
Запускать как крон-задачу каждый день.
"""
import logging
import asyncio
from telegram import Bot
from datetime import datetime, timedelta

import config
import database as db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def notify_expiring_subscriptions():
    """Уведомить пользователей и админов об истекающих завтра подписках"""
    logger.info("Начало проверки истекающих подписок")
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    
    # Получаем подписки, истекающие завтра
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0)
    
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, u.username, u.first_name
            FROM subscriptions s
            JOIN users u ON s.telegram_id = u.telegram_id
            WHERE s.status = 'active'
            AND s.end_date >= ?
            AND s.end_date <= ?
        """, (tomorrow_start.isoformat(), tomorrow_end.isoformat()))
        
        expiring = cursor.fetchall()
    
    logger.info(f"Найдено истекающих завтра подписок: {len(expiring)}")
    
    if not expiring:
        logger.info("Нет истекающих подписок")
        return
    
    # Уведомляем пользователей
    for sub in expiring:
        telegram_id = sub['telegram_id']
        end_date = datetime.fromisoformat(sub['end_date']).strftime('%d.%m.%Y %H:%M')
        
        message = config.MESSAGES['subscription_expiring_soon'].format(
            expiry_date=end_date
        )
        
        try:
            await bot.send_message(chat_id=telegram_id, text=message)
            logger.info(f"Уведомление отправлено пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")
    
    # Уведомляем админов
    admin_message = f"""⚠️ УВЕДОМЛЕНИЕ ДЛЯ АДМИНОВ

Подписки, истекающие завтра ({len(expiring)}):

"""
    
    for sub in expiring:
        username = f"@{sub['username']}" if sub['username'] else "Нет username"
        name = sub['first_name'] or "Без имени"
        end_date = datetime.fromisoformat(sub['end_date']).strftime('%d.%m.%Y %H:%M')
        
        admin_message += f"• {name} ({username})\n  Истекает: {end_date}\n\n"
    
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_message)
            logger.info(f"Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    logger.info("Уведомления отправлены")

def main():
    """Точка входа"""
    config.validate_config()
    asyncio.run(notify_expiring_subscriptions())

if __name__ == '__main__':
    main()
