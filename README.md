# Tier List участников Telegram чата

Веб-приложение для голосования за участников чата с системой aura и tier-list категориями.

## Возможности

- 🏆 Tier-list с категориями от S (Великолепно) до G (Ужасно)
- 🗳️ Система голосования: 5 голосов, каждый восстанавливается через 3 часа
- ⚡ Aura может быть отрицательной
- 🎨 Красивый dark UI в фиолетовых тонах
- 📱 Адаптивный дизайн

## Деплой на Render.com

Все настройки и секреты (Telegram API, строка сессии, строка
подключения к Postgres) хранятся в одном файле `config.py`, который
не коммитится в git и на Render загружается через **Secret Files**, а
не через Environment Variables. Полный пошаговый гайд — в
[DEPLOY.md](DEPLOY.md).

Коротко:

1. Создайте репозиторий на GitHub и загрузите код (без `config.py` —
   он в `.gitignore`).
2. На [render.com](https://render.com): New + → Web Service →
   подключите репозиторий.
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app -c gunicorn_config.py`
3. Settings → Environment → Secret Files → добавьте файл с именем
   `config.py` и содержимым вашего заполненного конфига.
4. Create Web Service.

После деплоя сервис сам соберёт участников чата и будет обновлять их
каждые 5 минут; aura хранится в Postgres, поэтому не теряется при
пересоздании контейнера.

## Локальный запуск

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Сбор участников чата

1. Скопируйте `config.example.py` в `config.py` и заполните данные
   (`API_ID`, `API_HASH`, `PHONE`, `PASSWORD`, `DATABASE_URL`, `CHATS`)
2. Получите API_ID и API_HASH на https://my.telegram.org
3. Получите строку сессии: `python get_session_string.py` и вставьте
   её в `config.py` как `SESSION_STRING`
4. Запустите:

```bash
python collect_users.py
```

### Запуск сервера

```bash
python app.py
```

Откройте http://localhost:5000

## Структура проекта

- `app.py` - Flask-сервер с API
- `collector.py` - логика сбора участников через Telethon (используется и сервером, и скриптами ниже)
- `collect_users.py` - разовый ручной запуск сбора участников
- `get_session_string.py` - разовый локальный запуск для получения `SESSION_STRING`
- `db.py` - слой хранения данных (Postgres)
- `config.py` - все настройки и секреты проекта (не в git, см. DEPLOY.md)
- `config.example.py` - шаблон config.py без реальных значений
- `index.html` - Frontend

## Технологии

- Backend: Flask + Python
- Frontend: Vanilla JS + CSS
- Telegram API: Telethon
- База данных: Postgres (Neon)
- Хостинг: Render.com (бесплатно)
