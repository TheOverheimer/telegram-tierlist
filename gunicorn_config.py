import os
import sys
import threading
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def when_ready(server):
    """Вызывается когда Gunicorn готов принимать запросы"""
    logger.info("🚀 Gunicorn запущен, инициализация автосбора...")

    try:
        from collector import auto_collect_loop

        def run_collector():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(auto_collect_loop())

        collector_thread = threading.Thread(target=run_collector, daemon=True)
        collector_thread.start()
        logger.info("✅ Автосбор участников запущен (каждые 5 минут)")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить автосбор: {e}")

# Gunicorn конфигурация
# PORT — единственная переменная окружения, которая осталась: её задаёт
# сам Render динамически при каждом запуске контейнера, это не секрет и
# не наши данные, а требование платформы, поэтому вынести её в config.py
# нельзя (там просто нет актуального значения на момент старта).
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1
threads = 2
worker_class = "sync"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
