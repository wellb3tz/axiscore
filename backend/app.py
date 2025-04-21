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

# Global variables for database connection
conn = None
cursor = None
DATABASE_URL = os.getenv('DATABASE_URL')
# Base URL for public-facing URLs (use environment variable or default to localhost)
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

# Utility functions for 3D viewer implementations to reduce code duplication

def get_file_extension(model_url, ext_param=None):
    """Determine file extension from URL or parameters"""
    if ext_param and ext_param.startswith('.'):
        # Use extension from URL parameter (without the dot)
        return ext_param
    else:
        # Extract from model URL
        file_extension = os.path.splitext(model_url)[1].lower()
        if not file_extension and '.' in model_url:
            # Try the last part after the dot
            file_extension = f".{model_url.split('.')[-1].lower()}"
        return file_extension if file_extension else ".glb"  # Default to .glb

def get_content_type_from_extension(file_extension):
    """Get MIME content type based on file extension"""
    if file_extension.lower().endswith('.glb'):
        return 'model/gltf-binary'
    elif file_extension.lower().endswith('.gltf'):
        return 'model/gltf+json'
    elif file_extension.lower().endswith('.fbx'):
        return 'application/octet-stream'  # FBX doesn't have an official MIME type
    elif file_extension.lower().endswith('.obj'):
        return 'text/plain'  # OBJ files are plain text
    return 'application/octet-stream'  # Default

def extract_uuid_from_text(text):
    """Extract UUID from text if present"""
    if not text:
        return None
    uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    uuid_match = re.search(uuid_pattern, text)
    return uuid_match.group(1) if uuid_match else None

def get_telegram_parameters(request, telegram_webapp=None):
    """
    Extract model parameters from Telegram WebApp or URL parameters.
    Returns a tuple of (model_url, uuid, file_extension)
    """
    model_param = request.args.get('model', '')
    uuid_param = request.args.get('uuid', '')
    ext_param = request.args.get('ext', '')
    
    # Try to get UUID from Telegram WebApp
    start_param = None
    start_command = None
    
    if telegram_webapp:
        # Extract from Telegram WebApp
        try:
            start_param = telegram_webapp.get('initDataUnsafe', {}).get('start_param')
            start_command = telegram_webapp.get('initDataUnsafe', {}).get('start_command')
        except:
            pass
            
    # If we have a direct UUID from a parameter, use that
    extracted_uuid = uuid_param
    
    # If no direct UUID, check start_param
    if not extracted_uuid and start_param:
        extracted_uuid = extract_uuid_from_text(start_param)
    
    # If still no UUID, check start_command
    if not extracted_uuid and start_command:
        extracted_uuid = extract_uuid_from_text(start_command)
    
    # If still no UUID, check if model_param contains a UUID
    if not extracted_uuid and model_param:
        extracted_uuid = extract_uuid_from_text(model_param)
    
    # Get file extension
    file_extension = get_file_extension(model_param, ext_param)
    
    # Construct model URL based on parameters
    if model_param:
        if model_param.startswith('/models/'):
            model_url = f"{BASE_URL}{model_param}"
        elif not model_param.startswith('http'):
            model_url = f"{BASE_URL}/models/{model_param}"
        else:
            model_url = model_param
    elif extracted_uuid:
        model_url = f"{BASE_URL}/models/{extracted_uuid}/model{file_extension}"
    else:
        model_url = ""
    
    return model_url, extracted_uuid, file_extension

def generate_threejs_viewer_html(model_url, file_extension, debug_mode=False, telegram_webapp_js=False):
    """
    Generates HTML with Three.js viewer for 3D models.
    Parameters:
    - model_url: URL to the 3D model
    - file_extension: File extension to determine loader type (.glb, .gltf, .fbx)
    - debug_mode: Whether to show debug info
    - telegram_webapp_js: Whether to include Telegram WebApp JS
    """
    telegram_webapp_script = '<script src="https://telegram.org/js/telegram-web-app.js"></script>' if telegram_webapp_js else ''
    
    # Normalize the extension by removing the dot if present and converting to lowercase
    extension_type = file_extension.lower().replace('.', '')
    
    # Determine appropriate loader based on file extension
    loader_type = "GLTFLoader"  # Default
    if extension_type == "fbx":
        loader_type = "FBXLoader"
    elif extension_type == "obj":
        loader_type = "OBJLoader"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>3D Model Viewer</title>
        {telegram_webapp_script}
        <style>
            body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; font-family: Arial, sans-serif; }}
            #model-container {{ width: 100%; height: 100%; }}
            .error {{ color: red; padding: 20px; position: absolute; top: 10px; left: 10px; background: rgba(255,255,255,0.8); border-radius: 5px; display: none; }}
            .debug-info {{ position: absolute; bottom: 10px; left: 10px; background: rgba(255,255,255,0.8); padding: 10px; border-radius: 5px; font-size: 12px; max-width: 80%; display: {('block' if debug_mode else 'none')}; }}
        </style>
    </head>
    <body>
        <div id="model-container"></div>
        <div id="error" class="error"></div>
        <div id="debug-info" class="debug-info"></div>
        <script src="https://unpkg.com/three@0.132.2/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/GLTFLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/FBXLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/OBJLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/MTLLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/libs/fflate.min.js"></script>
        <script>
            // Initialize debugging
            const debugInfo = document.getElementById('debug-info');
            const errorDiv = document.getElementById('error');
            
            function showDebug(text) {{
                if (debugInfo) {{
                    debugInfo.textContent += text + '\\n';
                    debugInfo.style.display = 'block';
                }}
                console.log(text);
            }}
            
            function showError(text) {{
                if (errorDiv) {{
                    errorDiv.textContent = text;
                    errorDiv.style.display = 'block';
                }}
                console.error(text);
            }}
            
            // Telegram WebApp initialization if included
            const webApp = window.Telegram?.WebApp;
            if (webApp) {{
                webApp.ready();
                webApp.expand();
                showDebug('Telegram WebApp initialized');
            }}
            
            // ThreeJS setup
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
            
            // Load 3D model
            const modelUrl = '{model_url}';
            showDebug('Model URL: ' + modelUrl);
            
            if (modelUrl) {{
                // Determine which loader to use
                const fileExtension = '{extension_type}';
                showDebug('File type: ' + fileExtension);
                
                if (fileExtension === 'fbx') {{
                    // Use FBXLoader for FBX files
                    const loader = new THREE.FBXLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            const fov = camera.fov * (Math.PI / 180);
                            const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
                            
                            camera.position.z = cameraDistance * 1.5;
                            camera.updateProjectionMatrix();
                            
                            scene.add(object);
                            showDebug('FBX model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }} else if (fileExtension === 'obj') {{
                    // Use OBJLoader for OBJ files
                    const loader = new THREE.OBJLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            const fov = camera.fov * (Math.PI / 180);
                            const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
                            
                            camera.position.z = cameraDistance * 1.5;
                            camera.updateProjectionMatrix();
                            
                            scene.add(object);
                            showDebug('OBJ model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }} else {{
                    // Use GLTFLoader for GLB/GLTF files (default)
                    const loader = new THREE.GLTFLoader();
                    loader.load(
                        modelUrl,
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
                            showDebug('GLTF/GLB model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }}
            }} else {{
                showError('No model URL provided');
            }}
            
            // Animation and resize handling
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

# Error handling utility functions

def log_error(error, context=""):
    """Standardized error logging function"""
    import traceback
    error_type = type(error).__name__
    error_msg = str(error)
    error_trace = traceback.format_exc()
    
    # Always log to console
    print(f"❌ ERROR [{error_type}] {context}: {error_msg}")
    if error_trace:
        print(f"Stack trace:\n{error_trace}")
    
    return {
        "type": error_type,
        "message": error_msg,
        "trace": error_trace,
        "context": context
    }

def api_error(error, status_code=500, context=""):
    """Standardized API error response generator"""
    error_details = log_error(error, context)
    
    # Only include stack trace in development environment
    if os.getenv('FLASK_ENV') != 'development':
        error_details.pop('trace', None)
    
    return jsonify({
        "error": error_details['type'],
        "message": error_details['message'],
        "context": context,
        "status": "error",
        "path": request.path,
        "method": request.method
    }), status_code

def db_transaction(func):
    """
    Decorator for database transactions that handles connection errors,
    commits on success, and rolls back on exception
    """
    def wrapper(*args, **kwargs):
        if not ensure_db_connection():
            return jsonify({"error": "Database unavailable", "status": "error"}), 503
        
        try:
            # Reset any previous transaction state
            conn.rollback()
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Commit if no exception occurred
            conn.commit()
            return result
        except psycopg2.Error as db_error:
            # Rollback on database errors
            try:
                conn.rollback()
            except:
                pass
            
            # Log and return standardized error response
            return api_error(db_error, 500, f"Database error in {func.__name__}")
        except Exception as e:
            # Rollback on any other exception
            try:
                conn.rollback()
            except:
                pass
            
            # Log and return standardized error response
            return api_error(e, 500, f"Error in {func.__name__}")
    
    # Preserve the function's metadata
    wrapper.__name__ = func.__name__
    return wrapper

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

# Initial database connection attempt
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
    
    # Create large_model_content table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS large_model_content (
            model_id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
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

    # Check if database connection exists and create user if needed
    if ensure_db_connection():
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
        if file_name.lower().endswith(('.glb', '.gltf', '.fbx', '.obj')) or 'model' in mime_type.lower():
            # Download file from Telegram
            try:
                print(f"Processing file: {file_name}, ID: {file_id}")
                
                # Ensure database connection before proceeding
                if not ensure_db_connection():
                    print("Database connection unavailable, cannot process model")
                    send_message(chat_id, "Sorry, our database is currently unavailable. Please try again later.")
                    return jsonify({"status": "error", "msg": "Database connection unavailable"}), 500
                    
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
                        
                        # Extract UUID from model_url for a cleaner parameter
                        uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
                        uuid_match = re.search(uuid_pattern, model_url)
                        model_uuid = uuid_match.group(1) if uuid_match else "unknown"
                        
                        # Extract file extension to ensure proper loading
                        file_extension = os.path.splitext(file_name)[1].lower()
                        
                        # Create multiple Telegram link formats for better compatibility
                        # Format 1: Standard t.me link with startapp parameter
                        # This format is supposed to pass the parameter via start_param but might not be working correctly
                        # miniapp_url = f"https://t.me/{bot_username}/app?startapp={model_uuid}"
                        
                        # Using a different format that might be more compatible with Telegram WebApps
                        # Instead of using startapp, use a format that focuses on the bot username with the WebApp command
                        miniapp_url = f"https://t.me/{bot_username}?start={model_uuid}"
                        
                        # Format 2: Direct link to the miniapp with UUID in the query
                        direct_miniapp_url = f"{BASE_URL}/miniapp?uuid={model_uuid}&ext={file_extension}"
                        
                        # Format 3: Direct link to the miniapp with model parameter
                        model_direct_url = f"{BASE_URL}/miniapp?model={model_url}"
                        
                        # For debugging, log the URLs
                        print(f"Generated Mini App URL: {miniapp_url}")
                        print(f"Generated direct miniapp URL: {direct_miniapp_url}")
                        print(f"Generated model direct URL: {model_direct_url}")
                        print(f"File extension: {file_extension}")
                        
                        # Send message with options
                        response_text = f"3D model received: {file_name}\n\nUse one of the buttons below to view it:"
                        
                        # Create a combined keyboard with both options
                        keyboard = {
                            'inline_keyboard': [
                                [
                                    {
                                        'text': '📱 Open in Axiscore (Recommended)',
                                        'web_app': {
                                            'url': f"{BASE_URL}/miniapp?uuid={model_uuid}&ext={file_extension}"
                                        }
                                    }
                                ],
                                [
                                    {
                                        'text': '🌐 Open in Browser',
                                        'url': model_direct_url
                                    }
                                ]
                            ]
                        }
                        
                        # Send the message with combined keyboard
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
            send_message(chat_id, "Please send a 3D model file (.glb, .gltf, or .fbx).")
    # Handle text messages
    else:
        # Check for specific commands
        if text.lower() == '/start':
            response_text = "Welcome to Axiscore 3D Model Viewer! You can send me a 3D model file (.glb, .gltf, .fbx, or .obj) and I'll generate an interactive preview for you."
        elif text.lower() == '/help':
            response_text = """
Axiscore 3D Model Viewer Help:
• Send a 3D model file (.glb, .gltf, .fbx, or .obj) directly to this chat
• I'll create an interactive viewer link
• Click "Open in Axiscore" to view and interact with your model
• Use pinch/scroll to zoom, drag to rotate
• You can download the original model from the viewer
            """
        else:
            # Generic response for other messages
            response_text = f"Send me a 3D model file (.glb, .gltf, .fbx, or .obj) to view it in Axiscore. You said: {text}"
        
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
    
    # Get file extension for the model
    file_extension = get_file_extension(model_url)
    extension_type = file_extension.lower().replace('.', '')
    
    # Return HTML page with embedded model viewer using our utility function
    return generate_threejs_viewer_html(model_url, file_extension)

@app.route('/models', methods=['GET'])
@jwt_required()
@db_transaction
def get_models():
    telegram_id = get_jwt_identity()
    
    # The database connection is already ensured by the db_transaction decorator
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
    
    return jsonify({
        "models": model_list, 
        "status": "success",
        "count": len(model_list)
    }), 200

@app.route('/models', methods=['POST'])
@jwt_required()
@db_transaction
def add_model():
    telegram_id = get_jwt_identity()
    
    if not request.json or 'model_url' not in request.json:
        return jsonify({
            "error": "MissingParameter",
            "message": "Missing model URL", 
            "status": "error"
        }), 400
    
    model_url = request.json['model_url']
    model_name = request.json.get('model_name', os.path.basename(urllib.parse.urlparse(model_url).path))
    
    # The database connection is already ensured by the db_transaction decorator
    cursor.execute(
        "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s) RETURNING id",
        (telegram_id, model_name, model_url)
    )
    model_id = cursor.fetchone()[0]
    
    # Successful response
    return jsonify({
        "id": model_id,
        "name": model_name,
        "url": model_url,
        "status": "success"
    }), 201

@app.route('/favicon.ico')
def favicon():
    # Return a 204 No Content response
    return '', 204

@app.route('/models/<model_id>/<filename>')
def serve_model(model_id, filename):
    """Serve model file directly from the database."""
    try:
        print(f"🔍 Serving model request: {model_id}/{filename}")
        
        # Ensure database connection
        if not ensure_db_connection():
            print("❌ Database connection unavailable")
            return jsonify({
                "error": "DatabaseUnavailable",
                "message": "Database connection unavailable",
                "status": "error"
            }), 503
        
        # Reset any failed transaction state
        try:
            conn.rollback()
        except:
            pass
        
        # Extract the UUID from the URL if needed
        # Sometimes model_id is the UUID, sometimes it's in the URL
        extracted_uuid = extract_uuid_from_text(model_id)
        if extracted_uuid:
            print(f"📋 Extracted UUID from model_id: {extracted_uuid}")
        
        content = None
        found_model = False
        
        # STEP 1: Check models table using the URL
        cursor.execute("SELECT id, model_url FROM models WHERE model_url LIKE %s", (f"%{model_id}%",))
        url_result = cursor.fetchone()
        
        if url_result:
            found_model = True
            model_db_id = url_result[0]
            model_url = url_result[1]
            content = None  # Don't assume content column exists
            print(f"✅ Found model via URL pattern: DB ID={model_db_id}, URL={model_url}")
            
            # Try to extract UUID from model_url if we didn't get it already
            if not extracted_uuid:
                extracted_uuid = extract_uuid_from_text(model_url)
                if extracted_uuid:
                    print(f"📋 Extracted UUID from model_url: {extracted_uuid}")
        
        # STEP 2: If we have a UUID, check large_model_content
        if extracted_uuid:
            print(f"🔍 Checking large_model_content table with UUID: {extracted_uuid}")
            cursor.execute("SELECT content FROM large_model_content WHERE model_id = %s", (extracted_uuid,))
            large_result = cursor.fetchone()
            
            if large_result and large_result[0]:
                content = large_result[0]
                print(f"✅ Found content in large_model_content table for UUID: {extracted_uuid}")
            else:
                print(f"⚠️ No content found in large_model_content table for UUID: {extracted_uuid}")
        else:
            print(f"⚠️ No UUID could be extracted from the request")
        
        # STEP 3: If still no content, check large_model_content with the filename
        if not content and not extracted_uuid:
            print(f"🔍 Checking large_model_content table for any entry matching filename")
            cursor.execute("SELECT model_id, content FROM large_model_content LIMIT 50")
            all_large_models = cursor.fetchall()
            
            for lm in all_large_models:
                large_model_id = lm[0]
                large_content = lm[1]
                print(f"📊 Found large model ID: {large_model_id}")
                
                if large_content:
                    content = large_content
                    print(f"✅ Using content from large model: {large_model_id}")
                    break
        
        # If we still don't have content, report a 404
        if not content:
            error_msg = "Model content not available"
            if found_model:
                error_msg = "Model found but content is not available in the database"
            print(f"❌ {error_msg}")
            return jsonify({
                "error": "ModelNotFound",
                "message": error_msg,
                "model_id": model_id,
                "extracted_uuid": extracted_uuid,
                "status": "error"
            }), 404
        
        # Convert base64 back to binary
        try:
            decoded_content = base64.b64decode(content)
            content_size = len(decoded_content)
            print(f"✅ Successfully decoded content, size: {content_size} bytes")
        except Exception as e:
            error_details = log_error(e, f"Failed to decode base64 content for model {model_id}")
            return jsonify({
                "error": error_details['type'], 
                "message": error_details['message'], 
                "status": "error"
            }), 500
        
        # Determine content type based on filename
        content_type = get_content_type_from_extension(filename)
        
        # Set CORS headers to allow loading from any origin
        response = make_response(decoded_content)
        response.headers.set('Content-Type', content_type)
        response.headers.set('Access-Control-Allow-Origin', '*')
        response.headers.set('Cache-Control', 'public, max-age=31536000')  # Cache for 1 year
        print(f"🚀 Returning model content of type {content_type}, size {content_size} bytes")
        return response
        
    except Exception as e:
        # Log the error using our utility function
        error_details = log_error(e, f"Error serving model {model_id}/{filename}")
        
        # Always rollback on error
        try:
            conn.rollback()
        except:
            pass
            
        return jsonify({
            "error": error_details['type'],
            "message": error_details['message'],
            "status": "error",
            "model_id": model_id,
            "filename": filename
        }), 500

@app.route('/viewer')
def model_viewer():
    model_param = request.args.get('model', '')
    
    # Get model URL using our utility function
    model_url, _, file_extension = get_telegram_parameters(request)
    
    # Use more advanced viewer with Telegram WebApp integration
    html = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>3D Model Viewer</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
        <style>
            body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; font-family: Arial, sans-serif; }}
            .container {{ position: relative; width: 100%; height: 100%; }}
            #model-viewer {{ width: 100%; height: 100%; }}
            .loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 18px; color: white; background-color: rgba(0, 0, 0, 0.7); padding: 20px; border-radius: 10px; text-align: center; }}
            .error {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 18px; color: white; background-color: rgba(255, 0, 0, 0.7); padding: 20px; border-radius: 10px; text-align: center; max-width: 80%; }}
            #debug {{ position: absolute; bottom: 0; left: 0; background-color: rgba(0, 0, 0, 0.7); color: white; padding: 5px; font-size: 12px; max-width: 100%; max-height: 30%; overflow-y: auto; display: none; }}
            .ar-button {{ position: absolute; bottom: 20px; right: 20px; background-color: #007bff; color: white; border: none; border-radius: 20px; padding: 10px 20px; font-size: 16px; cursor: pointer; display: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <model-viewer id="model-viewer" src="{model_url}" ar ar-modes="webxr scene-viewer quick-look" camera-controls auto-rotate></model-viewer>
            <div id="loading" class="loading">Loading model...</div>
            <div id="error" class="error" style="display: none;"></div>
            <div id="debug"></div>
            <button id="ar-button" class="ar-button">View in AR</button>
        </div>
        
        <script>
            // Initialize Telegram WebApp
            const tg = window.Telegram.WebApp;
            tg.expand();
            
            const modelViewer = document.getElementById('model-viewer');
            const loadingMessage = document.getElementById('loading');
            const errorMessage = document.getElementById('error');
            const debugElement = document.getElementById('debug');
            const arButton = document.getElementById('ar-button');
            
            // Get the start parameter (if any)
            const startParam = tg.initDataUnsafe && tg.initDataUnsafe.start_param 
                ? tg.initDataUnsafe.start_param 
                : null;
            
            // Debug function to display messages
            function debug(message) {{
                if (debugElement) {{
                    debugElement.style.display = 'block';
                    debugElement.innerHTML += message + '<br>';
                }}
                console.log(message);
            }}
            
            // Set up model-viewer events
            modelViewer.addEventListener('load', () => {{
                loadingMessage.style.display = 'none';
                
                // Check if AR is available
                if (modelViewer.canActivateAR) {{
                    arButton.style.display = 'block';
                }}
            }});
            
            modelViewer.addEventListener('error', (event) => {{
                loadingMessage.style.display = 'none';
                errorMessage.style.display = 'block';
                errorMessage.textContent = 'Error loading model. Please try again.';
                debug('Error: ' + JSON.stringify(event.detail));
            }});
            
            // Custom AR button
            arButton.addEventListener('click', () => {{
                modelViewer.activateAR();
            }});
            
            // Fallback to Three.js if model-viewer doesn't work or no model URL
            if (!'{model_url}') {{
                loadingMessage.style.display = 'none';
                errorMessage.style.display = 'block';
                errorMessage.textContent = 'No model URL provided.';
            }}

            // Handle 3D file formats not supported by model-viewer (like FBX or OBJ)
            const fileExtension = '{file_extension}'.toLowerCase();
            if (fileExtension.replace('.', '') === 'fbx' || fileExtension.replace('.', '') === 'obj') {{
                // Hide model-viewer and create three.js container
                modelViewer.style.display = 'none';
                const threeContainer = document.createElement('div');
                threeContainer.style.width = '100%';
                threeContainer.style.height = '100%';
                document.querySelector('.container').appendChild(threeContainer);
                
                // Initialize three.js
                const scene = new THREE.Scene();
                scene.background = new THREE.Color(0xf0f0f0);
                
                const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                camera.position.z = 5;
                
                const renderer = new THREE.WebGLRenderer({{ antialias: true }});
                renderer.setSize(window.innerWidth, window.innerHeight);
                threeContainer.appendChild(renderer.domElement);
                
                const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
                scene.add(ambientLight);
                
                const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
                directionalLight.position.set(1, 1, 1);
                scene.add(directionalLight);
                
                const controls = new THREE.OrbitControls(camera, renderer.domElement);
                controls.enableDamping = true;
                
                // Determine which loader to use
                const extension = fileExtension.replace('.', '');
                
                if (extension === 'fbx') {{
                    // Load FBX model
                    const loader = new THREE.FBXLoader();
                    loader.load(
                        '{model_url}',
                        (object) => {{
                            loadingMessage.style.display = 'none';
                            
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            const fov = camera.fov * (Math.PI / 180);
                            const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
                            
                            camera.position.z = cameraDistance * 1.5;
                            camera.updateProjectionMatrix();
                            
                            scene.add(object);
                        }},
                        (xhr) => {{
                            console.log((xhr.loaded / xhr.total) * 100 + '% loaded');
                        }},
                        (error) => {{
                            loadingMessage.style.display = 'none';
                            errorMessage.style.display = 'block';
                            errorMessage.textContent = 'Error loading FBX model: ' + error.message;
                            debug('Error: ' + error.message);
                        }}
                    );
                }} else if (extension === 'obj') {{
                    // Load OBJ model
                    const loader = new THREE.OBJLoader();
                    loader.load(
                        '{model_url}',
                        (object) => {{
                            loadingMessage.style.display = 'none';
                            
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            const fov = camera.fov * (Math.PI / 180);
                            const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
                            
                            camera.position.z = cameraDistance * 1.5;
                            camera.updateProjectionMatrix();
                            
                            scene.add(object);
                        }},
                        (xhr) => {{
                            console.log((xhr.loaded / xhr.total) * 100 + '% loaded');
                        }},
                        (error) => {{
                            loadingMessage.style.display = 'none';
                            errorMessage.style.display = 'block';
                            errorMessage.textContent = 'Error loading OBJ model: ' + error.message;
                            debug('Error: ' + error.message);
                        }}
                    );
                }}
                
                // Animation loop
                function animate() {{
                    requestAnimationFrame(animate);
                    controls.update();
                    renderer.render(scene, camera);
                }}
                animate();
                
                // Handle window resize
                window.addEventListener('resize', () => {{
                    camera.aspect = window.innerWidth / window.innerHeight;
                    camera.updateProjectionMatrix();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                }});
            }}
        </script>
    </body>
    </html>
    '''
    
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html'
    return response

@app.route('/miniapp')
@app.route('/miniapp/')
def miniapp():
    """Serve the MiniApp React frontend."""
    # Get parameters and model URL using our utility function
    model_url, uuid_param, file_extension = get_telegram_parameters(request)
    
    # If we have a UUID directly (from Telegram), search for the model in database
    if uuid_param and not model_url:
        print(f"Received UUID parameter: {uuid_param}")
        # Search for a model with this UUID
        if ensure_db_connection():
            try:
                # Also get the model_name to determine correct file extension
                cursor.execute("SELECT model_url, model_name FROM models WHERE model_url LIKE %s", (f"%{uuid_param}%",))
                result = cursor.fetchone()
                if result and result[0]:
                    model_url = result[0]
                    model_name = result[1] if len(result) > 1 else ""
                    print(f"Found model URL from UUID: {model_url}")
                    
                    # Store the file extension for possible use later
                    if '.' in model_name:
                        file_extension = os.path.splitext(model_name)[1].lower()
                else:
                    print(f"No model found for UUID: {uuid_param}")
            except Exception as e:
                print(f"Error finding model for UUID: {e}")
    
    print(f"Using file extension: {file_extension}")
    print(f"Rendering miniapp with model URL: {model_url}")
    
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
    
    # If no file is found, return a simple HTML with model viewer
    # Prepare a JavaScript-friendly version of the model URL
    js_model_url = model_url.replace("'", "\\'")
    
    # For miniapp, we need a more specialized viewer with Telegram WebApp integration
    # This version handles both model-viewer component and ThreeJS fallback
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Axiscore 3D Viewer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body, html {{ height: 100%; margin: 0; padding: 0; font-family: Arial, sans-serif; }}
            #viewer {{ width: 100%; height: 100%; }}
            .error {{ 
                color: red; 
                padding: 20px; 
                position: absolute; 
                top: 10px; 
                left: 10px; 
                background: rgba(255,255,255,0.8); 
                border-radius: 5px; 
                display: none; 
            }}
            .debug-info {{
                position: absolute;
                bottom: 10px;
                left: 10px;
                background: rgba(255,255,255,0.8);
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
                max-width: 80%;
                display: none;
            }}
        </style>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
    </head>
    <body>
        <div id="viewer"></div>
        <div id="error" class="error"></div>
        <div id="debug-info" class="debug-info"></div>
        <script src="https://unpkg.com/three@0.132.2/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/GLTFLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/FBXLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/OBJLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/MTLLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/libs/fflate.min.js"></script>
        <script>
            // Initialize Telegram WebApp
            const webApp = window.Telegram?.WebApp;
            let modelUrl = '{js_model_url}';
            const baseUrl = '{BASE_URL}';  // Define baseUrl for JavaScript
            const debugInfo = document.getElementById('debug-info');
            const errorDiv = document.getElementById('error');
            
            // Always show debug info in Telegram
            if (webApp) {{
                debugInfo.style.display = 'block';
                showDebug('Debug mode enabled. Base URL: ' + baseUrl + '\\nInitial model URL: ' + modelUrl);
            }} else {{
                // Show debug info for browser testing
                debugInfo.style.display = 'block';
                showDebug('Browser mode. Base URL: ' + baseUrl + '\\nInitial model URL: ' + modelUrl);
            }}
            
            // Show debugging info
            function showDebug(text) {{
                debugInfo.textContent = text;
                debugInfo.style.display = 'block';
            }}
            
            // Handle Telegram startapp parameter if available
            if (webApp) {{
                const startParam = webApp.initDataUnsafe?.start_param;
                const startCommand = webApp.initDataUnsafe?.start_command;
                showDebug('Telegram WebApp detected!\\nStart param: ' + (startParam || 'none') + 
                          '\\nStart command: ' + (startCommand || 'none'));
                
                // Try to get UUID from start param
                if (startParam) {{
                    console.log('Using start parameter from Telegram:', startParam);
                    
                    // If modelUrl is empty or start_param looks like a UUID, use start_param
                    if (modelUrl === '' || startParam.includes('-')) {{
                        const uuid = startParam;
                        modelUrl = `${{baseUrl}}/models/${{uuid}}/model{file_extension}`;
                        showDebug('Using model from Telegram parameter:\\n' + modelUrl);
                    }}
                }} else if (startCommand) {{
                    // Some versions of Telegram might pass the parameter as a start_command
                    console.log('Using start command from Telegram:', startCommand);
                    
                    // Extract UUID from start command if it looks like one
                    const uuidMatch = startCommand.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/);
                    if (uuidMatch) {{
                        const uuid = uuidMatch[1];
                        modelUrl = `${{baseUrl}}/models/${{uuid}}/model{file_extension}`;
                        showDebug('Using model from Telegram start command:\\n' + modelUrl);
                    }}
                }} else {{
                    // If no start param, try to extract UUID from URL
                    const urlParams = new URLSearchParams(window.location.search);
                    let uuidParam = urlParams.get('uuid') || urlParams.get('startapp');
                    
                    // Check for "start" parameter which is used in Telegram bot start commands
                    if (!uuidParam) {{
                        const startValue = urlParams.get('start');
                        if (startValue) {{
                            // Extract UUID from start value if it looks like one
                            const uuidMatch = startValue.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/);
                            if (uuidMatch) {{
                                uuidParam = uuidMatch[1];
                            }} else {{
                                uuidParam = startValue;
                            }}
                        }}
                    }}
                    
                    if (uuidParam) {{
                        console.log('Using UUID from URL parameters:', uuidParam);
                        modelUrl = `${{baseUrl}}/models/${{uuidParam}}/model{file_extension}`;
                        showDebug('Using model from URL parameter:\\n' + modelUrl);
                    }} else {{
                        // Try to extract UUID from the URL path
                        const urlPath = window.location.pathname;
                        const uuidMatch = urlPath.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/);
                        
                        if (uuidMatch) {{
                            const uuid = uuidMatch[1];
                            console.log('Extracted UUID from URL path:', uuid);
                            modelUrl = `${{baseUrl}}/models/${{uuid}}/model{file_extension}`;
                            showDebug('Using model from URL path:\\n' + modelUrl);
                        }}
                    }}
                }}
                
                // Tell Telegram we're ready
                webApp.ready();
                webApp.expand();
            }}
            
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
                console.log('Loading model from URL:', modelUrl);
                
                // Extract file extension for loader selection
                const extension = '{file_extension}'.toLowerCase();
                showDebug('Using file extension: ' + extension);
                
                // Remove the dot from the extension before comparison
                const extensionWithoutDot = extension.replace('.', '');
                
                if (extensionWithoutDot === 'fbx') {{
                    // Use FBXLoader for FBX files
                    showDebug('Using FBXLoader for FBX file');
                    const loader = new THREE.FBXLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            camera.position.z = maxDim * 2;
                            
                            scene.add(object);
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            console.error('Error loading model:', error);
                            errorDiv.textContent = 'Failed to load 3D model: ' + error.message;
                            errorDiv.style.display = 'block';
                            showDebug('Error: ' + error.message);
                        }}
                    );
                }} else if (extensionWithoutDot === 'obj') {{
                    // Use OBJLoader for OBJ files
                    showDebug('Using OBJLoader for OBJ file');
                    const loader = new THREE.OBJLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
                            object.position.x = -center.x;
                            object.position.y = -center.y;
                            object.position.z = -center.z;
                            
                            // Adjust camera
                            const maxDim = Math.max(size.x, size.y, size.z);
                            camera.position.z = maxDim * 2;
                            
                            scene.add(object);
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            console.error('Error loading model:', error);
                            errorDiv.textContent = 'Failed to load 3D model: ' + error.message;
                            errorDiv.style.display = 'block';
                            showDebug('Error: ' + error.message);
                        }}
                    );
                }} else {{
                    // Use GLTFLoader for GLB/GLTF files (default)
                    showDebug('Using GLTFLoader for ' + extension + ' file');
                    const loader = new THREE.GLTFLoader();
                    loader.load(
                        modelUrl,
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
                            camera.position.z = maxDim * 2;
                            
                            scene.add(gltf.scene);
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            console.error('Error loading model:', error);
                            errorDiv.textContent = 'Failed to load 3D model: ' + error.message;
                            errorDiv.style.display = 'block';
                            showDebug('Error: ' + error.message);
                        }}
                    );
                }}
            }} else {{
                errorDiv.textContent = 'No model loaded. Send a 3D model to the Telegram bot (@AxisCoreBot) to view it here.';
                errorDiv.style.display = 'block';
                showDebug('No model URL provided. This app requires a model parameter in the URL (e.g., ?model=<model_id> or ?uuid=<uuid>)');
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
    
    return html

@app.route('/help')
def help_page():
    return """
    <h1>Axiscore 3D Model Viewer API</h1>
    <p>This API allows you to view and share 3D models via Telegram.</p>
    <p>Supported file formats:</p>
    <ul>
        <li>glTF/GLB (.glb, .gltf)</li>
        <li>Filmbox (.fbx)</li>
        <li>Wavefront (.obj)</li>
    </ul>
    <p>To use this service, send your 3D model file to the Telegram bot: @AxisCoreBot</p>
    """

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "3D Model Viewer API is running",
        "supported_formats": ["glb", "gltf", "fbx", "obj"]
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
            print("❌ Missing content in file data")
            return None
            
        # Ensure database connection
        if not ensure_db_connection():
            print("❌ Database connection unavailable, cannot save model")
            return None
            
        # Generate a unique ID for the model
        model_id = str(uuid.uuid4())
        
        # Get the original filename and preserve its extension
        original_filename = file_data.get('filename', file_data.get('name', ''))
        
        # If no filename provided or invalid, determine extension from mime_type or use default
        if not original_filename or '.' not in original_filename:
            # Try to get extension from mime type
            mime_type = file_data.get('mime_type', '').lower()
            if 'fbx' in mime_type:
                filename = f"model.fbx"
            else:
                # Default to GLB if no better information
                filename = f"model.glb"
        else:
            # Use the original filename
            filename = original_filename
            
        print(f"📌 Saving model with ID: {model_id}, filename: {filename}")
        
        # Extract file extension for later use
        file_extension = os.path.splitext(filename)[1].lower()
        
        # Check size of content
        content_size = file_data.get('size', len(file_data['content']))
        print(f"📊 Content size: {content_size} bytes, File type: {file_extension}")
        
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
            print("📋 Creating large_model_content table")
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
            print("📋 Adding content_size column to models table")
            cursor.execute("ALTER TABLE models ADD COLUMN content_size BIGINT")
            
        # Extract proper telegram_id with fallback to avoid 'unknown'
        telegram_id = file_data.get('telegram_id')
        if not telegram_id or telegram_id == 'unknown':
            telegram_id = '591646476'  # Use a default ID if unknown
            
        # Generate consistent URL for the model that will be accessible
        model_path = f"/models/{model_id}/{filename}"
        model_url = f"{BASE_URL}{model_path}"
        
        print(f"🔗 Generated URL: {model_url}")
        
        # Always store content in large_model_content table for backup
        try:
            cursor.execute(
                "INSERT INTO large_model_content (model_id, content) VALUES (%s, %s)",
                (model_id, file_data['content'])
            )
            print(f"✅ Content stored in large_model_content table with ID: {model_id}")
        except Exception as e:
            print(f"❌ Error storing in large_model_content: {e}")
            # Continue anyway, might work in models table
        
        # Store the model information in the database with different strategies based on size
        if content_size > 1024 * 1024:  # If larger than 1MB
            print(f"📊 Large content detected ({content_size} bytes), storing reference only")
            # For large models, store the model reference
            try:
                cursor.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content_size, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, content_size, datetime.now())
                )
                print(f"✅ Model reference stored in models table")
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"⚠️ Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    cursor.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s)",
                        (telegram_id, filename, model_url)
                    )
                else:
                    raise
        else:
            # For smaller models, store the content directly
            print(f"📊 Standard content size ({content_size} bytes), storing directly")
            try:
                cursor.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content, content_size, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, file_data['content'], content_size, datetime.now())
                )
                print(f"✅ Model with content stored in models table")
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"⚠️ Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    cursor.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url, content) VALUES (%s, %s, %s, %s)",
                        (telegram_id, filename, model_url, file_data['content'])
                    )
                else:
                    raise
        
        # Commit the transaction
        conn.commit()
        print(f"✅ Successfully saved model {model_id} to database")
        
        # For debugging, try to verify the content was stored
        try:
            cursor.execute("SELECT model_id FROM large_model_content WHERE model_id = %s", (model_id,))
            if cursor.fetchone():
                print(f"✅ Verified: Content exists in large_model_content table")
            else:
                print(f"⚠️ Warning: Content not found in large_model_content table")
        except Exception as verify_err:
            print(f"⚠️ Error verifying content: {verify_err}")
        
        # Return the path portion for the model
        return model_path
        
    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        print(f"❌ Error saving model to storage: {e}")
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

@app.route('/model-info/<model_id>')
def model_info(model_id):
    """Get information about a model for debugging purposes."""
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({"error": "Database connection unavailable"}), 500
            
        # First, try to rollback any failed transaction to get clean state
        try:
            conn.rollback()
        except:
            pass
            
        # Check for model in models table
        cursor.execute("SELECT id, telegram_id, model_name, model_url FROM models WHERE model_url LIKE %s", (f"%{model_id}%",))
        models = cursor.fetchall()
        
        models_info = []
        for model in models:
            models_info.append({
                "id": model[0],
                "telegram_id": model[1],
                "model_name": model[2],
                "model_url": model[3]
            })
            
        # Check in large_model_content table
        cursor.execute("SELECT model_id FROM large_model_content WHERE model_id = %s", (model_id,))
        large_model = cursor.fetchone()
        
        large_model_info = None
        if large_model:
            large_model_info = {
                "model_id": large_model[0],
                "has_content": True
            }
            
        return jsonify({
            "model_id": model_id,
            "models_found": len(models_info),
            "models": models_info,
            "large_model": large_model_info
        })
        
    except Exception as e:
        # Always rollback on error
        try:
            conn.rollback()
        except:
            pass
            
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/find-model-by-name/<filename>')
def find_model_by_name(filename):
    """Find a model by its filename."""
    try:
        # Ensure database connection
        if not ensure_db_connection():
            return jsonify({"error": "Database connection unavailable"}), 500
            
        # Reset transaction state
        try:
            conn.rollback()
        except:
            pass
            
        # Search by filename
        cursor.execute("SELECT id, telegram_id, model_name, model_url FROM models WHERE model_name = %s", (filename,))
        models = cursor.fetchall()
        
        results = []
        for model in models:
            model_id = model[0]
            telegram_id = model[1]
            model_name = model[2]
            model_url = model[3]
            
            # Check if content exists
            cursor.execute("SELECT content FROM models WHERE id = %s", (model_id,))
            content_result = cursor.fetchone()
            has_content = content_result is not None and content_result[0] is not None
            
            results.append({
                "id": model_id,
                "telegram_id": telegram_id,
                "model_name": model_name,
                "model_url": model_url,
                "has_content": has_content
            })
            
        return jsonify({
            "filename": filename,
            "models_found": len(results),
            "models": results
        })
        
    except Exception as e:
        # Always rollback on error
        try:
            conn.rollback()
        except:
            pass
            
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.errorhandler(500)
def handle_500(e):
    """Handle internal server errors and log details."""
    error_details = log_error(e, f"Internal Server Error at {request.path}")
    
    return jsonify({
        "error": "InternalServerError",
        "message": error_details['message'],
        "path": request.path,
        "method": request.method,
        "status": "error"
    }), 500

def ensure_db_connection():
    """Ensure database connection is active, reconnect if needed."""
    global conn, cursor, DATABASE_URL
    
    try:
        # Check if connection is closed or cursor is None
        if conn is None or cursor is None or conn.closed:
            print("Database connection lost, reconnecting...")
            # Reconnect to database
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cursor = conn.cursor()
            print("Successfully reconnected to database")
        
        # Test connection with a simple query
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True
    except Exception as e:
        print(f"Failed to ensure database connection: {e}")
        try:
            # If connection exists but is broken, close it to avoid leaks
            if conn and not conn.closed:
                conn.close()
        except:
            pass
        
        try:
            # Attempt to reconnect one more time
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cursor = conn.cursor()
            print("Successfully reconnected to database after error")
            return True
        except Exception as reconnect_error:
            print(f"Failed to reconnect to database: {reconnect_error}")
            conn = None
            cursor = None
            return False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)