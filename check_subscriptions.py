# -*- coding: utf-8 -*-
"""
Скрипт для проверки истёкших подписок и удаления пользователей из канала.
Запускать как крон-задачу каждые 6-12 часов.
"""
import logging
import asyncio
from telegram import Bot
from datetime import datetime

import config
import database as db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def check_and_remove_expired():
    """Проверить истёкшие подписки и удалить пользователей из канала"""
    logger.info("Начало проверки истёкших подписок")
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    
    # Получаем истёкшие подписки
    expired = db.get_expired_subscriptions()
    
    # Также проверяем тестовые подписки (они истекают быстрее)
    current_time = datetime.now().isoformat()
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND end_date <= ?
            AND stripe_subscription_id LIKE 'test_%'
        """, (current_time,))
        test_expired = cursor.fetchall()
        
        if test_expired:
            expired = list(expired) + [dict(row) for row in test_expired]
    
    logger.info(f"Найдено истёкших подписок: {len(expired)}")
    
    for subscription in expired:
        telegram_id = subscription['telegram_id']
        
        try:
            # Пытаемся удалить пользователя из канала
            await bot.ban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
            await bot.unban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
            
            logger.info(f"Пользователь {telegram_id} удалён из канала")
            
            # Обновляем статус подписки
            db.update_subscription_status(
                subscription['stripe_subscription_id'],
                'expired'
            )
            
            # Отправляем уведомление пользователю
            message = config.MESSAGES['subscription_expired']
            await bot.send_message(chat_id=telegram_id, text=message)
            
            # Уведомляем админов (получаем имя пользователя)
            with db.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, first_name FROM users WHERE telegram_id = ?", (telegram_id,))
                user_info = cursor.fetchone()
            
            if user_info:
                username = f"@{user_info['username']}" if user_info['username'] else "нет username"
                name = user_info['first_name'] or "Без имени"
                admin_message = f"⚠️ Подписка истекла: {name} ({username}). Пользователь удалён из канала."
            else:
                admin_message = f"⚠️ Подписка истекла. Пользователь удалён из канала."
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=admin_message)
                except Exception as ex:
                    logger.error(f"Ошибка уведомления админа {admin_id}: {ex}")
            
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя {telegram_id}: {e}")
    
    logger.info("Проверка завершена")

def main():
    """Точка входа"""
    config.validate_config()
    asyncio.run(check_and_remove_expired())

if __name__ == '__main__':
    main()
