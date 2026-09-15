"""
Разовый сбор участников (без цикла на 5 минут). Логика та же, что в
collector.py — просто удобный отдельный вход для ручного запуска:

    python collect_users.py
"""
import asyncio

import db
from collector import collect_users

if __name__ == '__main__':
    db.init_db()
    count = asyncio.run(collect_users())
    print(f"Собрано участников: {count}")
