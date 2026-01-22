# -*- coding: utf-8 -*-
"""
Скрипт для проверки истёкших подписок и удаления пользователей из канала.
Запускать как крон-задачу каждые 6-12 часов.
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

async def check_and_remove_expired():
    """Проверить истёкшие подписки и удалить пользователей из канала"""
    logger.info("Начало проверки истёкших подписок")
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    
    # Получаем истёкшие подписки
    expired = db.get_expired_subscriptions()
    
    # ФИЛЬТРАЦИЯ: Удаляем только тех, у кого подписка кончилась более 24 часов назад
    # Это дает юзеру 1 день на продление
    final_to_remove = []
    grace_period = timedelta(days=1)
    now = datetime.now()
    
    for sub in expired:
        end_date = datetime.fromisoformat(sub['end_date'])
        if now > (end_date + grace_period):
            final_to_remove.append(sub)
        else:
            logger.info(f"⏳ Юзер {sub['telegram_id']} в льготном периоде (истекло {end_date.strftime('%d.%m %H:%M')})")

    # Группируем подписки по telegram_id (только для тех, кто прошел льготный период)
    users_to_check = {}
    for sub in final_to_remove:
        telegram_id = sub['telegram_id']
        if telegram_id not in users_to_check:
            users_to_check[telegram_id] = []
        users_to_check[telegram_id].append(sub)
    
    logger.info(f"Итого к удалению после льготного периода: {len(users_to_check)}")
    
    # Обрабатываем каждого пользователя
    for telegram_id, subs in users_to_check.items():
        
        try:
            # ВАЖНО: Проверяем, есть ли у юзера ДРУГИЕ активные подписки
            active_sub = db.get_active_subscription(telegram_id)
            
            if active_sub:
                logger.info(f"⏭️ Пропуск {telegram_id}: есть активная подписка до {active_sub['end_date']}")
                
                # Старые истёкшие помечаем как expired, но пользователя НЕ удаляем
                with db.get_db() as conn:
                    cursor = conn.cursor()
                    for sub in subs:
                        cursor.execute('''
                            UPDATE subscriptions
                            SET status = 'expired', updated_at = ?
                            WHERE id = ?
                        ''', (datetime.now().isoformat(), sub['id']))
                
                logger.info(f"Старые подписки помечены как expired, но юзер {telegram_id} остаётся в канале")
                continue
            
            # Нет активных подписок - УДАЛЯЕМ из канала
            logger.info(f"❌ Удаляем {telegram_id} из канала (нет активных подписок)")
            
            # Пытаемся удалить пользователя из канала
            await bot.ban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
            await bot.unban_chat_member(chat_id=config.CHANNEL_ID, user_id=telegram_id)
            
            logger.info(f"✅ Пользователь {telegram_id} удалён из канала")
            
            # Обновляем статус ВСЕХ его подписок на 'expired'
            with db.get_db() as conn:
                cursor = conn.cursor()
                for sub in subs:
                    cursor.execute('''
                        UPDATE subscriptions
                        SET status = 'expired', updated_at = ?
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), sub['id']))
            
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
