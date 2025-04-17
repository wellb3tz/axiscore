import os
import psycopg2
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests
import hashlib
import hmac
import json
from dotenv import load_dotenv
from flask_cors import CORS
import urllib.parse
import socket
import re
import shutil

# Load environment variables from .env file
load_dotenv()

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend/build')
CORS(app)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
jwt = JWTManager(app)

DATABASE_URL = os.getenv('DATABASE_URL')

# Extract host from DATABASE_URL to resolve to IPv4 address
if DATABASE_URL:
    host_match = re.search(r'@([^:]+):', DATABASE_URL)
    if host_match:
        hostname = host_match.group(1)
        try:
            # Get the IPv4 address
            host_ip = socket.gethostbyname(hostname)
            # Replace the hostname with the IP address
            DATABASE_URL = DATABASE_URL.replace('@' + hostname + ':', '@' + host_ip + ':')
        except socket.gaierror:
            print(f"Could not resolve hostname {hostname}")

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    # Create models table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id SERIAL PRIMARY KEY,
            telegram_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id TEXT NOT NULL UNIQUE,
            username TEXT,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    print("Successfully connected to database and initialized tables")
except psycopg2.OperationalError as e:
    print(f"Error connecting to database: {e}")
    # If in development, raise the error; in production, continue with limited functionality
    if os.getenv('FLASK_ENV') == 'development':
        raise
    else:
        conn = None
        cursor = None
        print("Running with limited functionality - database features will be unavailable")

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_SECRET = TELEGRAM_BOT_TOKEN.split(':')[1] if TELEGRAM_BOT_TOKEN else ""

def check_telegram_auth(data):
    check_hash = data.pop('hash')
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(TELEGRAM_BOT_SECRET.encode()).digest()
    hmac_string = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac_string == check_hash

@app.route('/telegram_auth', methods=['POST'])
def telegram_auth():
    auth_data = request.json
    if not check_telegram_auth(auth_data):
        return jsonify({"msg": "Telegram authentication failed"}), 401

    telegram_id = auth_data['id']
    username = auth_data.get('username', '')

    # Check if database connection exists
    if conn and cursor:
        try:
            # Check if user exists, create if not
            cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            user = cursor.fetchone()
            if not user:
                cursor.execute("INSERT INTO users (telegram_id, username, password) VALUES (%s, %s, %s)", 
                              (telegram_id, username, ''))
                conn.commit()
        except Exception as e:
            print(f"Database error in telegram_auth: {e}")
    
    access_token = create_access_token(identity=telegram_id)
    return jsonify(access_token=access_token), 200

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    # If it's a GET request, just return a simple status
    if request.method == 'GET':
        return jsonify({
            "status": "online",
            "message": "Telegram webhook is active. Please use POST requests for webhook communication."
        })
    
    # Handle POST request (actual webhook)
    data = request.json
    
    # Extract message data
    message = data.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')
    
    if not chat_id:
        return jsonify({"status": "error", "msg": "No chat_id found"}), 400
    
    # Check if message contains a document (file)
    if message.get('document'):
        document = message.get('document')
        file_name = document.get('file_name', '')
        file_id = document.get('file_id')
        mime_type = document.get('mime_type', '')
        
        # Check if it's a 3D model file
        if file_name.lower().endswith(('.glb', '.gltf')) or 'model' in mime_type.lower():
            # Download file from Telegram
            try:
                file_path = download_telegram_file(file_id)
                if file_path:
                    # Save to storage and get URL
                    model_url = save_model_to_storage(file_path, file_name, chat_id)
                    
                    # Get the bot username for creating the Mini App URL
                    bot_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
                    bot_info = requests.get(bot_info_url).json()
                    bot_username = bot_info.get('result', {}).get('username', '')
                    
                    # Create a web app URL that works in both Telegram and browser
                    model_param = urllib.parse.quote(model_url)
                    
                    # Direct web URL for browser access
                    direct_url = f"{request.url_root}miniapp?model={model_param}"
                    
                    # Use Telegram's t.me format with web app
                    # The format should be: https://t.me/BOT_USERNAME/app
                    # Where "app" should match your Mini App short_name in BotFather
                    miniapp_url = f"https://t.me/{bot_username}/app?startapp=model__{model_param}"
                    
                    # For debugging, log the URL
                    print(f"Generated Mini App URL: {miniapp_url}")
                    
                    # Send message with both options
                    response_text = f"3D model received: {file_name}\n\nUse the button below to view it in Telegram:"
                    
                    # Send inline button to open in Axiscore
                    keyboard = {
                        'inline_keyboard': [
                            [
                                {
                                    'text': 'Open in Axiscore',
                                    'url': miniapp_url
                                }
                            ],
                            [
                                {
                                    'text': 'Open in Browser',
                                    'url': direct_url
                                }
                            ]
                        ]
                    }
                    
                    # Send the message with keyboard
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': response_text,
                        'reply_markup': keyboard
                    }
                    requests.post(url, json=payload)
                    
                    return jsonify({"status": "ok"}), 200
                else:
                    send_message(chat_id, "Failed to download your file. Please try again.")
            except Exception as e:
                print(f"Error processing 3D model: {e}")
                send_message(chat_id, "Failed to process your 3D model. Please try again.")
        else:
            send_message(chat_id, "Please send a 3D model file (.glb or .gltf).")
    # Handle text messages
    else:
        # Check for specific commands
        if text.lower() == '/start':
            response_text = "Welcome to Axiscore 3D Model Viewer! You can send me a 3D model file (.glb or .gltf) and I'll generate an interactive preview for you."
        elif text.lower() == '/help':
            response_text = """
Axiscore 3D Model Viewer Help:
• Send a 3D model file (.glb or .gltf) directly to this chat
• I'll create an interactive viewer link
• Click "Open in Axiscore" to view and interact with your model
• Use pinch/scroll to zoom, drag to rotate
• You can download the original model from the viewer
            """
        else:
            # Generic response for other messages
            response_text = f"Send me a 3D model file (.glb or .gltf) to view it in Axiscore. You said: {text}"
        
        send_message(chat_id, response_text)
    
    return jsonify({"status": "ok"}), 200

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    requests.post(url, json=payload)

def send_inline_button(chat_id, text, button_text, button_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': {
            'inline_keyboard': [[{
                'text': button_text,
                'url': button_url
            }]]
        }
    }
    requests.post(url, json=payload)

@app.route('/view', methods=['GET'])
def view_model():
    model_url = request.args.get('model')
    if not model_url:
        return "No model URL provided", 400
    
    # Return HTML page with embedded model viewer
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>3D Model Viewer</title>
        <style>
            body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }}
            #model-container {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div id="model-container"></div>
        <script src="https://unpkg.com/three@0.132.2/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/GLTFLoader.js"></script>
        <script>
            const container = document.getElementById('model-container');
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);
            
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.z = 5;
            
            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            container.appendChild(renderer.domElement);
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1);
            scene.add(directionalLight);
            
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.25;
            
            const loader = new THREE.GLTFLoader();
            loader.load(
                '{model_url}',
                (gltf) => {{
                    // Center model
                    const box = new THREE.Box3().setFromObject(gltf.scene);
                    const center = box.getCenter(new THREE.Vector3());
                    const size = box.getSize(new THREE.Vector3());
                    
                    gltf.scene.position.x = -center.x;
                    gltf.scene.position.y = -center.y;
                    gltf.scene.position.z = -center.z;
                    
                    // Adjust camera
                    const maxDim = Math.max(size.x, size.y, size.z);
                    const fov = camera.fov * (Math.PI / 180);
                    const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
                    
                    camera.position.z = cameraDistance * 1.5;
                    camera.updateProjectionMatrix();
                    
                    scene.add(gltf.scene);
                }},
                (xhr) => {{
                    console.log((xhr.loaded / xhr.total) * 100 + '% loaded');
                }},
                (error) => {{
                    console.error('Error loading model:', error);
                    document.body.innerHTML = '<div style="color: red; padding: 20px;">Error loading model: ' + error.message + '</div>';
                }}
            );
            
            window.addEventListener('resize', () => {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
            
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }}
            
            animate();
        </script>
    </body>
    </html>
    """
    
    return html

@app.route('/models', methods=['GET'])
@jwt_required()
def get_models():
    telegram_id = get_jwt_identity()
    
    # If database connection is not available
    if not conn or not cursor:
        return jsonify({"error": "Database connection not available"}), 503
    
    try:
        cursor.execute("SELECT id, model_name, model_url, created_at FROM models WHERE telegram_id = %s", (telegram_id,))
        models = cursor.fetchall()
        
        model_list = []
        for model in models:
            model_list.append({
                "id": model[0],
                "name": model[1],
                "url": model[2],
                "created_at": model[3].isoformat() if model[3] else None
            })
        
        return jsonify(models=model_list), 200
    except Exception as e:
        print(f"Database error in get_models: {e}")
        return jsonify({"error": "Database error occurred"}), 500

@app.route('/models', methods=['POST'])
@jwt_required()
def add_model():
    telegram_id = get_jwt_identity()
    
    if not request.json or not 'model_url' in request.json:
        return jsonify({"msg": "Missing model URL"}), 400
    
    model_url = request.json['model_url']
    model_name = request.json.get('model_name', os.path.basename(urllib.parse.urlparse(model_url).path))
    
    # If database connection is not available
    if not conn or not cursor:
        return jsonify({"error": "Database connection not available"}), 503
    
    try:
        cursor.execute(
            "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s) RETURNING id",
            (telegram_id, model_name, model_url)
        )
        model_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "id": model_id,
            "name": model_name,
            "url": model_url
        }), 201
    except Exception as e:
        print(f"Database error in add_model: {e}")
        return jsonify({"error": "Database error occurred"}), 500

@app.route('/favicon.ico')
def favicon():
    # Return a 204 No Content response
    return '', 204

@app.route('/models/<filename>', methods=['GET'])
def serve_model(filename):
    """Serve uploaded 3D model files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/miniapp')
@app.route('/miniapp/')
def miniapp():
    """Serve the MiniApp React frontend."""
    # Redirect to the frontend for handling
    return send_file('../frontend/build/index.html')

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "3D Model Viewer API is running"
    })

def download_telegram_file(file_id):
    """Download a file from Telegram servers using its file_id."""
    # Get file path from Telegram
    file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    file_info_response = requests.get(file_info_url)
    file_info = file_info_response.json()
    
    if file_info.get('ok'):
        telegram_file_path = file_info['result']['file_path']
        # Download file from Telegram
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{telegram_file_path}"
        response = requests.get(download_url)
        
        # Create local path - store in uploads folder with unique filename
        local_filename = f"{file_id}_{os.path.basename(telegram_file_path)}"
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], local_filename)
        
        # Save file locally
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        print(f"File downloaded and saved to {local_path}")
        return local_filename  # Return just the filename, not the full path
    else:
        print(f"Error getting file info: {file_info}")
        return None

def save_model_to_storage(file_path, file_name, user_id):
    """Save model information to database and return public URL."""
    # For this example, we'll serve files directly from our uploads folder
    
    # Save reference in the database
    if conn and cursor:
        try:
            # Get public URL for the file
            model_url = f"{request.url_root}models/{file_path}"
            
            cursor.execute(
                "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s) RETURNING id",
                (user_id, file_name, model_url)
            )
            model_id = cursor.fetchone()[0]
            conn.commit()
            
            print(f"Model saved to database with ID {model_id}")
            return model_url
        except Exception as e:
            print(f"Database error in save_model_to_storage: {e}")
    
    # Fallback: direct file path if database saving fails
    return f"{request.url_root}models/{file_path}"

# Serve React static files
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('../frontend/build/static', path)

@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route to support React Router."""
    if path.startswith('api/') or path.startswith('models/'):
        return jsonify({"error": "Route not found"}), 404
    return send_file('../frontend/build/index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)