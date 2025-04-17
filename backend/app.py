import os
import psycopg2
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
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
import base64
import io
import uuid
from datetime import datetime

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
# Base URL for public-facing URLs (use environment variable or default to localhost)
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

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
            content TEXT,
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
                print(f"Processing file: {file_name}, ID: {file_id}")
                file_data = download_telegram_file(file_id)
                
                if file_data:
                    print(f"File downloaded successfully, size: {file_data['size']} bytes")
                    # Save to storage and get URL
                    model_url = save_model_to_storage(file_data)
                    
                    if model_url:
                        print(f"Model saved successfully, URL: {model_url}")
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
                        print(f"Generated direct URL: {direct_url}")
                        
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
                        print("Failed to save model to storage")
                        send_message(chat_id, "Failed to store your 3D model. Database error.")
                else:
                    print("Failed to download file from Telegram")
                    send_message(chat_id, "Failed to download your file from Telegram. Please try again.")
            except psycopg2.Error as dbe:
                print(f"Database error processing 3D model: {dbe}")
                send_message(chat_id, f"Database error: {str(dbe)[:100]}. Please contact the administrator.")
            except Exception as e:
                import traceback
                print(f"Error processing 3D model: {e}")
                print(traceback.format_exc())
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

@app.route('/models/<model_id>/<filename>')
def serve_model(model_id, filename):
    """Serve model file directly from the database."""
    try:
        print(f"Attempting to serve model: {model_id}/{filename}")
        
        if not conn or not cursor:
            print("No database connection available")
            return jsonify({"error": "Server configuration error"}), 500
        
        # Fetch the model data from the database
        cursor.execute("SELECT content FROM models WHERE model_url = %s", (f"base64://{model_id}",))
        result = cursor.fetchone()
        
        if not result:
            print(f"Model not found: {model_id}")
            return jsonify({"error": "Model not found"}), 404
            
        content = result[0]
        
        # Check if we have content stored
        if not content:
            # Try to get it from large_model_content table
            print(f"Model found but no content stored in models table. Checking large_model_content for: {model_id}")
            cursor.execute("SELECT content FROM large_model_content WHERE model_id = %s", (model_id,))
            large_result = cursor.fetchone()
            
            if large_result and large_result[0]:
                content = large_result[0]
                print(f"Content found in large_model_content table")
            else:
                print(f"No content found in either table for model: {model_id}")
                return jsonify({"error": "Model content not available"}), 404
        
        # Convert base64 back to binary
        try:
            decoded_content = base64.b64decode(content)
            print(f"Successfully decoded content, size: {len(decoded_content)} bytes")
        except Exception as e:
            print(f"Failed to decode base64 content: {e}")
            return jsonify({"error": "Failed to process model data"}), 500
        
        # Determine content type based on filename
        content_type = 'application/octet-stream'  # Default
        if filename.lower().endswith('.glb'):
            content_type = 'model/gltf-binary'
        elif filename.lower().endswith('.gltf'):
            content_type = 'model/gltf+json'
        
        # Set CORS headers to allow loading from any origin
        response = make_response(decoded_content)
        response.headers.set('Content-Type', content_type)
        response.headers.set('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        print(f"Error serving model {model_id}/{filename}: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Server error"}), 500

@app.route('/miniapp')
@app.route('/miniapp/')
def miniapp():
    """Serve the MiniApp React frontend."""
    # Log the request for debugging
    model_param = request.args.get('model')
    if model_param:
        print(f"MiniApp requested with model: {model_param}")
    
    # Try different possible paths for the frontend file
    possible_paths = [
        '../frontend/build/index.html',  # Original relative path
        'frontend/build/index.html',     # Without leading ../
        '/app/frontend/build/index.html' # Absolute path in container
    ]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                return send_file(path)
        except:
            continue
    
    # If no file is found, return a simple HTML with error message and model viewer
    model_url = request.args.get('model', '')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Axiscore 3D Viewer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body, html {{ height: 100%; margin: 0; padding: 0; }}
            #viewer {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div id="viewer"></div>
        <script src="https://unpkg.com/three@0.132.2/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/GLTFLoader.js"></script>
        <script>
            const modelUrl = '{model_url}';
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);
            
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.z = 5;
            
            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.getElementById('viewer').appendChild(renderer.domElement);
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1);
            scene.add(directionalLight);
            
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            
            if (modelUrl) {{
                const loader = new THREE.GLTFLoader();
                loader.load(modelUrl, (gltf) => {{
                    scene.add(gltf.scene);
                    
                    // Center and scale model
                    const box = new THREE.Box3().setFromObject(gltf.scene);
                    const center = box.getCenter(new THREE.Vector3());
                    const size = box.getSize(new THREE.Vector3());
                    
                    gltf.scene.position.x = -center.x;
                    gltf.scene.position.y = -center.y;
                    gltf.scene.position.z = -center.z;
                    
                    const maxDim = Math.max(size.x, size.y, size.z);
                    camera.position.z = maxDim * 2;
                }}, undefined, (error) => {{
                    console.error('Error loading model:', error);
                    alert('Failed to load 3D model: ' + error.message);
                }});
            }}
            
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

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "3D Model Viewer API is running"
    })

def download_telegram_file(file_id):
    """Download a file from Telegram servers using its file_id and return content."""
    try:
        # Get file path from Telegram
        file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        file_info_response = requests.get(file_info_url)
        file_info = file_info_response.json()
        
        print(f"File info response: {file_info}")
        
        if file_info.get('ok'):
            telegram_file_path = file_info['result']['file_path']
            file_size = file_info['result'].get('file_size', 0)
            
            # Check file size, Telegram usually limits to 20MB
            if file_size > 20 * 1024 * 1024:
                print(f"File too large: {file_size} bytes")
                return None
                
            # Download file from Telegram
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{telegram_file_path}"
            response = requests.get(download_url, stream=True)
            
            if response.status_code == 200:
                # Get the file content as bytes
                file_content = response.content
                print(f"Downloaded file size: {len(file_content)} bytes")
                
                # Create local path for debug purposes
                local_filename = f"{file_id}_{os.path.basename(telegram_file_path)}"
                
                # Encode file content as base64 for storage in DB
                try:
                    base64_content = base64.b64encode(file_content).decode('utf-8')
                    print(f"Base64 encoding successful, length: {len(base64_content)}")
                    
                    return {
                        'filename': local_filename,
                        'content': base64_content,
                        'size': len(file_content)
                    }
                except Exception as e:
                    print(f"Error during base64 encoding: {e}")
                    return None
            else:
                print(f"Error downloading file: {response.status_code}, {response.text}")
                return None
        else:
            print(f"Error getting file info: {file_info}")
            return None
    except Exception as e:
        print(f"Error in download_telegram_file: {e}")
        return None

def save_model_to_storage(file_data):
    """
    Save a 3D model to storage and return a unique URL.
    For large models (>1MB), only store the model ID and not the content.
    """
    try:
        # Check if valid base64 content
        if not file_data.get('content'):
            print("Missing content in file data")
            return None
            
        # Generate a unique ID for the model
        model_id = str(uuid.uuid4())
        filename = file_data.get('filename', file_data.get('name', 'model.glb'))
        print(f"Saving model with ID: {model_id}, filename: {filename}")
        
        # Check size of content
        content_size = file_data.get('size', len(file_data['content']))
        print(f"Content size: {content_size} bytes")
        
        # Begin a transaction
        cursor.execute("BEGIN")
        
        # First, check if the large_model_content table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'large_model_content'
            )
        """)
        
        if not cursor.fetchone()[0]:
            # Create large_model_content table if it doesn't exist
            print("Creating large_model_content table")
            cursor.execute("""
                CREATE TABLE large_model_content (
                    model_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Check if content_size column exists in models table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'models' AND column_name = 'content_size'
            )
        """)
        
        if not cursor.fetchone()[0]:
            # Add content_size column if it doesn't exist
            print("Adding content_size column to models table")
            cursor.execute("ALTER TABLE models ADD COLUMN content_size BIGINT")
            
        # Extract proper telegram_id with fallback to avoid 'unknown'
        telegram_id = file_data.get('telegram_id')
        if not telegram_id or telegram_id == 'unknown':
            telegram_id = '591646476'  # Use a default ID if unknown
            
        # Generate consistent URL for the model that will be accessible
        model_path = f"/models/{model_id}/{filename}"
        model_url = f"{BASE_URL}{model_path}"
        
        # Store the model information in the database with different strategies based on size
        if content_size > 1024 * 1024:  # If larger than 1MB
            print(f"Large content detected ({content_size} bytes), storing reference only")
            # For large models, store the model reference
            try:
                cursor.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content_size, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, content_size, datetime.now())
                )
                
                # Store content in a separate table for large content
                cursor.execute(
                    "INSERT INTO large_model_content (model_id, content) VALUES (%s, %s)",
                    (model_id, file_data['content'])
                )
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    cursor.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s)",
                        (telegram_id, filename, model_url)
                    )
                    cursor.execute(
                        "INSERT INTO large_model_content (model_id, content) VALUES (%s, %s)",
                        (model_id, file_data['content'])
                    )
                else:
                    raise
        else:
            # For smaller models, store the content directly
            print(f"Standard content size ({content_size} bytes), storing directly")
            try:
                cursor.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content, content_size, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, file_data['content'], content_size, datetime.now())
                )
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    cursor.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url, content) VALUES (%s, %s, %s, %s)",
                        (telegram_id, filename, model_url, file_data['content'])
                    )
                else:
                    raise
        
        # Commit the transaction
        conn.commit()
        print(f"Successfully saved model {model_id} to database")
        
        # Return the path portion for the model
        return model_path
        
    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        print(f"Error saving model to storage: {e}")
        import traceback
        print(traceback.format_exc())
        return None

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

@app.route('/model-webhook', methods=['POST'])
def model_webhook():
    try:
        print("Webhook received")
        data = request.json
        print(f"Webhook data: {json.dumps(data, indent=2)}")
        
        # Extract chat_id and status
        chat_id = data.get('chat_id')
        status = data.get('status')
        
        print(f"Processing webhook for chat_id: {chat_id}, status: {status}")
        
        if not chat_id:
            print("Missing chat_id in webhook data")
            return jsonify({"error": "Missing chat_id in webhook data"}), 400
            
        if not status:
            print("Missing status in webhook data")
            return jsonify({"error": "Missing status in webhook data"}), 400
        
        # Handle completed status
        if status == 'completed':
            # Check if file_data exists and has content
            file_data = data.get('file_data')
            if not file_data:
                print("Missing file_data in webhook data")
                return jsonify({"error": "Missing file_data in completed webhook"}), 400
                
            if not file_data.get('content'):
                print("Missing content in file_data")
                return jsonify({"error": "Missing content in file_data"}), 400
                
            # Add telegram_id to file_data for tracking
            file_data['telegram_id'] = chat_id
                
            # Save the model to storage
            print("Saving model to storage")
            model_url = save_model_to_storage(file_data)
            
            if not model_url:
                print("Failed to save model to storage")
                # Update the user's status in the database
                cursor.execute(
                    "UPDATE users SET status = %s WHERE telegram_id = %s",
                    ("error", chat_id)
                )
                conn.commit()
                
                # Send error message to user
                send_message(
                    chat_id=chat_id,
                    text="Failed to process your 3D model. Please try again."
                )
                return jsonify({"error": "Failed to save model to storage"}), 500
            
            # Update the user's status and model URL in the database
            try:
                cursor.execute(
                    "UPDATE users SET status = %s, model_url = %s WHERE telegram_id = %s",
                    ("completed", model_url, chat_id)
                )
                conn.commit()
            except Exception as db_error:
                print(f"Database update error: {db_error}")
                # If we can't update the database but saved the model, still try to notify the user
            
            # Send success message to user
            try:
                public_url = f"{BASE_URL}{model_url}"
                send_message(
                    chat_id,
                    f"Your 3D model is ready! View it here: {public_url}"
                )
                print(f"Success message sent to user {chat_id} with URL {public_url}")
            except Exception as bot_error:
                print(f"Error sending message to user: {bot_error}")
                return jsonify({"error": f"Failed to send message to user: {str(bot_error)}"}), 500
                
            return jsonify({"success": True, "model_url": model_url})
            
        # Handle failed status
        elif status == 'failed':
            error = data.get('error', 'Unknown error occurred')
            print(f"Model generation failed: {error}")
            
            # Update the user's status in the database
            cursor.execute(
                "UPDATE users SET status = %s WHERE telegram_id = %s",
                ("failed", chat_id)
            )
            conn.commit()
            
            # Send error message to user
            send_message(
                chat_id=chat_id,
                text=f"Sorry, we couldn't create your 3D model. Error: {error}"
            )
            
            return jsonify({"success": True})
            
        # Handle unknown status
        else:
            print(f"Unknown status in webhook: {status}")
            return jsonify({"error": f"Unknown status: {status}"}), 400
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.errorhandler(500)
def handle_500(e):
    """Handle internal server errors and log details."""
    import traceback
    error_traceback = traceback.format_exc()
    print(f"Internal Server Error: {str(e)}")
    print(error_traceback)
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e),
        "path": request.path,
        "method": request.method
    }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)