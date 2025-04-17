import os
import psycopg2
from flask import Flask, request, jsonify, send_file
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

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
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

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Extract message data
    message = data.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')
    
    if not chat_id:
        return jsonify({"status": "error", "msg": "No chat_id found"}), 400
    
    # Handle commands
    if text.startswith('/start'):
        response_text = "Welcome to 3D Model Viewer Bot! Send me a 3D model URL to view it."
        send_message(chat_id, response_text)
    elif text.startswith('/help'):
        response_text = "This bot allows you to view 3D models. Send a GLTF/GLB model URL to view it."
        send_message(chat_id, response_text)
    elif text.startswith('/mymodels'):
        # Get user's models
        models = []
        if conn and cursor:
            try:
                cursor.execute("SELECT model_name, model_url FROM models WHERE telegram_id = %s", (chat_id,))
                models = cursor.fetchall()
            except Exception as e:
                print(f"Database error in webhook /mymodels: {e}")
                models = []
        
        if models:
            model_list = "\n".join([f"{idx+1}. {model[0]}: {model[1]}" for idx, model in enumerate(models)])
            response_text = f"Your models:\n{model_list}"
        else:
            response_text = "You haven't uploaded any models yet."
        
        send_message(chat_id, response_text)
    elif text.startswith('http') and ('.glb' in text.lower() or '.gltf' in text.lower()):
        # Process model URL
        model_url = text.strip()
        model_name = os.path.basename(urllib.parse.urlparse(model_url).path)
        
        # Save model URL to database if available
        if conn and cursor:
            try:
                cursor.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s)",
                    (chat_id, model_name, model_url)
                )
                conn.commit()
            except Exception as e:
                print(f"Database error in webhook model save: {e}")
        
        # Generate viewer URL
        viewer_url = f"{request.url_root}view?model={urllib.parse.quote(model_url)}"
        
        # Send inline keyboard with button to view the model
        send_inline_button(
            chat_id, 
            f"Model '{model_name}' added. Click the button below to view it:", 
            "View 3D Model", 
            viewer_url
        )
    else:
        response_text = "Please send a valid 3D model URL (ending with .glb or .gltf)"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)