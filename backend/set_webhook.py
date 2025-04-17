import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://axiscore.onrender.com/webhook')

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message"]
    }
    
    response = requests.post(url, json=payload)
    print(f"Webhook set response: {response.json()}")
    
    # Get webhook info to verify
    info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    info_response = requests.get(info_url)
    print(f"Webhook info: {info_response.json()}")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        exit(1)
        
    set_webhook()
    print(f"Webhook URL: {WEBHOOK_URL}") 