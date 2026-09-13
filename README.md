# Tier List участников Telegram чата

Веб-приложение для голосования за участников чата с системой aura и tier-list категориями.

## Возможности

- 🏆 Tier-list с категориями от S (Великолепно) до G (Ужасно)
- 🗳️ Система голосования: 5 голосов, каждый восстанавливается через 3 часа
- ⚡ Aura может быть отрицательной
- 🎨 Красивый dark UI в фиолетовых тонах
- 📱 Адаптивный дизайн

## Деплой на Render.com

### 1. Подготовка

1. Установите Git: https://git-scm.com/download/win
2. Создайте репозиторий на GitHub
3. Загрузите код (см. ниже)

### 2. Настройка Render.com

1. Зарегистрируйтесь на [render.com](https://render.com)
2. Нажмите "New +" → "Web Service"
3. Подключите ваш GitHub репозиторий
4. Настройки:
   - **Name**: tier-list-chat (или любое имя)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app -c gunicorn_config.py`
   - **Instance Type**: Free

5. **Environment Variables** (очень важно!):
   - `API_ID` = ваш API ID (с https://my.telegram.org)
   - `API_HASH` = ваш API Hash
   - `PHONE` = номер телефона (например: 79123456789)
   - `CHAT_USERNAME` = @DigRock_Chat
   - `PASSWORD` = ваш 2FA пароль (если есть)

6. Нажмите "Create Web Service"

### 3. Первый запуск

После деплоя сервис автоматически:
- ✅ Запустится и будет доступен по URL
- ✅ Каждые 5 минут будет собирать участников чата
- ✅ Обновлять данные о новых участниках
- ✅ Сохранять aura при обновлениях

**Важно:** Первый сбор участников произойдёт сразу после запуска, затем каждые 5 минут автоматически.

### 4. Загрузка кода на GitHub

```bash
cd C:\Users\1\PycharmProjects\statistiics_tg

# Инициализация Git
git init

# Добавляем все файлы
git add .

# Первый коммит
git commit -m "Initial commit"

# Подключаем к GitHub (замените YOUR_USERNAME на ваш GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/telegram-tierlist.git

# Отправляем код
git branch -M main
git push -u origin main
```

## Локальный запуск

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Сбор участников чата

1. Скопируйте `config.example.py` в `config.py` и заполните данные
2. Получите API_ID и API_HASH на https://my.telegram.org
3. Запустите:

```bash
python collect_users.py
```

### Запуск сервера

```bash
python app.py
```

Откройте http://localhost:5000

## Структура проекта

- `app.py` - Flask сервер с API
- `collect_users.py` - Скрипт для сбора участников через Telethon
- `index.html` - Frontend
- `users.json` - Данные участников и aura
- `votes.json` - История голосований

## Технологии

- Backend: Flask + Python
- Frontend: Vanilla JS + CSS
- Telegram API: Telethon
- Хостинг: Render.com (бесплатно)
