from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import threading
import asyncio
import logging

import db
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# chat_id (в базе) по slug (из config.CHATS), заполняется при старте
_chat_ids_by_slug = {}


def default_slug():
    return config.CHATS[0]['slug']


def resolve_chat_id(slug):
    if slug not in _chat_ids_by_slug:
        raise KeyError(slug)
    return _chat_ids_by_slug[slug]


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


@app.route('/api/chats', methods=['GET'])
def list_chats():
    """Список чатов, которые обслуживает этот сервер (для будущего переключателя чатов)."""
    return jsonify([
        {'slug': c['slug'], 'title': c.get('title') or c['slug']}
        for c in config.CHATS
    ])


@app.route('/api/users', methods=['GET'])
def get_users():
    slug = request.args.get('chat', default_slug())
    try:
        chat_id = resolve_chat_id(slug)
    except KeyError:
        return jsonify({'error': f'Неизвестный чат: {slug}'}), 404

    return jsonify(db.get_users(chat_id))


@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.json or {}
    slug = data.get('chat', default_slug())
    try:
        chat_id = resolve_chat_id(slug)
    except KeyError:
        return jsonify({'error': f'Неизвестный чат: {slug}'}), 404

    user_id = data.get('user_id')
    voter_id = data.get('voter_id')
    amount = data.get('amount', 100)

    if user_id is None or not voter_id:
        return jsonify({'error': 'user_id и voter_id обязательны'}), 400

    # Фронтенд всегда шлёт +100/-100, но amount приходит от клиента,
    # так что не доверяем ему напрямую — приводим к ближайшему из двух значений.
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return jsonify({'error': 'некорректный amount'}), 400
    amount = 100 if amount >= 0 else -100

    existing = db.get_vote_for_target(chat_id, voter_id, user_id)
    if existing:
        return jsonify({
            'error': f"Вы уже голосовали за этого участника. "
                     f"Следующий голос через {existing['minutes_left']} минут"
        }), 429

    active_votes = db.get_active_votes(chat_id, voter_id)
    if len(active_votes) >= 5:
        next_available = min(active_votes, key=lambda v: v['minutes_left'])
        return jsonify({
            'error': f"Все 5 голосов использованы. "
                     f"Следующий голос через {next_available['minutes_left']} минут"
        }), 429

    try:
        new_aura = db.cast_vote(chat_id, voter_id, user_id, amount)
    except ValueError:
        return jsonify({'error': 'Пользователь не найден'}), 404

    votes_left = 5 - len(active_votes) - 1

    return jsonify({
        'success': True,
        'new_aura': new_aura,
        'votes_left': votes_left
    })


@app.route('/api/can_vote', methods=['POST'])
def can_vote():
    data = request.json or {}
    slug = data.get('chat', default_slug())
    try:
        chat_id = resolve_chat_id(slug)
    except KeyError:
        return jsonify({'error': f'Неизвестный чат: {slug}'}), 404

    voter_id = data.get('voter_id')
    if not voter_id:
        return jsonify({'error': 'voter_id обязателен'}), 400

    active_votes = db.get_active_votes(chat_id, voter_id)
    votes_available = 5 - len(active_votes)

    return jsonify({
        'can_vote': votes_available > 0,
        'votes_available': votes_available,
        'votes_details': active_votes
    })


def _bootstrap_chats():
    """Создаёт таблицы и регистрирует чаты из config.CHATS при старте приложения.
    Выполняется на уровне модуля, а не только в блоке __main__, потому что
    gunicorn импортирует app.py напрямую (app:app) и __main__ не запускается."""
    db.init_db()
    for chat in config.CHATS:
        chat_id = db.get_or_create_chat(
            chat['slug'], telegram_username=chat.get('username'), title=chat.get('title')
        )
        _chat_ids_by_slug[chat['slug']] = chat_id
    logger.info(f"Зарегистрированы чаты: {list(_chat_ids_by_slug.keys())}")


_bootstrap_chats()

if __name__ == '__main__':
    os.makedirs('static/avatars', exist_ok=True)

    # Запускаем автосбор участников в отдельном потоке.
    # На проде (gunicorn) этот же collector запускается через хук when_ready
    # в gunicorn_config.py — см. этот файл.
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
        logger.warning(f"⚠️ Автосбор участников не запущен: {e}")

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
