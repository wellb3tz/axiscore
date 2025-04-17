import os
import psycopg2
from psycopg2.errors import UniqueViolation
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests
import hashlib
import hmac
import time
from dotenv import load_dotenv
from flask_socketio import SocketIO, send, emit
from routes.inventory import inventory_bp
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['SECRET_KEY'] = 'your_secret_key'
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Register blueprints
app.register_blueprint(inventory_bp)

DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_SECRET = TELEGRAM_BOT_TOKEN.split(':')[1]

def check_telegram_auth(data):
    check_hash = data.pop('hash')
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(TELEGRAM_BOT_SECRET.encode()).digest()
    hmac_string = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac_string == check_hash

@app.route('/register', methods=['POST'])
def register():
    try:
        telegram_id = request.json.get('telegram_id')
        username = request.json.get('username')
        password = request.json.get('password')
        
        # Allow multiple accounts with the same Telegram ID
        cursor.execute("INSERT INTO users (telegram_id, username, password) VALUES (%s, %s, %s)", (telegram_id, username, password))
        conn.commit()
        return jsonify({"msg": "User registered successfully"}), 200
    except UniqueViolation:
        conn.rollback()  # Rollback the transaction on error
        return jsonify({"msg": "User already exists"}), 400
    except Exception as e:
        conn.rollback()  # Rollback the transaction on error
        return jsonify({"msg": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.json.get('username')
        password = request.json.get('password')
        
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if not user:
            return jsonify({"msg": "Bad username or password"}), 401
        
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200
    except Exception as e:
        conn.rollback()  # Rollback the transaction on error
        return jsonify({"msg": str(e)}), 500

@app.route('/telegram_auth', methods=['POST'])
def telegram_auth():
    auth_data = request.json
    if not check_telegram_auth(auth_data):
        return jsonify({"msg": "Telegram authentication failed"}), 401

    telegram_id = auth_data['id']
    username = auth_data['username']

    cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (telegram_id, username, password) VALUES (%s, %s, %s)", (telegram_id, username, ''))
        conn.commit()

    access_token = create_access_token(identity=telegram_id)
    return jsonify(access_token=access_token), 200

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    chat_id = data['message']['chat']['id']
    text = data['message']['text']
    
    # Respond to the message
    response_text = f"Received your message: {text}"
    send_message(chat_id, response_text)
    
    return jsonify({"status": "ok"}), 200

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    requests.post(url, json=payload)

@socketio.on('message')
def handle_message(msg):
    send(msg, broadcast=True)

online_users = {}

@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('user_id')
    online_users[user_id] = request.sid
    emit_online_users()

@socketio.on('disconnect')
def handle_disconnect():
    user_id = None
    for uid, sid in online_users.items():
        if sid == request.sid:
            user_id = uid
            break
    if user_id:
        del online_users[user_id]
    emit_online_users()

def emit_online_users():
    emit('online_users', {'onlineUsers': len(online_users)}, broadcast=True)

@app.route('/online-users', methods=['GET'])
def get_online_users():
    return jsonify({"onlineUsers": len(online_users)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)