# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', 0))
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Stripe Configuration
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Server Configuration
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://localhost:8080/webhook')
PORT = int(os.getenv('PORT', 8080))

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

# Stripe Price IDs (автоматически подтягиваются из API)
STRIPE_PRICES = {
    '1_month': 'price_1SrkkQAQcjmHJH4yZ7ECWxPM',  # 4.99 EUR/месяц
    '6_months': 'price_1Srkp1AQcjmHJH4ynlLT5I5v',  # 24.99 EUR/6 месяцев
    '12_months': 'price_1SrktMAQcjmHJH4y55By2JLp'  # 44.99 EUR/12 месяцев
}

# Тексты бота (испанский)
MESSAGES = {
    'welcome': """👋🏻 Bienvenido a ENGUERRADOS

Estás a un solo paso de acceder a información que la mayoría no ve o no sabe interpretar.

ENGUERRADOS es un espacio privado para quienes entienden que el mundo se mueve por poder, intereses y decisiones estratégicas, no por titulares superficiales.

🚀 Tras el pago, obtendrás acceso inmediato a análisis geopolítico y geoeconómico de alto nivel:
— hechos verificados
— contexto profundo
— lectura estratégica de conflictos, mercados y alianzas globales.

Aquí no se consume ruido.
Aquí se anticipan escenarios y se toman decisiones con ventaja.""",

    'choose_plan': """La suscripción representa tu membresía y el acceso a una comunidad privada, donde el análisis estratégico convierte la información en ventaja.

Selecciona el período de suscripción:""",

    'payment_success': """🙌🏻 Pago realizado con éxito

Puedes unirte al canal de la comunidad a través del siguiente enlace 👇🏻

{invite_link}

¡Bienvenido a ENGUERRADOS! 🚀""",

    'subscription_expired': """⚠️ Tu suscripción ha finalizado.

Para seguir teniendo acceso al canal, selecciona un nuevo plan.""",

    'subscription_expiring_soon': """⚠️ Tu período de suscripción finaliza mañana.

Fecha de finalización: {expiry_date}

Renueva ahora y sigue disfrutando del acceso al canal.""",

    'already_subscribed': """✅ Ya tienes una suscripción activa.

Acceso válido hasta: {expiry_date}

Para recibir el enlace de nuevo, usa "Obtener enlace".""",
    
    'main_menu': """📋 Inicio

Selecciona una opción:""",
    
    'admin_menu': """👨‍💼 Admin Panel

Comandos disponibles:"""
}

# Validación de configuración
def validate_config():
    """Проверка обязательных параметров конфигурации"""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не установлен")
    
    if not CHANNEL_ID:
        errors.append("CHANNEL_ID не установлен")
    
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS не установлены")
    
    if not STRIPE_API_KEY:
        errors.append("STRIPE_API_KEY не установлен")
    
    if errors:
        raise ValueError("Ошибки конфигурации:\n" + "\n".join(f"- {e}" for e in errors))
    
    return True
