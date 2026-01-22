# -*- coding: utf-8 -*-
"""
Автоматическая проверка истёкших подписок каждые 30 секунд.
Для тестирования. В продакшене использовать крон.
"""
import asyncio
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_checks():
    """Запускать проверку каждые 30 секунд"""
    from check_subscriptions import check_and_remove_expired
    
    logger.info("Автоматическая проверка запущена (каждые 30 секунд)")
    
    while True:
        try:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Проверка истёкших подписок...")
            await check_and_remove_expired()
            logger.info("Проверка завершена. Следующая через 30 секунд.")
        except Exception as e:
            logger.error(f"Ошибка при проверке: {e}")
        
        await asyncio.sleep(30)  # 30 секунд

def main():
    """Точка входа"""
    import config
    config.validate_config()
    
    logger.info("="*60)
    logger.info("АВТОПРОВЕРКА ПОДПИСОК")
    logger.info("="*60)
    logger.info("Интервал: 30 секунд")
    logger.info("Для остановки: Ctrl+C")
    logger.info("="*60)
    
    try:
        asyncio.run(run_checks())
    except KeyboardInterrupt:
        logger.info("\nАвтопроверка остановлена")

if __name__ == '__main__':
    main()
