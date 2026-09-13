import asyncio
import json
import os
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.photos import GetUserPhotosRequest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Попытка импорта конфига
try:
    from config import API_ID, API_HASH, PHONE, CHAT_USERNAME, PASSWORD
except ImportError:
    # Для деплоя - берём из переменных окружения
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH')
    PHONE = os.environ.get('PHONE')
    CHAT_USERNAME = os.environ.get('CHAT_USERNAME')
    PASSWORD = os.environ.get('PASSWORD', '')

USERS_FILE = 'users.json'

async def collect_users():
    """Собирает участников чата и обновляет users.json"""
    try:
        logger.info("Начинаем сбор участников...")

        client = TelegramClient('session', API_ID, API_HASH)

        await client.start(
            phone=PHONE,
            password=lambda: PASSWORD if PASSWORD else None
        )

        chat = await client.get_entity(CHAT_USERNAME)
        participants = await client.get_participants(chat)

        # Загружаем существующие данные для сохранения aura
        existing_users = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_users = {u['id']: u for u in existing_data}

        os.makedirs('static/avatars', exist_ok=True)
        users_data = []

        for user in participants:
            user_id = user.id

            # Сохраняем aura, если пользователь уже существует
            existing_aura = existing_users.get(user_id, {}).get('aura', 0)

            user_dict = {
                'id': user_id,
                'username': user.username or '',
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'aura': existing_aura,  # Сохраняем старую aura
                'photo_url': ''
            }

            # Скачиваем аватарку только если её ещё нет
            avatar_path = f'static/avatars/{user_id}.jpg'
            if not os.path.exists(avatar_path):
                try:
                    photos = await client(GetUserPhotosRequest(
                        user_id=user_id,
                        offset=0,
                        max_id=0,
                        limit=1
                    ))

                    if photos.photos:
                        file = await client.download_profile_photo(
                            user,
                            file=avatar_path
                        )
                        if file:
                            user_dict['photo_url'] = f'/static/avatars/{user_id}.jpg'
                except Exception as e:
                    logger.warning(f"Не удалось скачать аватарку для {user_id}: {e}")
            else:
                user_dict['photo_url'] = f'/static/avatars/{user_id}.jpg'

            users_data.append(user_dict)

        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Собрано {len(users_data)} пользователей")
        await client.disconnect()

        return len(users_data)

    except Exception as e:
        logger.error(f"❌ Ошибка при сборе участников: {e}")
        return None

async def auto_collect_loop():
    """Автоматический сбор каждые 5 минут"""
    while True:
        try:
            count = await collect_users()
            if count is not None:
                logger.info(f"Следующее обновление через 5 минут...")
            await asyncio.sleep(300)  # 5 минут
        except Exception as e:
            logger.error(f"Ошибка в цикле автосбора: {e}")
            await asyncio.sleep(300)

if __name__ == '__main__':
    # Для локального запуска - один раз собрать
    asyncio.run(collect_users())
