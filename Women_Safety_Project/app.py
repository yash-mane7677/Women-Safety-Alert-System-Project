import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Configuration Loading ---
# Tries to load credentials from a local config.json file.
# This ensures sensitive data is not hardcoded.
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
    USER_NAME = config['user_details']['name']
    TELEGRAM_CONFIG = config['telegram_credentials']
    EMAIL_CONFIG = config['email_credentials']
    EMERGENCY_CONTACTS = config['emergency_contacts']
except FileNotFoundError:
    print("FATAL ERROR: config.json not found. The server cannot start.")
    exit()
except KeyError as e:
    print(f"FATAL ERROR: Missing key in config.json: {e}")
    exit()

def send_email_alert(contact, location_link):
    """Sends an email alert to a single contact."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_CONFIG['sender_email']
    msg['To'] = contact['email']
    msg['Subject'] = f"Emergency Alert from {USER_NAME}"
    
    body = f"""
    This is an automated emergency alert from {USER_NAME}.
    They have triggered an SOS alert and may be in need of immediate assistance.
    Their approximate location is: {location_link}
    Please try to contact them immediately.
    """
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG['sender_email'], contact['email'], text)
        server.quit()
        print(f"Successfully sent email to {contact['name']} at {contact['email']}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to send email to {contact['name']}. Details: {e}")
        return False

def send_telegram_alert(location_link):
    """Sends a Telegram message to the specified chat ID."""
    bot_token = TELEGRAM_CONFIG.get('bot_token')
    chat_id = TELEGRAM_CONFIG.get('chat_id')
    
    if not bot_token or 'PASTE' in bot_token or not chat_id or 'PASTE' in chat_id:
        print("ERROR: Telegram bot_token or chat_id is missing or not updated in config.json")
        return False
        
    message = f"""
    🔴 **EMERGENCY SOS ALERT** 🔴
    
    From: **{USER_NAME}**
    
    An SOS alert has been triggered. Immediate assistance may be required.
    
    📍 **Approximate Location:**
    {location_link}
    """
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        print(f"Successfully sent Telegram alert to Chat ID {chat_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to send Telegram alert. Details: {e}")
        print("Response from Telegram:", response.text if 'response' in locals() else "No response")
        return False

@app.route('/api/trigger-alert', methods=['POST'])
def trigger_alert():
    """Endpoint to handle the SOS alert."""
    data = request.json
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if not lat or not lon:
        return jsonify({"status": "error", "message": "Missing location data"}), 400
        
    print(f"Received alert trigger for location: Lat={lat}, Lon={lon}")
    
    location_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    telegram_success = send_telegram_alert(location_link)
    
    email_results = [send_email_alert(contact, location_link) for contact in EMERGENCY_CONTACTS]
        
    if telegram_success or any(email_results):
        return jsonify({"status": "success", "message": "Alerts sent."})
    else:
        return jsonify({"status": "error", "message": "All alert methods failed. Check server configuration."}), 500

if __name__ == '__main__':
    print("Starting Women Safety Alert System API...")
    print(f"Listening for requests on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
    