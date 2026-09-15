# Деплой

## Идея

Все приватные данные (Telegram API, строка сессии, строка подключения
к Postgres) лежат в одном файле — `config.py`. Он не коммитится в git
(см. `.gitignore`). На Render этот файл загружается не через
Environment Variables, а через **Secret Files** — Render сам кладёт
его в корень проекта перед стартом контейнера, и `import config`
работает точно так же, как при локальном запуске.

Единственное исключение — переменная `PORT`: её значение назначает
сам Render динамически при каждом запуске, это не секрет и не наши
данные, а требование платформы. Она остаётся как есть в
`gunicorn_config.py`.

## 1. Заполнить config.py

Скопируйте `config.example.py` в `config.py` и впишите реальные
значения:

- `API_ID`, `API_HASH`, `PHONE`, `PASSWORD` — с https://my.telegram.org
  и от аккаунта-коллектора.
- `DATABASE_URL` — строка подключения к Postgres (например, из
  [Neon](https://neon.tech): Create project → Connection Details →
  скопировать `DATABASE_URL` вида
  `postgresql://user:password@ep-xxxx.aws.neon.tech/dbname?sslmode=require`).
- `CHATS` — список чатов, которые обслуживает сервер.
- `SESSION_STRING` — оставьте пустым, получим на следующем шаге.

## 2. Получить строку сессии

Локально, один раз:

```bash
pip install -r requirements.txt
python get_session_string.py
```

Скрипт запросит номер телефона, код из Telegram и (если включена)
пароль 2FA, а затем напечатает строку — вставьте её в `config.py` как
значение `SESSION_STRING`.

## 3. Настроить Render.com

1. Зарегистрируйтесь на [render.com](https://render.com), New + → Web
   Service, подключите GitHub-репозиторий.
2. Настройки сервиса:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app -c gunicorn_config.py`
   - **Instance Type**: Free
3. **Settings → Environment → Secret Files → + Add Secret File**:
   - **Filename**: `config.py`
   - **Contents**: вставьте содержимое своего заполненного `config.py`
     целиком.
   - Save Changes — Render запустит новый деплой и положит файл в
     корень проекта.
4. Create Web Service.

Никаких Environment Variables добавлять не нужно — все данные уже в
секретном файле `config.py`.

## 4. Первый запуск

После деплоя сервис:
- запустится и будет доступен по URL;
- сразу соберёт участников чата и будет обновлять список каждые 5 минут;
- при повторных голосованиях будет сохранять aura в Postgres —
  на бесплатном плане Render диск контейнера не персистентный, но
  база данных живёт отдельно от контейнера, так что данные не теряются.

## Обновление config.py

Если нужно поменять данные (например, добавить чат в `CHATS` или
обновить `SESSION_STRING`) — отредактируйте Secret File в Render
(Settings → Environment → Secret Files → config.py → Edit) и
сохраните: Render передеплоит сервис с новым содержимым файла.
