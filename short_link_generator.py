# -*- coding: utf-8 -*-
"""
Генератор коротких ссылок для Stripe Checkout
"""
import random
import string
import requests
import logging

logger = logging.getLogger(__name__)

# Домен для коротких ссылок
DOMAIN = "https://pay.enguerrados.com"
REDIRECT_SERVER_URL = "http://localhost:8001"

def generate_short_code(length=8):
    """Генерировать случайный короткий код"""
    # Используем только буквы и цифры (без путаницы: 0/O, 1/l)
    chars = string.ascii_letters + string.digits
    chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('l', '')
    
    return ''.join(random.choice(chars) for _ in range(length))

def create_short_link(full_stripe_url, plan_name=''):
    """
    Создать короткую ссылку для Stripe Checkout URL
    
    Args:
        full_stripe_url: Полный URL от Stripe
        plan_name: Название плана (1m, 6m, 12m)
    
    Returns:
        str: Короткая ссылка или полная (если сервер недоступен)
    """
    try:
        # Генерируем короткий код
        short_code = generate_short_code(8)
        
        # Если указан план - добавляем префикс
        if plan_name:
            short_code = f"{plan_name}-{short_code}"
        
        # Регистрируем ссылку на redirect сервере
        response = requests.post(
            f"{REDIRECT_SERVER_URL}/add",
            json={
                'short_code': short_code,
                'full_url': full_stripe_url
            },
            timeout=2
        )
        
        if response.status_code == 200:
            short_url = f"{DOMAIN}/{short_code}"
            logger.info(f"✅ Короткая ссылка создана: {short_url}")
            return short_url
        else:
            logger.error(f"Ошибка создания короткой ссылки: {response.status_code}")
            return full_stripe_url
    
    except Exception as e:
        logger.error(f"Ошибка генерации короткой ссылки: {e}")
        # Если что-то пошло не так - возвращаем полную ссылку
        return full_stripe_url
