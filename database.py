# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

import os
DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot_database.db')
print(f"[DATABASE] Using file: {DATABASE_FILE}")

@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Инициализация базы данных"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                stripe_price_id TEXT,
                status TEXT NOT NULL,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        
        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                stripe_payment_id TEXT UNIQUE,
                stripe_checkout_session_id TEXT UNIQUE,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_telegram_id ON subscriptions(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_telegram_id ON payments(telegram_id)')
        
        logger.info("База данных инициализирована")

def add_or_update_user(telegram_id, username=None, first_name=None, last_name=None):
    """Добавить или обновить пользователя"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
        ''', (telegram_id, username, first_name, last_name))
        logger.info(f"Пользователь {telegram_id} добавлен/обновлён")

def create_subscription(telegram_id, stripe_customer_id, stripe_subscription_id, 
                       stripe_price_id, duration_months):
    """Создать новую подписку"""
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30 * duration_months)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscriptions 
            (telegram_id, stripe_customer_id, stripe_subscription_id, stripe_price_id, 
             status, start_date, end_date)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
        ''', (telegram_id, stripe_customer_id, stripe_subscription_id, stripe_price_id,
              start_date, end_date))
        
        subscription_id = cursor.lastrowid
        logger.info(f"Создана подписка {subscription_id} для пользователя {telegram_id}")
        return subscription_id

def get_active_subscription(telegram_id):
    """Получить активную подписку пользователя"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM subscriptions
            WHERE telegram_id = ? 
            AND status = 'active'
            AND end_date > CURRENT_TIMESTAMP
            ORDER BY end_date DESC
            LIMIT 1
        ''', (telegram_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None

def update_subscription_status(stripe_subscription_id, status):
    """Обновить статус подписки"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE subscriptions
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = ?
        ''', (status, stripe_subscription_id))
        logger.info(f"Подписка {stripe_subscription_id} обновлена: {status}")

def extend_subscription(stripe_subscription_id, months):
    """Продлить подписку"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE subscriptions
            SET end_date = datetime(end_date, '+' || ? || ' months'),
                updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = ?
        ''', (months, stripe_subscription_id))
        logger.info(f"Подписка {stripe_subscription_id} продлена на {months} месяцев")

def add_payment(telegram_id, stripe_payment_id, stripe_checkout_session_id, 
                amount, currency, status='succeeded'):
    """Добавить запись о платеже"""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO payments 
                (telegram_id, stripe_payment_id, stripe_checkout_session_id, 
                 amount, currency, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (telegram_id, stripe_payment_id, stripe_checkout_session_id,
                  amount, currency, status))
            
            payment_id = cursor.lastrowid
            logger.info(f"Добавлен платёж {payment_id} для пользователя {telegram_id}")
            return payment_id
        except sqlite3.IntegrityError:
            logger.warning(f"Платёж {stripe_payment_id} уже существует")
            return None

def get_expired_subscriptions():
    """Получить истёкшие подписки"""
    from datetime import datetime
    current_time = datetime.now().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND end_date <= ?
        ''', (current_time,))
        
        rows = cursor.fetchall()
        logger.info(f"SQL: Проверка подписок с end_date <= {current_time}, найдено: {len(rows)}")
        return [dict(row) for row in rows]

def get_user_by_telegram_id(telegram_id):
    """Получить пользователя по Telegram ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_subscription_by_stripe_id(stripe_subscription_id):
    """Получить подписку по Stripe Subscription ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM subscriptions
            WHERE stripe_subscription_id = ?
        ''', (stripe_subscription_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_subscription_by_checkout_session(checkout_session_id):
    """Получить Telegram ID по Checkout Session ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT telegram_id FROM payments
            WHERE stripe_checkout_session_id = ?
        ''', (checkout_session_id,))
        row = cursor.fetchone()
        return row['telegram_id'] if row else None
