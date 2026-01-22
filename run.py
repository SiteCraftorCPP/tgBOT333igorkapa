# -*- coding: utf-8 -*-
"""
Единый скрипт запуска бота и webhook сервера в отдельных процессах
"""
import subprocess
import sys
import time
import os

def main():
    print("="*60)
    print("ENGUERRADOS Telegram Bot - Запуск")
    print("="*60)
    print()
    
    # Проверка конфигурации
    try:
        import config
        config.validate_config()
        print("✓ Конфигурация проверена")
    except Exception as e:
        print(f"✗ Ошибка конфигурации: {e}")
        sys.exit(1)
    
    # Инициализация БД
    try:
        import database as db
        db.init_db()
        print("✓ База данных инициализирована")
    except Exception as e:
        print(f"✗ Ошибка БД: {e}")
        sys.exit(1)
    
    print()
    print("Запуск сервисов...")
    print()
    
    processes = []
    
    try:
        # Запуск Telegram бота
        print("[1/2] Запуск Telegram бота...")
        bot_process = subprocess.Popen(
            [sys.executable, "bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        processes.append(("Telegram Bot", bot_process))
        time.sleep(2)
        
        # Запуск Webhook сервера
        print("[2/2] Запуск Webhook сервера...")
        webhook_process = subprocess.Popen(
            [sys.executable, "webhook_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        processes.append(("Webhook Server", webhook_process))
        time.sleep(2)
        
        print()
        print("="*60)
        print("✓ Все сервисы запущены!")
        print()
        print("Telegram Bot: работает")
        print("Webhook Server: http://localhost:8080")
        print()
        print("Нажмите Ctrl+C для остановки")
        print("="*60)
        print()
        
        # Ждём завершения
        while True:
            time.sleep(1)
            
            # Проверяем, что процессы живы
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n✗ {name} остановлен (код: {proc.returncode})")
                    raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        print("\n\nОстановка сервисов...")
        for name, proc in processes:
            print(f"  Останавливаю {name}...")
            proc.terminate()
            proc.wait()
        print("\n✓ Все сервисы остановлены")

if __name__ == '__main__':
    main()
