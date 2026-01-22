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
    """
    Проверить истёкшие подписки:
    - Через 24 часа после истечения → отправить предупреждение
    - Через 48 часов после истечения → удалить из канала
    """
    logger.info("Начало проверки истёкших подписок")
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    
    # Получаем истёкшие подписки
    expired = db.get_expired_subscriptions()
    
    now = datetime.now()
    grace_period_24h = timedelta(hours=24)
    grace_period_48h = timedelta(hours=48)
    
    # Разделяем на категории:
    # 1. Прошло 24-48 часов → отправить предупреждение
    # 2. Прошло 48+ часов → удалить из канала
    
    users_to_warn = {}      # Через 24ч - предупреждение
    users_to_remove = {}    # Через 48ч - удаление
    
    for sub in expired:
        end_date = datetime.fromisoformat(sub['end_date'])
        time_elapsed = now - end_date
        telegram_id = sub['telegram_id']
        
        if time_elapsed >= grace_period_48h:
            # Прошло 48+ часов - удаляем
            if telegram_id not in users_to_remove:
                users_to_remove[telegram_id] = []
            users_to_remove[telegram_id].append(sub)
        elif time_elapsed >= grace_period_24h:
            # Прошло 24-48 часов - предупреждаем
            if telegram_id not in users_to_warn:
                users_to_warn[telegram_id] = []
            users_to_warn[telegram_id].append(sub)
        else:
            # Прошло < 24 часов - ничего не делаем (ждём)
            logger.info(f"⏳ Юзер {telegram_id} в первом льготном периоде (истекло {end_date.strftime('%d.%m %H:%M')})")
    
    logger.info(f"К предупреждению (24ч): {len(users_to_warn)}, к удалению (48ч): {len(users_to_remove)}")
    
    # === ПРЕДУПРЕЖДАЕМ (прошло 24ч) ===
    for telegram_id, subs in users_to_warn.items():
        # Проверяем, есть ли ДРУГИЕ активные подписки
        active_sub = db.get_active_subscription(telegram_id)
        
        if active_sub:
            logger.info(f"⏭️ Пропуск предупреждения {telegram_id}: есть активная подписка до {active_sub['end_date']}")
            # Помечаем старые как expired
            with db.get_db() as conn:
                cursor = conn.cursor()
                for sub in subs:
                    cursor.execute('''
                        UPDATE subscriptions
                        SET status = 'expired', updated_at = ?
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), sub['id']))
            continue
        
        # Нет активных - отправляем ПРЕДУПРЕЖДЕНИЕ
        try:
            warning_message = """⚠️ Tu suscripción ha finalizado.

Tienes 24 horas para renovarla antes de perder el acceso al canal.

Para renovar, selecciona un plan en el bot."""
            
            await bot.send_message(chat_id=telegram_id, text=warning_message)
            logger.info(f"⚠️ Предупреждение отправлено {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки предупреждения {telegram_id}: {e}")
    
    # === УДАЛЯЕМ (прошло 48ч) ===
    for telegram_id, subs in users_to_remove.items():
        
        try:
        # ВАЖНО: Проверяем, есть ли у юзера ДРУГИЕ активные подписки
        active_sub = db.get_active_subscription(telegram_id)
        
        if active_sub:
            logger.info(f"⏭️ Пропуск удаления {telegram_id}: есть активная подписка до {active_sub['end_date']}")
            
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
        logger.info(f"❌ Удаляем {telegram_id} из канала (прошло 48ч, нет активных подписок)")
        
        try:
            
            # Удаляем пользователя из канала
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
            
            # Уведомляем админов (получаем имя пользователя)
            with db.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username, first_name FROM users WHERE telegram_id = ?", (telegram_id,))
                user_info = cursor.fetchone()
            
            if user_info:
                username = f"@{user_info['username']}" if user_info['username'] else "sin username"
                name = user_info['first_name'] or "Sin nombre"
                admin_message = f"⚠️ Suscripción expirada: {name} ({username}). Usuario eliminado del canal."
            else:
                admin_message = f"⚠️ Suscripción expirada. Usuario eliminado del canal."
            
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=admin_message)
                except Exception as ex:
                    logger.error(f"Ошибка уведомления админа {admin_id}: {ex}")
        
        except telegram.error.BadRequest as e:
            if "not enough rights" in str(e).lower():
                logger.error(f"❌ Нет прав для удаления пользователя {telegram_id}")
            elif "user is an administrator" in str(e).lower() or "chat owner" in str(e).lower():
                logger.warning(f"⚠️ Пользователь {telegram_id} - админ/владелец канала")
            else:
                logger.error(f"❌ Ошибка Telegram для {telegram_id}: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {telegram_id}: {e}")
    
    logger.info("Проверка завершена")

def main():
    """Точка входа"""
    config.validate_config()
    asyncio.run(check_and_remove_expired())

if __name__ == '__main__':
    main()
