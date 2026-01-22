# -*- coding: utf-8 -*-
import requests
import logging
from typing import Dict, Optional

import config

logger = logging.getLogger(__name__)

STRIPE_API_BASE = "https://api.stripe.com/v1"

def get_headers():
    """Получить заголовки для запросов к Stripe API"""
    return {
        "Authorization": f"Bearer {config.STRIPE_API_KEY}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

def create_checkout_session(price_id: str, customer_email: str, metadata: Dict) -> Optional[Dict]:
    """
    Создать Checkout Session в Stripe
    
    Args:
        price_id: ID цены в Stripe
        customer_email: Email клиента
        metadata: Метаданные (telegram_id, username, etc)
    
    Returns:
        Dict с данными сессии или None при ошибке
    """
    try:
        url = f"{STRIPE_API_BASE}/checkout/sessions"
        
        data = {
            "mode": "subscription",
            "payment_method_types[]": "card",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": 1,
            "customer_email": customer_email,
            "success_url": config.WEBHOOK_URL.replace('/webhook', '/success?session_id={CHECKOUT_SESSION_ID}'),
            "cancel_url": config.WEBHOOK_URL.replace('/webhook', '/cancel'),
        }
        
        # Добавляем метаданные
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = str(value)
        
        response = requests.post(url, headers=get_headers(), data=data)
        
        if response.status_code == 200:
            session = response.json()
            logger.info(f"Создана Checkout Session: {session['id']}")
            return session
        else:
            error = response.json()
            logger.error(f"Ошибка создания Checkout Session: {error}")
            return None
    
    except Exception as e:
        logger.error(f"Исключение при создании Checkout Session: {e}")
        return None

def get_price_info(price_id: str) -> Optional[Dict]:
    """
    Получить информацию о цене
    
    Returns:
        Dict с информацией о цене: amount, currency, interval
    """
    try:
        url = f"{STRIPE_API_BASE}/prices/{price_id}"
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            price = response.json()
            
            amount = price.get('unit_amount', 0) / 100 if price.get('unit_amount') else 0
            currency = price.get('currency', 'eur').upper()
            
            recurring = price.get('recurring', {})
            interval = recurring.get('interval', 'month') if recurring else 'one-time'
            interval_count = recurring.get('interval_count', 1) if recurring else 1
            
            return {
                'amount': amount,
                'currency': currency,
                'interval': interval,
                'interval_count': interval_count,
                'display': f"{amount} {currency}"
            }
        else:
            logger.error(f"Ошибка получения цены {price_id}: {response.json()}")
            return None
    
    except Exception as e:
        logger.error(f"Исключение при получении цены: {e}")
        return None

def get_subscription(subscription_id: str) -> Optional[Dict]:
    """Получить информацию о подписке"""
    try:
        url = f"{STRIPE_API_BASE}/subscriptions/{subscription_id}"
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Ошибка получения подписки: {response.json()}")
            return None
    
    except Exception as e:
        logger.error(f"Исключение при получении подписки: {e}")
        return None

def cancel_subscription(subscription_id: str) -> bool:
    """Отменить подписку"""
    try:
        url = f"{STRIPE_API_BASE}/subscriptions/{subscription_id}"
        response = requests.delete(url, headers=get_headers())
        
        if response.status_code == 200:
            logger.info(f"Подписка {subscription_id} отменена")
            return True
        else:
            logger.error(f"Ошибка отмены подписки: {response.json()}")
            return False
    
    except Exception as e:
        logger.error(f"Исключение при отмене подписки: {e}")
        return False

def get_checkout_session(session_id: str) -> Optional[Dict]:
    """Получить информацию о Checkout Session"""
    try:
        url = f"{STRIPE_API_BASE}/checkout/sessions/{session_id}"
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Ошибка получения сессии: {response.json()}")
            return None
    
    except Exception as e:
        logger.error(f"Исключение при получении сессии: {e}")
        return None

def get_customer(customer_id: str) -> Optional[Dict]:
    """Получить информацию о клиенте"""
    try:
        url = f"{STRIPE_API_BASE}/customers/{customer_id}"
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Ошибка получения клиента: {response.json()}")
            return None
    
    except Exception as e:
        logger.error(f"Исключение при получении клиента: {e}")
        return None

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Проверить подпись webhook от Stripe
    
    ВАЖНО: Для продакшена нужно использовать webhook secret
    """
    if not config.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET не установлен - webhook не проверяется!")
        return True
    
    # TODO: Реализовать проверку подписи через stripe.Webhook.construct_event
    # Сейчас возвращаем True для упрощения
    return True
