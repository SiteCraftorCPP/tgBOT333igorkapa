# -*- coding: utf-8 -*-
"""
Сервер для редиректов коротких ссылок на Stripe Checkout
Запускается на порту 8001 (отдельно от webhook сервера)
"""
import logging
from flask import Flask, redirect, request, render_template_string
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Хранилище коротких ссылок -> полных Stripe URL
# Обновляется при создании checkout session в stripe_integration.py
SHORT_LINKS = {}

@app.route('/')
def index():
    """Главная страница - редирект на Telegram бота"""
    # TODO: Замени на username своего бота
    return redirect('https://t.me/YOUR_BOT_USERNAME')

@app.route('/<short_code>')
def redirect_payment(short_code):
    """Редирект короткой ссылки на полный Stripe URL"""
    
    # Проверяем, есть ли короткий код в базе
    if short_code in SHORT_LINKS:
        full_url = SHORT_LINKS[short_code]
        logger.info(f"Редирект: {short_code} -> {full_url[:50]}...")
        return redirect(full_url)
    
    # Если не найден - показываем красивую страницу ошибки
    logger.warning(f"Короткий код не найден: {short_code}")
    return render_template_string(ERROR_PAGE), 404

@app.route('/add', methods=['POST'])
def add_link():
    """API для добавления короткой ссылки (вызывается из stripe_integration.py)"""
    data = request.json
    short_code = data.get('short_code')
    full_url = data.get('full_url')
    
    if not short_code or not full_url:
        return {'error': 'Missing parameters'}, 400
    
    SHORT_LINKS[short_code] = full_url
    logger.info(f"Добавлена короткая ссылка: {short_code}")
    
    return {'status': 'ok', 'short_code': short_code}, 200

@app.route('/health')
def health():
    """Health check"""
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'links_count': len(SHORT_LINKS)
    }

# Красивая страница ошибки
ERROR_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Enlace no encontrado - ENGUERRADOS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            font-size: 72px;
            color: #667eea;
            margin-bottom: 20px;
        }
        h2 {
            font-size: 24px;
            color: #333;
            margin-bottom: 15px;
        }
        p {
            color: #666;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        a {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 40px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: 600;
            transition: transform 0.2s;
        }
        a:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍</h1>
        <h2>Enlace no encontrado</h2>
        <p>Este enlace de pago no existe o ha expirado.</p>
        <p>Por favor, solicita un nuevo enlace de pago desde el bot.</p>
        <a href="https://t.me/YOUR_BOT_USERNAME">Ir al Bot</a>
        <!-- TODO: Замени YOUR_BOT_USERNAME на username своего бота -->
    </div>
</body>
</html>
"""

def main():
    """Запуск сервера редиректов"""
    logger.info("Сервер редиректов запущен на порту 8001")
    app.run(host='0.0.0.0', port=8001, debug=False)

if __name__ == '__main__':
    main()
