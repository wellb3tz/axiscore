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

# Import modules
import viewer_utils
from viewer_utils import (
    get_file_extension, 
    get_content_type_from_extension, 
    extract_uuid_from_text,
    get_telegram_parameters,
    generate_threejs_viewer_html
)
import error_utils
from error_utils import (
    log_error,
    api_error
)
import telegram_utils
from telegram_utils import (
    check_telegram_auth,
    send_message,
    send_inline_button,
    send_webapp_button,
    download_telegram_file,
    get_bot_info
)
import db_utils
from db_utils import (
    DatabaseManager,
    create_transaction_decorator
)

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

# Base URL for public-facing URLs (use environment variable or default to localhost)
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
# Telegram bot token for API calls
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_SECRET = TELEGRAM_BOT_TOKEN.split(':')[1] if TELEGRAM_BOT_TOKEN else ""

# Initialize the database manager
db = DatabaseManager()

# Create the db_transaction decorator
db_transaction = create_transaction_decorator(db)

@app.route('/telegram_auth', methods=['POST'])
def telegram_auth():
    auth_data = request.json
    if not check_telegram_auth(auth_data, TELEGRAM_BOT_SECRET):
        return jsonify({"msg": "Telegram authentication failed"}), 401

    telegram_id = auth_data['id']
    username = auth_data.get('username', '')

    # Check if database connection exists and create user if needed
    if db.ensure_connection():
        user = db.get_user(telegram_id)
        if not user:
            db.create_user(telegram_id, username)
    
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
                if not db.ensure_connection():
                    print("Database connection unavailable, cannot process model")
                    send_message(chat_id, "Sorry, our database is currently unavailable. Please try again later.", TELEGRAM_BOT_TOKEN)
                    return jsonify({"status": "error", "msg": "Database connection unavailable"}), 500
                    
                file_data = download_telegram_file(file_id, TELEGRAM_BOT_TOKEN)
                
                if file_data:
                    print(f"File downloaded successfully, size: {file_data['size']} bytes")
                    # Add telegram_id to file_data for tracking
                    file_data['telegram_id'] = chat_id
                    # Save to storage and get URL
                    model_url = db.save_model(file_data, BASE_URL)
                    
                    if model_url:
                        print(f"Model saved successfully, URL: {model_url}")
                        # Get the bot username for creating the Mini App URL
                        bot_info = get_bot_info(TELEGRAM_BOT_TOKEN)
                        bot_username = bot_info.get('username', '') if bot_info else ''
                        
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
                        send_webapp_button(chat_id, response_text, keyboard, TELEGRAM_BOT_TOKEN)
                        
                        return jsonify({"status": "ok"}), 200
                    else:
                        print("Failed to save model to storage")
                        send_message(chat_id, "Failed to store your 3D model. Database error.", TELEGRAM_BOT_TOKEN)
                else:
                    print("Failed to download file from Telegram")
                    send_message(chat_id, "Failed to download your file from Telegram. Please try again.", TELEGRAM_BOT_TOKEN)
            except psycopg2.Error as dbe:
                print(f"Database error processing 3D model: {dbe}")
                send_message(chat_id, f"Database error: {str(dbe)[:100]}. Please contact the administrator.", TELEGRAM_BOT_TOKEN)
            except Exception as e:
                import traceback
                print(f"Error processing 3D model: {e}")
                print(traceback.format_exc())
                send_message(chat_id, "Failed to process your 3D model. Please try again.", TELEGRAM_BOT_TOKEN)
        else:
            send_message(chat_id, "Please send a 3D model file (.glb, .gltf, or .fbx).", TELEGRAM_BOT_TOKEN)
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
        
        send_message(chat_id, response_text, TELEGRAM_BOT_TOKEN)
    
    return jsonify({"status": "ok"}), 200

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
    model_list = db.get_models_for_user(telegram_id)
    
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
    
    model_id = db.add_model_for_user(telegram_id, model_name, model_url)
    
    if model_id:
        # Successful response
        return jsonify({
            "id": model_id,
            "name": model_name,
            "url": model_url,
            "status": "success"
        }), 201
    else:
        return jsonify({
            "error": "DatabaseError",
            "message": "Failed to add model", 
            "status": "error"
        }), 500

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
        if not db.ensure_connection():
            print("❌ Database connection unavailable")
            return jsonify({
                "error": "DatabaseUnavailable",
                "message": "Database connection unavailable",
                "status": "error"
            }), 503
        
        # Reset any failed transaction state
        db.rollback()
        
        # Extract the UUID from the URL if needed
        # Sometimes model_id is the UUID, sometimes it's in the URL
        extracted_uuid = extract_uuid_from_text(model_id)
        if extracted_uuid:
            print(f"📋 Extracted UUID from model_id: {extracted_uuid}")
        
        content = None
        found_model = False
        
        # STEP 1: Check models table using the URL
        url_result = db.execute(
            "SELECT id, model_url FROM models WHERE model_url LIKE %s", 
            (f"%{model_id}%",), 
            fetch='one'
        )
        
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
            large_result = db.execute(
                "SELECT content FROM large_model_content WHERE model_id = %s", 
                (extracted_uuid,), 
                fetch='one'
            )
            
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
            all_large_models = db.execute(
                "SELECT model_id, content FROM large_model_content LIMIT 50", 
                fetch='all'
            )
            
            if all_large_models:
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
        db.rollback()
            
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
    return generate_threejs_viewer_html(model_url, file_extension)

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
        if db.ensure_connection():
            try:
                # Also get the model_name to determine correct file extension
                result = db.execute(
                    "SELECT model_url, model_name FROM models WHERE model_url LIKE %s", 
                    (f"%{uuid_param}%",), 
                    fetch='one'
                )
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
    js_model_url = model_url.replace("'", "\\'") if model_url else ''
    
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
        if not db.ensure_connection():
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
        db.execute("BEGIN")
        
        # First, check if the large_model_content table exists
        db.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'large_model_content'
            )
        """)
        
        if not db.fetchone()[0]:
            # Create large_model_content table if it doesn't exist
            print("📋 Creating large_model_content table")
            db.execute("""
                CREATE TABLE large_model_content (
                    model_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Check if content_size column exists in models table
        db.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'models' AND column_name = 'content_size'
            )
        """)
        
        if not db.fetchone()[0]:
            # Add content_size column if it doesn't exist
            print("📋 Adding content_size column to models table")
            db.execute("ALTER TABLE models ADD COLUMN content_size BIGINT")
            
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
            db.execute(
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
                db.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content_size, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, content_size, datetime.now())
                )
                print(f"✅ Model reference stored in models table")
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"⚠️ Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    db.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s)",
                        (telegram_id, filename, model_url)
                    )
                else:
                    raise
        else:
            # For smaller models, store the content directly
            print(f"📊 Standard content size ({content_size} bytes), storing directly")
            try:
                db.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content, content_size, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, file_data['content'], content_size, datetime.now())
                )
                print(f"✅ Model with content stored in models table")
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"⚠️ Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    db.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url, content) VALUES (%s, %s, %s, %s)",
                        (telegram_id, filename, model_url, file_data['content'])
                    )
                else:
                    raise
        
        # Commit the transaction
        db.execute("COMMIT")
        print(f"✅ Successfully saved model {model_id} to database")
        
        # For debugging, try to verify the content was stored
        try:
            db.execute("SELECT model_id FROM large_model_content WHERE model_id = %s", (model_id,))
            if db.fetchone():
                print(f"✅ Verified: Content exists in large_model_content table")
            else:
                print(f"⚠️ Warning: Content not found in large_model_content table")
        except Exception as verify_err:
            print(f"⚠️ Error verifying content: {verify_err}")
        
        # Return the path portion for the model
        return model_path
        
    except Exception as e:
        # Rollback in case of error
        db.execute("ROLLBACK")
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
                db.execute(
                    "UPDATE users SET status = %s WHERE telegram_id = %s",
                    ("error", chat_id)
                )
                db.execute("COMMIT")
                
                # Send error message to user
                send_message(
                    chat_id=chat_id,
                    text="Failed to process your 3D model. Please try again.",
                    bot_token=TELEGRAM_BOT_TOKEN
                )
                return jsonify({"error": "Failed to save model to storage"}), 500
            
            # Update the user's status and model URL in the database
            try:
                db.execute(
                    "UPDATE users SET status = %s, model_url = %s WHERE telegram_id = %s",
                    ("completed", model_url, chat_id)
                )
                db.execute("COMMIT")
            except Exception as db_error:
                print(f"Database update error: {db_error}")
                # If we can't update the database but saved the model, still try to notify the user
            
            # Send success message to user
            try:
                public_url = f"{BASE_URL}{model_url}"
                send_message(
                    chat_id,
                    f"Your 3D model is ready! View it here: {public_url}",
                    bot_token=TELEGRAM_BOT_TOKEN
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
            db.execute(
                "UPDATE users SET status = %s WHERE telegram_id = %s",
                ("failed", chat_id)
            )
            db.execute("COMMIT")
            
            # Send error message to user
            send_message(
                chat_id=chat_id,
                text=f"Sorry, we couldn't create your 3D model. Error: {error}",
                bot_token=TELEGRAM_BOT_TOKEN
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
        if not db.ensure_connection():
            return jsonify({"error": "Database connection unavailable"}), 500
            
        # First, try to rollback any failed transaction to get clean state
        db.execute("ROLLBACK")
            
        # Check for model in models table
        models = db.execute(
            "SELECT id, telegram_id, model_name, model_url FROM models WHERE model_url LIKE %s", 
            (f"%{model_id}%",), 
            fetch='all'
        )
        
        models_info = []
        for model in models:
            models_info.append({
                "id": model[0],
                "telegram_id": model[1],
                "model_name": model[2],
                "model_url": model[3]
            })
            
        # Check in large_model_content table
        large_model = db.execute(
            "SELECT model_id FROM large_model_content WHERE model_id = %s", 
            (model_id,), 
            fetch='one'
        )
        
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
        db.execute("ROLLBACK")
            
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
        if not db.ensure_connection():
            return jsonify({"error": "Database connection unavailable"}), 500
            
        # Reset transaction state
        db.execute("ROLLBACK")
            
        # Search by filename
        models = db.execute(
            "SELECT id, telegram_id, model_name, model_url FROM models WHERE model_name = %s", 
            (filename,), 
            fetch='all'
        )
        
        results = []
        for model in models:
            model_id = model[0]
            telegram_id = model[1]
            model_name = model[2]
            model_url = model[3]
            
            # Check if content exists
            content_result = db.execute(
                "SELECT content FROM models WHERE id = %s", 
                (model_id,), 
                fetch='one'
            )
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
        db.execute("ROLLBACK")
            
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)