import asyncio
import json
import os
from telethon import TelegramClient
from telethon.tl.functions.photos import GetUserPhotosRequest
from config import API_ID, API_HASH, PHONE, CHAT_USERNAME, PASSWORD

async def collect_users():
    client = TelegramClient('session', API_ID, API_HASH)

    os.makedirs('static/avatars', exist_ok=True)

    await client.start(
        phone=PHONE,
        password=lambda: PASSWORD if PASSWORD else None
    )

    chat = await client.get_entity(CHAT_USERNAME)
    participants = await client.get_participants(chat)

    users_data = []

    for user in participants:
        user_dict = {
            'id': user.id,
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'aura': 0,
            'photo_url': ''
        }

        try:
            photos = await client(GetUserPhotosRequest(
                user_id=user.id,
                offset=0,
                max_id=0,
                limit=1
            ))

            if photos.photos:
                photo = photos.photos[0]
                file = await client.download_profile_photo(user, file=f'static/avatars/{user.id}.jpg')
                if file:
                    user_dict['photo_url'] = f'/static/avatars/{user.id}.jpg'
        except:
            pass

        users_data.append(user_dict)

    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

    print(f"Собрано {len(users_data)} пользователей")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(collect_users())
