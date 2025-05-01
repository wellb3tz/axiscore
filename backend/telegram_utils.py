import os
import base64
import requests
import hashlib
import hmac
import json

def check_telegram_auth(data, bot_secret):
    """
    Verify the authentication data received from Telegram.
    
    Args:
        data: The authentication data from Telegram
        bot_secret: The bot's secret token (second part of the bot token)
        
    Returns:
        bool: True if authentication is valid, False otherwise
    """
    check_hash = data.pop('hash')
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(bot_secret.encode()).digest()
    hmac_string = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac_string == check_hash

def send_message(chat_id, text, bot_token):
    """
    Send a plain text message to a Telegram chat.
    
    Args:
        chat_id: The ID of the chat to send the message to
        text: The text of the message
        bot_token: The Telegram bot token
        
    Returns:
        The response from the Telegram API
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    return requests.post(url, json=payload)

def send_inline_button(chat_id, text, button_text, button_url, bot_token):
    """
    Send a message with an inline button to a Telegram chat.
    
    Args:
        chat_id: The ID of the chat to send the message to
        text: The text of the message
        button_text: The text on the button
        button_url: The URL the button will open
        bot_token: The Telegram bot token
        
    Returns:
        The response from the Telegram API
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
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
    return requests.post(url, json=payload)

def send_webapp_button(chat_id, text, keyboard, bot_token):
    """
    Send a message with a complex keyboard to a Telegram chat.
    
    Args:
        chat_id: The ID of the chat to send the message to
        text: The text of the message
        keyboard: The keyboard markup object
        bot_token: The Telegram bot token
        
    Returns:
        The response from the Telegram API
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': keyboard
    }
    return requests.post(url, json=payload)

def download_telegram_file(file_id, bot_token, emergency_flag=False):
    """
    Download a file from Telegram servers using its file_id and return content.
    
    Args:
        file_id: The file_id to download
        bot_token: The Telegram bot token
        emergency_flag: If True, will bypass download (emergency stop)
        
    Returns:
        dict: A dictionary containing the file data, or None if download failed
    """
    # Check emergency flag first - bypass download if active
    if emergency_flag:
        print(f"Emergency flag active - bypassing download for file: {file_id}")
        return None
        
    try:
        # Get file path from Telegram
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
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
            download_url = f"https://api.telegram.org/file/bot{bot_token}/{telegram_file_path}"
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

def get_bot_info(bot_token):
    """
    Get information about the bot from Telegram API.
    
    Args:
        bot_token: The Telegram bot token
        
    Returns:
        dict: The bot information or None if failed
    """
    try:
        bot_info_url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(bot_info_url)
        bot_info = response.json()
        
        if bot_info.get('ok'):
            return bot_info.get('result', {})
        return None
    except Exception as e:
        print(f"Error getting bot info: {e}")
        return None 