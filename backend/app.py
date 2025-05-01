import os
import psycopg2
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response, redirect
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
# Import archive utilities
import archive_utils
from archive_utils import (
    extract_archive,
    find_3d_model_files,
    cleanup_extraction
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
# Admin chat IDs for special commands (comma-separated list)
ADMIN_CHAT_IDS = os.getenv('ADMIN_CHAT_IDS', '')

# Track files being processed to prevent loops
PROCESSING_FILES = set()
PROCESSING_TIMES = {}
MAX_PROCESSING_TIME = 300  # seconds (5 minutes) before automatically clearing a processing lock

# "Circuit breaker" for stubborn webhooks
IGNORE_ALL_ARCHIVES = False
LAST_RESET_TIME = 0

# Perform initialization clean-up on app startup
print("🚀 Starting application - performing initialization cleanup")
# Reset processing state on app startup to prevent stale state
PROCESSING_FILES.clear()
PROCESSING_TIMES.clear()
# Ensure circuit breaker is off on fresh start
IGNORE_ALL_ARCHIVES = False
print(f"✅ Processing state reset: files={len(PROCESSING_FILES)}, circuit breaker={IGNORE_ALL_ARCHIVES}")

# Helper function to clean up processing state
def clear_processing_state(file_id):
    """Remove a file from processing tracking"""
    PROCESSING_FILES.discard(file_id)
    PROCESSING_TIMES.pop(file_id, None)

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
    # Declare all globals at the beginning of the function
    global IGNORE_ALL_ARCHIVES, LAST_RESET_TIME
    
    # If it's a GET request, just return a simple status
    if request.method == 'GET':
        return jsonify({
            "status": "online",
            "message": "Telegram webhook is active. Please use POST requests for webhook communication."
        })
    
    # Handle POST request (actual webhook)
    try:
        data = request.json
        
        # Extract message data
        message = data.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        # Check if IGNORE_ALL_ARCHIVES is active BEFORE any other processing, regardless of command
        # This ensures that if a previous emergency command was processed, we immediately respect it
        if IGNORE_ALL_ARCHIVES and message.get('document'):
            file_name = message.get('document', {}).get('file_name', 'unknown file')
            print(f"EMERGENCY STOP ACTIVE - ignoring file {file_name}")
            try:
                if chat_id:
                    send_message(chat_id, "🚨 Processing is currently disabled. Use /enable to re-enable processing.", TELEGRAM_BOT_TOKEN)
            except Exception as e:
                print(f"Error sending message: {e}")
            return jsonify({"status": "stopped", "message": "Processing is disabled"}), 200
        
        # EMERGENCY ESCAPE HATCH - Check for emergency command before anything else
        # Process this in a separate try block to ensure it runs even if other parts fail
        try:
            if text and chat_id:
                if text.lower() == '/911':
                    # This is a nuclear option that will be processed even during loops
                    IGNORE_ALL_ARCHIVES = True
                    
                    # Clear ALL processing
                    file_ids_to_remove = list(PROCESSING_FILES)
                    for file_id in file_ids_to_remove:
                        clear_processing_state(file_id)
                    
                    # Print confirmation to server logs
                    print(f"🚨 EMERGENCY STOP triggered by user {chat_id} with command {text}")
                    
                    # Clear ALL failed archives if DB is available
                    try:
                        if db.ensure_connection():
                            db.execute("DELETE FROM failed_archives")
                            db.commit()
                    except Exception as db_err:
                        print(f"Non-critical DB error during emergency stop: {db_err}")
                    
                    # Send direct response to show the command was accepted
                    try:
                        send_message(chat_id, "🚨 EMERGENCY STOP EXECUTED! All processing has been halted.", TELEGRAM_BOT_TOKEN)
                    except Exception as msg_err:
                        print(f"Error sending emergency confirmation: {msg_err}")
                    
                    return jsonify({"status": "ok", "message": "Emergency stop executed"}), 200
        except Exception as emergency_err:
            print(f"Error processing emergency command: {emergency_err}")
            # Still try to return a response
            if chat_id:
                try:
                    send_message(chat_id, "Error processing emergency command. Please contact administrator.", TELEGRAM_BOT_TOKEN)
                except:
                    pass
            return jsonify({"status": "error", "message": f"Emergency command error: {str(emergency_err)}"}), 500
        
        # Rest of the webhook processing
        # Clean up any stale processing locks
        current_time = datetime.now().timestamp()
        stale_files = []
        for file_id in PROCESSING_FILES:
            start_time = PROCESSING_TIMES.get(file_id, 0)
            if current_time - start_time > MAX_PROCESSING_TIME:
                stale_files.append(file_id)
        
        # Remove stale files
        for file_id in stale_files:
            clear_processing_state(file_id)
            print(f"Automatically cleared stale processing lock for file: {file_id}")
    
        if not chat_id:
            return jsonify({"status": "error", "msg": "No chat_id found"}), 400
        
        # Check if message contains a document (file)
        if message.get('document'):
            document = message.get('document')
            file_name = document.get('file_name', '')
            file_id = document.get('file_id')
            mime_type = document.get('mime_type', '')
            
            # Check if it's an archive file
            if file_name.lower().endswith(('.rar', '.zip', '.7z')):
                # Emergency circuit breaker - if we're in ignore mode for archives
                if IGNORE_ALL_ARCHIVES:
                    print(f"IGNORED ARCHIVE due to circuit breaker: {file_name}, ID: {file_id}")
                    return jsonify({"status": "ignored", "msg": "Archives temporarily disabled"}), 200
                    
                # Process archive file
                try:
                    print(f"Processing archive: {file_name}, ID: {file_id}")
                    
                    # Print raw data for debugging
                    print(f"DEBUG - Message data: {json.dumps(message, indent=2)}")
                    
                    # Check if this file is already being processed (prevents loops)
                    if file_id in PROCESSING_FILES:
                        print(f"File {file_id} is already being processed, ignoring duplicate webhook")
                        return jsonify({"status": "ignored", "msg": "File already being processed"}), 200
                    
                    # Add to processing set
                    PROCESSING_FILES.add(file_id)
                    PROCESSING_TIMES[file_id] = datetime.now().timestamp()
                    
                    # Ensure database connection before proceeding
                    if not db.ensure_connection():
                        print("Database connection unavailable, cannot process archive")
                        send_message(chat_id, "Sorry, our database is currently unavailable. Please try again later.", TELEGRAM_BOT_TOKEN)
                        clear_processing_state(file_id)
                        return jsonify({"status": "error", "msg": "Database connection unavailable"}), 500
                    
                    # Check if file was already processed and failed before
                    failed_archive = db.execute(
                        "SELECT error FROM failed_archives WHERE file_id = %s",
                        (file_id,),
                        fetch='one'
                    )
                    
                    if failed_archive:
                        print(f"Archive {file_id} previously failed with error: {failed_archive[0]}")
                        send_message(chat_id, f"This archive couldn't be processed previously. Error: {failed_archive[0]}", TELEGRAM_BOT_TOKEN)
                        return jsonify({"status": "error", "msg": "Archive previously failed"}), 200
                    
                    # Send a message to inform the user we're processing the archive
                    send_message(chat_id, f"Processing archive: {file_name}. This may take a moment...", TELEGRAM_BOT_TOKEN)
                    
                    # Download file from Telegram
                    file_data = download_telegram_file(file_id, TELEGRAM_BOT_TOKEN, IGNORE_ALL_ARCHIVES)
                    
                    if not file_data:
                        if IGNORE_ALL_ARCHIVES:
                            print(f"Emergency stop active - skipping download for file: {file_id}")
                            send_message(chat_id, "🚨 Emergency stop is active. Processing has been canceled.", TELEGRAM_BOT_TOKEN)
                            clear_processing_state(file_id)
                            return jsonify({"status": "stopped", "msg": "Processing stopped due to emergency command"}), 200
                        else:
                            print("Failed to download archive from Telegram")
                            send_message(chat_id, "Failed to download your archive from Telegram. Please try again.", TELEGRAM_BOT_TOKEN)
                            # Record failed archive to prevent retry loops
                            try:
                                db.execute(
                                    "INSERT INTO failed_archives (file_id, filename, error, telegram_id) VALUES (%s, %s, %s, %s) ON CONFLICT (file_id) DO NOTHING",
                                    (file_id, file_name, 'download failed', chat_id)
                                )
                                db.commit()
                            except Exception:
                                pass
                            clear_processing_state(file_id)
                            # Return 200 so Telegram does not retry this update
                            return jsonify({"status": "error", "msg": "Failed to download file"}), 200
                    
                    print(f"Archive downloaded successfully, size: {file_data['size']} bytes")
                    
                    # Save the archive to a temporary file
                    temp_file_path = os.path.join(UPLOAD_FOLDER, f"temp_archive_{uuid.uuid4()}{os.path.splitext(file_name)[1]}")
                    try:
                        # Decode base64 content
                        archive_content = base64.b64decode(file_data['content'])
                        
                        # Write to temporary file
                        with open(temp_file_path, 'wb') as f:
                            f.write(archive_content)
                        
                        print(f"Archive saved to temporary file: {temp_file_path}")
                        
                        # Extract the archive
                        extract_result = extract_archive(temp_file_path)
                        
                        if not extract_result['success']:
                            error_msg = extract_result['error']
                            # Provide more specific message for encoding issues
                            user_msg = "Failed to process your archive."
                            if "utf-8" in error_msg.lower() and "decode" in error_msg.lower():
                                user_msg = "Your archive contains files with unsupported encoding. Please ensure all filenames use Latin characters (a-z) without special characters."
                            
                            # Record failed archive in database to prevent reprocessing loops
                            db.execute(
                                "INSERT INTO failed_archives (file_id, filename, error, telegram_id) VALUES (%s, %s, %s, %s)",
                                (file_id, file_name, error_msg, chat_id)
                            )
                            db.commit()
                            
                            send_message(chat_id, f"{user_msg} To try again with a different archive, use the /reset command first.", TELEGRAM_BOT_TOKEN)
                            clear_processing_state(file_id)
                            raise Exception(f"Failed to extract archive: {error_msg}")
                        
                        # Find 3D model files in the extracted directory
                        extract_path = extract_result['extract_path']
                        files_found = extract_result['files']
                        
                        print(f"Extracted {len(files_found)} files from archive")
                        
                        # Find 3D model files
                        model_files = find_3d_model_files(files_found)
                        
                        if not model_files:
                            print("No 3D model files found in archive")
                            send_message(
                                chat_id, 
                                "No 3D model files (.glb, .gltf, .fbx, .obj) found in your archive. Please upload a valid archive containing 3D models.", 
                                TELEGRAM_BOT_TOKEN
                            )
                            # Clean up
                            cleanup_extraction(extract_path)
                            os.remove(temp_file_path)
                            clear_processing_state(file_id)
                            # Record failed archive in database to prevent reprocessing loops
                            try:
                                db.execute(
                                    "INSERT INTO failed_archives (file_id, filename, error, telegram_id) VALUES (%s, %s, %s, %s) ON CONFLICT (file_id) DO NOTHING",
                                    (file_id, file_name, 'no 3D model files found', chat_id)
                                )
                                db.commit()
                            except Exception as e:
                                print(f"Error recording failed archive: {e}")
                            
                            return jsonify({"status": "error", "msg": "No 3D model files found"}), 200
                        
                        print(f"Found {len(model_files)} 3D model files in archive:")
                        for model in model_files:
                            print(f"- {model['filename']} ({model['extension']})")
                        
                        # If multiple model files are found, ask the user which one to use
                        if len(model_files) > 1:
                            # Inform user about the found models
                            model_list = "\n".join([f"{i+1}. {m['filename']}" for i, m in enumerate(model_files)])
                            message_text = f"Found {len(model_files)} 3D models in your archive:\n\n{model_list}\n\nProcessing all models..."
                            send_message(chat_id, message_text, TELEGRAM_BOT_TOKEN)
                        
                        # Process each model file
                        processed_models = []
                        for model_file in model_files:
                            model_path = os.path.join(extract_path, model_file['path'])
                            model_filename = model_file['filename']
                            model_ext = model_file['extension']
                            
                            print(f"Processing model: {model_filename}")
                            
                            # Read the model file
                            with open(model_path, 'rb') as f:
                                model_content = f.read()
                            
                            # Convert to base64 for storage
                            model_base64 = base64.b64encode(model_content).decode('utf-8')
                            
                            # Create file data structure similar to what download_telegram_file returns
                            model_data = {
                                'filename': model_filename,
                                'content': model_base64,
                                'size': len(model_content),
                                'mime_type': f'model/{model_ext[1:]}',  # .glb -> model/glb
                                'telegram_id': chat_id
                            }
                            
                            # Save to storage and get URL
                            model_url = db.save_model(model_data, BASE_URL)
                            
                            if model_url:
                                processed_models.append({
                                    'filename': model_filename,
                                    'url': model_url,
                                    'extension': model_ext
                                })
                                print(f"Model {model_filename} saved successfully, URL: {model_url}")
                            else:
                                print(f"Failed to save model {model_filename} to storage")
                        
                        # Clean up
                        cleanup_extraction(extract_path)
                        os.remove(temp_file_path)
                        
                        if not processed_models:
                            print("Failed to process any models from the archive")
                            send_message(chat_id, "Failed to process any models from your archive. Please try again.", TELEGRAM_BOT_TOKEN)
                            clear_processing_state(file_id)
                            return jsonify({"status": "error", "msg": "Failed to process models"}), 500
                        
                        # Send response to user with all processed models
                        if len(processed_models) == 1:
                            # Single model
                            model = processed_models[0]
                            model_url = model['url']
                            model_filename = model['filename']
                            model_ext = model['extension']
                            
                            # Get the bot username for creating the Mini App URL
                            bot_info = get_bot_info(TELEGRAM_BOT_TOKEN)
                            bot_username = bot_info.get('username', '') if bot_info else ''
                            
                            # Extract UUID from model_url for a cleaner parameter
                            uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
                            uuid_match = re.search(uuid_pattern, model_url)
                            model_uuid = uuid_match.group(1) if uuid_match else "unknown"
                            
                            # Response message
                            response_text = f"Extracted and processed model: {model_filename}\n\nUse one of the buttons below to view it:"
                            
                            # Create a combined keyboard with both options
                            keyboard = {
                                'inline_keyboard': [
                                    [
                                        {
                                            'text': '📱 Open in Axiscore (Recommended)',
                                            'web_app': {
                                                'url': f"{BASE_URL}/miniapp?uuid={model_uuid}&ext={model_ext}"
                                            }
                                        }
                                    ],
                                    [
                                        {
                                            'text': '🌐 Open in Browser',
                                            'url': f"https://wellb3tz.github.io/axiscore/?model={BASE_URL}{model_url}"
                                        }
                                    ]
                                ]
                            }
                            
                            # Send the message with combined keyboard
                            send_webapp_button(chat_id, response_text, keyboard, TELEGRAM_BOT_TOKEN)
                        else:
                            # Multiple models
                            response_text = f"Extracted and processed {len(processed_models)} models from your archive:\n\n"
                            
                            # Send a message for each model
                            send_message(chat_id, response_text, TELEGRAM_BOT_TOKEN)
                            
                            for model in processed_models:
                                model_url = model['url']
                                model_filename = model['filename']
                                model_ext = model['extension']
                                
                                # Extract UUID from model_url
                                uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
                                uuid_match = re.search(uuid_pattern, model_url)
                                model_uuid = uuid_match.group(1) if uuid_match else "unknown"
                                
                                # Model-specific message
                                model_text = f"Model: {model_filename}"
                                
                                # Keyboard for this model
                                keyboard = {
                                    'inline_keyboard': [
                                        [
                                            {
                                                'text': '📱 Open in Axiscore',
                                                'web_app': {
                                                    'url': f"{BASE_URL}/miniapp?uuid={model_uuid}&ext={model_ext}"
                                                }
                                            }
                                        ],
                                        [
                                            {
                                                'text': '🌐 Open in Browser',
                                                'url': f"https://wellb3tz.github.io/axiscore/?model={BASE_URL}{model_url}"
                                            }
                                        ]
                                    ]
                                }
                                
                                # Send message for this model
                                send_webapp_button(chat_id, model_text, keyboard, TELEGRAM_BOT_TOKEN)
                        
                        # Remove from processing set after successful completion
                        clear_processing_state(file_id)
                        return jsonify({"status": "ok"}), 200
                        
                    except Exception as e:
                        print(f"Error processing archive: {e}")
                        # Clean up any temporary files
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                        
                        send_message(chat_id, f"Error processing your archive: {str(e)[:100]}. Please try again.", TELEGRAM_BOT_TOKEN)
                        clear_processing_state(file_id)
                        return jsonify({"status": "error", "msg": str(e)}), 500
                except Exception as e:
                    print(f"Error processing archive: {e}")
                    send_message(chat_id, "Failed to process your archive. Please try again.", TELEGRAM_BOT_TOKEN)
                    clear_processing_state(file_id)
                    return jsonify({"status": "error", "msg": str(e)}), 500
            
            # Check if it's a 3D model file
            elif file_name.lower().endswith(('.glb', '.gltf', '.fbx', '.obj')) or 'model' in mime_type.lower():
                # Download file from Telegram
                try:
                    print(f"Processing file: {file_name}, ID: {file_id}")
                    
                    # Check if this file is already being processed (prevents loops)
                    if file_id in PROCESSING_FILES:
                        print(f"File {file_id} is already being processed, ignoring duplicate webhook")
                        return jsonify({"status": "ignored", "msg": "File already being processed"}), 200
                    
                    # Add to processing set
                    PROCESSING_FILES.add(file_id)
                    PROCESSING_TIMES[file_id] = datetime.now().timestamp()
                    
                    # Ensure database connection before proceeding
                    if not db.ensure_connection():
                        print("Database connection unavailable, cannot process model")
                        send_message(chat_id, "Sorry, our database is currently unavailable. Please try again later.", TELEGRAM_BOT_TOKEN)
                        clear_processing_state(file_id)
                        return jsonify({"status": "error", "msg": "Database connection unavailable"}), 500
                        
                    # Download file from Telegram with emergency flag
                    file_data = download_telegram_file(file_id, TELEGRAM_BOT_TOKEN, IGNORE_ALL_ARCHIVES)
                    
                    if not file_data:
                        if IGNORE_ALL_ARCHIVES:
                            print(f"Emergency stop active - skipping download for file: {file_id}")
                            send_message(chat_id, "🚨 Emergency stop is active. Processing has been canceled.", TELEGRAM_BOT_TOKEN)
                            clear_processing_state(file_id)
                            return jsonify({"status": "stopped", "msg": "Processing stopped due to emergency command"}), 200
                        else:
                            print("Failed to download file from Telegram")
                            send_message(chat_id, "Failed to download your file from Telegram. Please try again.", TELEGRAM_BOT_TOKEN)
                            # Record failed file to prevent retry loops
                            try:
                                db.execute(
                                    "INSERT INTO failed_archives (file_id, filename, error, telegram_id) VALUES (%s, %s, %s, %s) ON CONFLICT (file_id) DO NOTHING",
                                    (file_id, file_name, 'download failed', chat_id)
                                )
                                db.commit()
                            except Exception:
                                pass
                            clear_processing_state(file_id)
                            # Return 200 so Telegram does not retry this update
                            return jsonify({"status": "error", "msg": "Failed to download file"}), 200
                    
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
                                        'url': f"https://wellb3tz.github.io/axiscore/?model={BASE_URL}{model_url}"
                                    }
                                ]
                            ]
                        }
                        
                        # Send the message with combined keyboard
                        send_webapp_button(chat_id, response_text, keyboard, TELEGRAM_BOT_TOKEN)
                        
                        # Remove from processing set after success
                        clear_processing_state(file_id)
                        return jsonify({"status": "ok"}), 200
                    else:
                        print("Failed to save model to storage")
                        send_message(chat_id, "Failed to store your 3D model. Database error.", TELEGRAM_BOT_TOKEN)
                        clear_processing_state(file_id)
                except psycopg2.Error as dbe:
                    print(f"Database error processing 3D model: {dbe}")
                    send_message(chat_id, f"Database error: {str(dbe)[:100]}. Please contact the administrator.", TELEGRAM_BOT_TOKEN)
                    clear_processing_state(file_id)
                except Exception as e:
                    import traceback
                    print(f"Error processing 3D model: {e}")
                    print(traceback.format_exc())
                    send_message(chat_id, "Failed to process your 3D model. Please try again.", TELEGRAM_BOT_TOKEN)
                    clear_processing_state(file_id)
            else:
                send_message(chat_id, "Please send a 3D model file (.glb, .gltf, or .fbx).", TELEGRAM_BOT_TOKEN)
        # Handle text messages
        else:
            # Check for specific commands
            if text.lower() == '/start':
                response_text = "Welcome to Axiscore 3D Model Viewer! You can send me a 3D model file (.glb, .gltf, .fbx, or .obj) or an archive (.rar, .zip, .7z) containing 3D models, and I'll generate an interactive preview for you."
            elif text.lower() == '/help':
                response_text = """
Axiscore 3D Model Viewer Help:
• Send a 3D model file (.glb, .gltf, .fbx, or .obj) directly to this chat
• Or upload an archive (.rar, .zip, .7z) containing 3D models
• For archives, I'll extract all 3D models inside
• I'll create an interactive viewer link for each model
• Click "Open in Axiscore" to view and interact with your model
• Use pinch/scroll to zoom, drag to rotate
• If you're stuck in a processing loop, use /reset command
                """
            elif text.lower() == '/reset':
                current_time = datetime.now().timestamp()
                
                # Reset failed archives for this user
                if db.ensure_connection():
                    db.execute(
                        "DELETE FROM failed_archives WHERE telegram_id = %s",
                        (chat_id,)
                    )
                    db.commit()
                    
                    # Also clear any processing locks for this user
                    file_ids_to_remove = list(PROCESSING_FILES)
                    
                    for file_id in file_ids_to_remove:
                        clear_processing_state(file_id)
                    
                    # Check if this is a rapid reset (within 60 seconds of previous reset)
                    # If so, enable the circuit breaker as an emergency measure
                    if current_time - LAST_RESET_TIME < 60:
                        IGNORE_ALL_ARCHIVES = True
                        response_text = f"🚨 EMERGENCY RESET detected! Archive processing has been disabled as a circuit breaker. Cleared {len(file_ids_to_remove)} processing locks."
                    else:
                        response_text = f"Reset successful. Cleared {len(file_ids_to_remove)} processing locks. Any archives that previously failed can now be processed again."
                    
                    # Update last reset time
                    LAST_RESET_TIME = current_time
                else:
                    response_text = "Could not reset due to database connection issues. Please try again later."
            elif text.lower() == '/enable':
                IGNORE_ALL_ARCHIVES = False
                response_text = "Processing has been re-enabled."
            elif text.lower() == '/disable':
                IGNORE_ALL_ARCHIVES = True
                response_text = "Processing has been disabled (circuit breaker active)."
            elif text.lower() == '/admin_cleanup' and str(chat_id) in ADMIN_CHAT_IDS.split(','):
                # Special admin command to initialize the failed_archives table and add problematic files
                if db.ensure_connection():
                    # Make sure the table exists
                    db.cursor.execute('''
                        CREATE TABLE IF NOT EXISTS failed_archives (
                            id SERIAL PRIMARY KEY,
                            file_id TEXT NOT NULL UNIQUE,
                            filename TEXT NOT NULL,
                            error TEXT NOT NULL,
                            telegram_id TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    db.commit()
                    
                    # Add any known problematic files by file_id - add the 3D Oasis - Skateboards.rar file
                    try:
                        db.execute(
                            "INSERT INTO failed_archives (file_id, filename, error, telegram_id) VALUES (%s, %s, %s, %s) ON CONFLICT (file_id) DO NOTHING",
                            ("problematic_file_id", "3D Oasis - Skateboards.rar", "utf-8 codec can't decode byte", chat_id)
                        )
                        db.commit()
                        response_text = "Admin cleanup completed. Known problematic files have been added to the block list."
                    except Exception as e:
                        response_text = f"Admin cleanup encountered an error: {str(e)}"
                else:
                    response_text = "Could not perform admin cleanup due to database connection issues."
            elif text.lower() == '/status':
                # Show current processing status for debugging
                processing_count = len(PROCESSING_FILES)
                circuit_breaker = "🔴 ACTIVE" if IGNORE_ALL_ARCHIVES else "🟢 Inactive"
                current_time = datetime.now().timestamp()
                
                # List all file IDs being processed (truncate if too many)
                processing_files_list = list(PROCESSING_FILES)
                if len(processing_files_list) > 5:
                    files_str = ", ".join(processing_files_list[:5]) + f" and {len(processing_files_list) - 5} more"
                else:
                    files_str = ", ".join(processing_files_list) if processing_files_list else "None"
                    
                response_text = f"""System status:
- Files being processed: {processing_count}
- Processing files: {files_str}
- Circuit breaker: {circuit_breaker}
- Last reset: {int(current_time - LAST_RESET_TIME)} seconds ago

Commands:
- /reset - Clear processing queue and failed archives
- /status - Show this status message"""
            elif text.lower() == '/debug':
                # Show all available commands and their descriptions
                response_text = """⚙️ AXISCORE BOT COMMANDS:

Standard Commands:
• /start - Display welcome message and introduction
• /help - Show how to use the bot and available features
• /enable - Turn on file processing
• /disable - Turn off file processing (circuit breaker)
• /reset - Clear failed archives and reset processing state
• /status - Show system status (processing files, circuit breaker state)
• /debug - Show this help message with all commands

Emergency Commands:
• /911 - Emergency stop (breaks any processing loop)

Admin Commands:
• /admin_cleanup - Initialize database tables (admin only)

These commands work even when the bot appears stuck. If the bot is completely unresponsive, please contact the administrator."""
            else:
                # Generic response for other messages
                response_text = f"Send me a 3D model file (.glb, .gltf, .fbx, .obj) or an archive containing 3D models (.rar, .zip, .7z) to view it in Axiscore. You said: {text}"
            
            send_message(chat_id, response_text, TELEGRAM_BOT_TOKEN)
            
            return jsonify({"status": "ok"}), 200

    except Exception as e:
        # Global error handler for the entire webhook
        error_msg = f"Webhook processing error: {str(e)}"
        print(error_msg)
        
        # Try to notify the user if we have a chat_id
        if 'chat_id' in locals() and chat_id:
            try:
                send_message(chat_id, "Sorry, an error occurred processing your request. Please try again later.", TELEGRAM_BOT_TOKEN)
            except:
                pass
        
        # Return error response
        return jsonify({"status": "error", "message": error_msg}), 500

@app.route('/view', methods=['GET'])
def view_model():
    model_url = request.args.get('model')
    if not model_url:
        return jsonify({
            "error": "MissingParameter",
            "message": "No model URL provided",
            "status": "error"
        }), 400
    
    # Get file extension for the model
    file_extension = get_file_extension(model_url)
    
    # Ensure model_url is an absolute URL
    if not model_url.startswith('http'):
        model_url = f"{BASE_URL}{model_url}"
    
    # Redirect to GitHub Pages
    github_url = f"https://wellb3tz.github.io/axiscore/?model={model_url}"
    return redirect(github_url)

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

@app.route('/viewer', methods=['GET'])
def model_viewer():
    # Get model URL and other parameters using our utility function
    model_url, uuid_param, file_extension = get_telegram_parameters(request)
    
    # Return model info as JSON for the frontend to render
    return jsonify({
        "model_url": model_url,
        "uuid": uuid_param,
        "file_extension": file_extension,
        "status": "success"
    })

@app.route('/miniapp', methods=['GET'])
@app.route('/miniapp/', methods=['GET'])
def miniapp():
    """Return model info for the MiniApp frontend."""
    # Get parameters and model URL using our utility function
    model_url, uuid_param, file_extension = get_telegram_parameters(request)
    
    # If direct model_url is provided, redirect to GitHub Pages
    if model_url:
        print(f"Redirecting to GitHub Pages with model URL: {model_url}")
        # Ensure model_url is an absolute URL
        if not model_url.startswith('http'):
            model_url = f"{BASE_URL}{model_url}"
        # Create the full GitHub Pages URL with the model parameter
        github_url = f"https://wellb3tz.github.io/axiscore/?model={model_url}"
        return redirect(github_url)
    
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
                    
                    # Ensure model_url is an absolute URL
                    if not model_url.startswith('http'):
                        model_url = f"{BASE_URL}{model_url}"
                    
                    # Redirect to GitHub Pages with the found model URL
                    github_url = f"https://wellb3tz.github.io/axiscore/?model={model_url}"
                    return redirect(github_url)
                else:
                    print(f"No model found for UUID: {uuid_param}")
            except Exception as e:
                print(f"Error finding model for UUID: {e}")
    
    print(f"Using file extension: {file_extension}")
    print(f"Rendering miniapp with model URL: {model_url}")
    
    # Return model info as JSON for the frontend to render
    return jsonify({
        "model_url": model_url,
        "uuid": uuid_param,
        "file_extension": file_extension,
        "base_url": BASE_URL,
        "status": "success"
    })

@app.route('/help', methods=['GET'])
def help_page():
    # Return API help information as JSON
    return jsonify({
        "api_name": "Axiscore 3D Model Viewer API",
        "description": "This API allows you to view and share 3D models via Telegram.",
        "supported_formats": [
            {"name": "glTF/GLB", "extensions": [".glb", ".gltf"]},
            {"name": "Filmbox", "extensions": [".fbx"]},
            {"name": "Wavefront", "extensions": [".obj"]}
        ],
        "supported_archives": [
            {"name": "RAR", "extensions": [".rar"]},
            {"name": "ZIP", "extensions": [".zip"]},
            {"name": "7-Zip", "extensions": [".7z"]}
        ],
        "features": [
            "Direct 3D model file uploads",
            "Archive extraction with automatic model detection",
            "Multiple model processing from a single archive",
            "Interactive 3D viewer with mobile support"
        ],
        "usage": "Send your 3D model file or archive to the Telegram bot: @AxisCoreBot",
        "status": "success"
    })

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "3D Model Viewer API is running",
        "supported_formats": ["glb", "gltf", "fbx", "obj"],
        "supported_archives": ["rar", "zip", "7z"],
        "features": {
            "model_viewing": True,
            "archive_extraction": True,
            "telegram_integration": True,
            "multi_model_support": True
        }
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
    
    # Try different possible paths for the frontend file
    possible_paths = [
        '../frontend/build/index.html',  # Original relative path
        'frontend/build/index.html',     # Without leading ../
        '/app/frontend/build/index.html' # Absolute path in container
    ]
    
    for possible_path in possible_paths:
        try:
            if os.path.exists(possible_path):
                return send_file(possible_path)
        except:
            continue
            
    # If we can't find the frontend, return a simple message
    return jsonify({
        "error": "Frontend not found",
        "message": "The React frontend build files were not found. Please make sure to build the frontend."
    }), 404

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