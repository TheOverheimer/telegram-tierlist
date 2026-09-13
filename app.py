from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
import threading
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

USERS_FILE = 'users.json'
VOTES_FILE = 'votes.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_votes():
    if os.path.exists(VOTES_FILE):
        with open(VOTES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Миграция старого формата в новый
            if data and isinstance(list(data.values())[0] if data else None, str):
                return {}
            return data
    return {}

def save_votes(votes):
    with open(VOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(votes, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/users', methods=['GET'])
def get_users():
    users = load_users()
    users_sorted = sorted(users, key=lambda x: x['aura'], reverse=True)
    return jsonify(users_sorted)

@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.json
    user_id = data.get('user_id')
    voter_id = data.get('voter_id')
    amount = data.get('amount', 100)

    votes = load_votes()

    # Инициализация структуры голосов для пользователя
    if voter_id not in votes:
        votes[voter_id] = {}

    # Проверка, не голосовал ли уже за этого участника
    if str(user_id) in votes[voter_id]:
        last_vote_time = datetime.fromisoformat(votes[voter_id][str(user_id)])
        time_diff = datetime.now() - last_vote_time

        if time_diff < timedelta(hours=3):
            remaining = timedelta(hours=3) - time_diff
            minutes = int(remaining.total_seconds() / 60)
            return jsonify({'error': f'Вы уже голосовали за этого участника. Следующий голос через {minutes} минут'}), 429

    # Проверка количества доступных голосов
    now = datetime.now()
    active_votes = []

    for target_user_id, vote_time in votes[voter_id].items():
        vote_datetime = datetime.fromisoformat(vote_time)
        if now - vote_datetime < timedelta(hours=3):
            active_votes.append({
                'user_id': target_user_id,
                'time_left': timedelta(hours=3) - (now - vote_datetime)
            })

    if len(active_votes) >= 5:
        # Все 5 голосов использованы
        next_available = min(active_votes, key=lambda x: x['time_left'])
        minutes = int(next_available['time_left'].total_seconds() / 60)
        return jsonify({'error': f'Все 5 голосов использованы. Следующий голос через {minutes} минут'}), 429

    users = load_users()
    user_found = False

    for user in users:
        if user['id'] == user_id:
            user['aura'] += amount
            user_found = True
            break

    if not user_found:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Сохраняем голос за конкретного пользователя
    votes[voter_id][str(user_id)] = now.isoformat()

    save_users(users)
    save_votes(votes)

    available_votes = 5 - len(active_votes) - 1

    return jsonify({
        'success': True,
        'new_aura': user['aura'],
        'votes_left': available_votes
    })

@app.route('/api/can_vote', methods=['POST'])
def can_vote():
    data = request.json
    voter_id = data.get('voter_id')

    votes = load_votes()

    if voter_id not in votes:
        return jsonify({
            'can_vote': True,
            'votes_available': 5,
            'votes_details': []
        })

    now = datetime.now()
    active_votes = []

    for target_user_id, vote_time in votes[voter_id].items():
        vote_datetime = datetime.fromisoformat(vote_time)
        time_diff = now - vote_datetime

        if time_diff < timedelta(hours=3):
            remaining = timedelta(hours=3) - time_diff
            minutes = int(remaining.total_seconds / 60)
            active_votes.append({
                'user_id': target_user_id,
                'minutes_left': minutes
            })

    votes_available = 5 - len(active_votes)

    return jsonify({
        'can_vote': votes_available > 0,
        'votes_available': votes_available,
        'votes_details': active_votes
    })

if __name__ == '__main__':
    os.makedirs('static/avatars', exist_ok=True)

    # Запускаем автосбор участников в отдельном потоке
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
