"""
Слой хранения данных поверх обычного Postgres (Neon / Supabase / любой другой).

Раньше данные лежали в users.json и votes.json прямо на диске контейнера —
на бесплатном Render такой диск не сохраняется между рестартами (сон/пробуждение,
редеплой), поэтому голоса и аура пропадали. Теперь всё живёт во внешней БД,
которая не зависит от жизненного цикла контейнера Render.

Заодно данные с самого начала разложены по чатам (таблица chats), чтобы
подключить второй, третий и т.д. чат в будущем можно было без миграций схемы —
достаточно добавить чат в config.CHATS.
"""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

import config

DATABASE_URL = config.DATABASE_URL


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL не задан. Укажите строку подключения к Postgres "
            "(например, из Neon) в переменных окружения — см. DEPLOY.md."
        )
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Создаёт таблицы, если их ещё нет. Безопасно вызывать при каждом старте."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id SERIAL PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    telegram_username TEXT,
                    title TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS members (
                    id SERIAL PRIMARY KEY,
                    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    telegram_user_id BIGINT NOT NULL,
                    username TEXT DEFAULT '',
                    first_name TEXT DEFAULT '',
                    last_name TEXT DEFAULT '',
                    aura INTEGER NOT NULL DEFAULT 0,
                    photo_url TEXT DEFAULT '',
                    updated_at TIMESTAMPTZ DEFAULT now(),
                    UNIQUE (chat_id, telegram_user_id)
                );

                CREATE TABLE IF NOT EXISTS votes (
                    id SERIAL PRIMARY KEY,
                    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    voter_id TEXT NOT NULL,
                    target_telegram_user_id BIGINT NOT NULL,
                    voted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (chat_id, voter_id, target_telegram_user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_members_chat_aura
                    ON members (chat_id, aura DESC);
                CREATE INDEX IF NOT EXISTS idx_votes_voter
                    ON votes (chat_id, voter_id, voted_at);
            """)


def get_or_create_chat(slug, telegram_username=None, title=None):
    """Находит чат по slug или создаёт новую запись — так добавление чата
    в settings.CHATS не требует ручных миграций базы."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM chats WHERE slug = %s", (slug,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE chats SET telegram_username = %s, "
                    "title = COALESCE(%s, title) WHERE id = %s",
                    (telegram_username, title, row['id'])
                )
                return row['id']
            cur.execute(
                "INSERT INTO chats (slug, telegram_username, title) "
                "VALUES (%s, %s, %s) RETURNING id",
                (slug, telegram_username, title)
            )
            return cur.fetchone()['id']


def upsert_members(chat_id, users):
    """
    users: список dict с ключами id, username, first_name, last_name, photo_url.
    aura существующих пользователей не трогаем — новые получают aura = 0.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            for u in users:
                cur.execute("""
                    INSERT INTO members
                        (chat_id, telegram_user_id, username, first_name, last_name, photo_url, aura, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 0, now())
                    ON CONFLICT (chat_id, telegram_user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        photo_url = CASE
                            WHEN EXCLUDED.photo_url = '' THEN members.photo_url
                            ELSE EXCLUDED.photo_url
                        END,
                        updated_at = now()
                """, (chat_id, u['id'], u.get('username', ''), u.get('first_name', ''),
                      u.get('last_name', ''), u.get('photo_url', '')))


def get_users(chat_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT telegram_user_id AS id, username, first_name, last_name, aura, photo_url
                FROM members
                WHERE chat_id = %s
                ORDER BY aura DESC
            """, (chat_id,))
            return [dict(r) for r in cur.fetchall()]


def get_active_votes(chat_id, voter_id):
    """Голоса voter_id за последние 3 часа: [{user_id, minutes_left}, ...]."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT target_telegram_user_id AS user_id,
                       GREATEST(0, CEIL(EXTRACT(EPOCH FROM
                           (voted_at + interval '3 hours' - now())) / 60))::int AS minutes_left
                FROM votes
                WHERE chat_id = %s AND voter_id = %s
                  AND voted_at > now() - interval '3 hours'
                ORDER BY voted_at
            """, (chat_id, voter_id))
            return [dict(r) for r in cur.fetchall()]


def get_vote_for_target(chat_id, voter_id, target_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT GREATEST(0, CEIL(EXTRACT(EPOCH FROM
                           (voted_at + interval '3 hours' - now())) / 60))::int AS minutes_left
                FROM votes
                WHERE chat_id = %s AND voter_id = %s AND target_telegram_user_id = %s
                  AND voted_at > now() - interval '3 hours'
            """, (chat_id, voter_id, target_id))
            return cur.fetchone()


def cast_vote(chat_id, voter_id, target_id, amount):
    """Начисляет aura и фиксирует голос в одной транзакции. Возвращает новую aura."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                UPDATE members SET aura = aura + %s, updated_at = now()
                WHERE chat_id = %s AND telegram_user_id = %s
                RETURNING aura
            """, (amount, chat_id, target_id))
            row = cur.fetchone()
            if not row:
                raise ValueError('user_not_found')

            cur.execute("""
                INSERT INTO votes (chat_id, voter_id, target_telegram_user_id, voted_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (chat_id, voter_id, target_telegram_user_id)
                DO UPDATE SET voted_at = now()
            """, (chat_id, voter_id, target_id))

            return row['aura']
