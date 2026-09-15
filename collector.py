import asyncio
import os
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.photos import GetUserPhotosRequest

import db
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_ID = config.API_ID
API_HASH = config.API_HASH
PHONE = config.PHONE
PASSWORD = config.PASSWORD
CHATS = config.CHATS  # [{'slug': ..., 'username': ..., 'title': ...}, ...]

# Строка сессии берётся из config.py (SESSION_STRING). Она переживает
# пересоздание контейнера на Render и не хранится в файле session.session.
# Если SESSION_STRING пуста (например, при самом первом локальном запуске
# до того, как вы её сгенерировали) — используется локальный файл session.session.
SESSION_STRING = config.SESSION_STRING


def _make_client():
    if SESSION_STRING:
        return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    return TelegramClient('session', API_ID, API_HASH)


async def _collect_one_chat(client, chat_cfg):
    """Собирает участников одного чата и сохраняет их в Postgres.
    aura существующих пользователей не трогается — только добавляются новые."""
    slug = chat_cfg['slug']
    username = chat_cfg['username']

    if not username:
        logger.warning(f"⚠️ У чата '{slug}' не задан username, пропускаем")
        return 0

    chat_id = db.get_or_create_chat(slug, telegram_username=username, title=chat_cfg.get('title'))

    chat = await client.get_entity(username)
    participants = await client.get_participants(chat)

    os.makedirs('static/avatars', exist_ok=True)
    users_data = []

    for user in participants:
        user_id = user.id
        user_dict = {
            'id': user_id,
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'photo_url': ''
        }

        avatar_path = f'static/avatars/{user_id}.jpg'
        if not os.path.exists(avatar_path):
            try:
                photos = await client(GetUserPhotosRequest(
                    user_id=user_id, offset=0, max_id=0, limit=1
                ))
                if photos.photos:
                    file = await client.download_profile_photo(user, file=avatar_path)
                    if file:
                        user_dict['photo_url'] = f'/static/avatars/{user_id}.jpg'
            except Exception as e:
                logger.warning(f"Не удалось скачать аватарку для {user_id}: {e}")
        else:
            user_dict['photo_url'] = f'/static/avatars/{user_id}.jpg'

        users_data.append(user_dict)

    db.upsert_members(chat_id, users_data)
    logger.info(f"✅ [{slug}] собрано {len(users_data)} участников")
    return len(users_data)


async def collect_users():
    """Одной авторизованной сессией обходит все чаты из settings.CHATS."""
    try:
        logger.info("Начинаем сбор участников...")

        client = _make_client()
        await client.start(
            phone=PHONE,
            password=lambda: PASSWORD if PASSWORD else None
        )

        total = 0
        for chat_cfg in CHATS:
            try:
                total += await _collect_one_chat(client, chat_cfg)
            except Exception as e:
                logger.error(f"❌ Ошибка сбора чата '{chat_cfg.get('slug')}': {e}")

        await client.disconnect()
        return total

    except Exception as e:
        logger.error(f"❌ Ошибка при сборе участников: {e}")
        return None


async def auto_collect_loop():
    """Автоматический сбор каждые 5 минут по всем чатам сразу."""
    while True:
        try:
            count = await collect_users()
            if count is not None:
                logger.info("Следующее обновление через 5 минут...")
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Ошибка в цикле автосбора: {e}")
            await asyncio.sleep(300)


if __name__ == '__main__':
    # Для локального запуска - один раз собрать по всем настроенным чатам
    db.init_db()
    asyncio.run(collect_users())
