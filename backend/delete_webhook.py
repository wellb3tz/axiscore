import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def delete_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    
    response = requests.post(url)
    print(f"Webhook deletion response: {response.json()}")
    
    # Get webhook info to verify
    info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    info_response = requests.get(info_url)
    print(f"Webhook info after deletion: {info_response.json()}")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        exit(1)
        
    delete_webhook()
    print("Webhook has been deleted.") 