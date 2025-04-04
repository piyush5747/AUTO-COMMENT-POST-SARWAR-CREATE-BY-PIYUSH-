from flask import Flask, render_template, request, jsonify
import requests
import time
import random
from datetime import datetime, timedelta
import json
import os
from threading import Thread

app = Flask(__name__)

# Configuration
CONFIG_FILE = 'config.json'
COOKIES_FILE = 'cookies.txt'

# Load or initialize config
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'post_id': '',
        'comments': [
            "Nice post! 👍",
            "Great content! 😊",
            "Awesome! 👏",
            "Thanks for sharing! 🙏",
            "Interesting! 🤔"
        ],
        'delay_min': 30,
        'delay_max': 120,
        'max_comments_per_day': 1000,
        'last_comment_time': None,
        'comment_count_today': 0,
        'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
        'current_cookie_index': 0,
        'active_cookies': []
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_cookies():
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, 'r') as f:
            cookies = [line.strip() for line in f if line.strip()]
            return cookies
    return []

def save_cookies(cookies):
    with open(COOKIES_FILE, 'w') as f:
        f.write('\n'.join(cookies))

# Beautiful UI with modern design
@app.route('/')
def index():
    config = load_config()
    cookies = load_cookies()
    return render_template('index.html', 
                         post_id=config['post_id'],
                         comments="\n".join(config['comments']),
                         delay_min=config['delay_min'],
                         delay_max=config['delay_max'],
                         max_comments=config['max_comments_per_day'],
                         comment_count=config['comment_count_today'],
                         cookies="\n".join(cookies),
                         active_cookies=len(config['active_cookies']))

@app.route('/update_config', methods=['POST'])
def update_config():
    config = load_config()
    
    config['post_id'] = request.form.get('post_id', '').strip()
    config['comments'] = [c.strip() for c in request.form.get('comments', '').split('\n') if c.strip()]
    config['delay_min'] = max(10, int(request.form.get('delay_min', 30)))
    config['delay_max'] = max(config['delay_min'] + 10, int(request.form.get('delay_max', 120)))
    config['max_comments_per_day'] = min(1500, max(100, int(request.form.get('max_comments', 1000))))
    
    # Save cookies
    cookies = [c.strip() for c in request.form.get('cookies', '').split('\n') if c.strip()]
    save_cookies(cookies)
    
    save_config(config)
    return jsonify({'status': 'success', 'message': 'Configuration updated!'})

@app.route('/start_commenting', methods=['POST'])
def start_commenting():
    config = load_config()
    cookies = load_cookies()
    
    if not cookies:
        return jsonify({
            'status': 'error',
            'message': 'Please add at least one valid Facebook cookie'
        })
    
    # Check if we need to reset daily counter
    today = datetime.now().strftime('%Y-%m-%d')
    if config['last_reset_date'] != today:
        config['comment_count_today'] = 0
        config['last_reset_date'] = today
        save_config(config)
    
    if config['comment_count_today'] >= config['max_comments_per_day']:
        return jsonify({
            'status': 'error',
            'message': f'Daily limit reached ({config["max_comments_per_day"]} comments). Try again tomorrow.'
        })
    
    if not config['post_id'] or not config['comments']:
        return jsonify({
            'status': 'error',
            'message': 'Please provide Post ID and Comments list'
        })
    
    # Start commenting in background
    thread = Thread(target=comment_loop, args=(config, cookies))
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': f'Commenting process started! ({config["comment_count_today"]}/{config["max_comments_per_day"]} today)',
        'comment_count': config['comment_count_today']
    })

def comment_loop(config, cookies):
    while config['comment_count_today'] < config['max_comments_per_day']:
        # Get next cookie in rotation
        cookie = get_next_cookie(config, cookies)
        if not cookie:
            print("No valid cookies available")
            break
        
        # Make comment
        success = make_comment_with_cookie(config, cookie)
        
        if success:
            config['comment_count_today'] += 1
            config['last_comment_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_config(config)
            
            # Random delay between comments
            delay = random.randint(config['delay_min'], config['delay_max'])
            time.sleep(delay)
        else:
            # If comment failed, try next cookie immediately
            continue

def get_next_cookie(config, cookies):
    # Rotate through cookies
    for _ in range(len(cookies)):
        config['current_cookie_index'] = (config['current_cookie_index'] + 1) % len(cookies)
        cookie = cookies[config['current_cookie_index']]
        
        # Check if cookie is valid
        if is_cookie_valid(cookie):
            if cookie not in config['active_cookies']:
                config['active_cookies'].append(cookie)
                save_config(config)
            return cookie
        else:
            # Remove invalid cookie
            cookies.remove(cookie)
            save_cookies(cookies)
            if cookie in config['active_cookies']:
                config['active_cookies'].remove(cookie)
                save_config(config)
    
    return None

def is_cookie_valid(cookie):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Cookie': cookie
        }
        response = requests.get('https://www.facebook.com/', headers=headers, timeout=10)
        return 'logout' in response.text.lower()
    except:
        return False

def make_comment_with_cookie(config, cookie):
    try:
        # Select a random comment
        comment_text = random.choice(config['comments'])
        
        # Prepare the request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Cookie': cookie,
            'Referer': f'https://www.facebook.com/{config["post_id"]}',
            'Origin': 'https://www.facebook.com',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Get form data first
        post_url = f'https://www.facebook.com/{config["post_id"]}'
        response = requests.get(post_url, headers=headers, timeout=10)
        
        # Extract fb_dtsg and other required parameters
        # (This is simplified - in a real implementation you'd need to parse these from the response)
        fb_dtsg = 'NA'
        if 'fb_dtsg' in response.text:
            fb_dtsg = response.text.split('fb_dtsg":"')[1].split('"')[0]
        
        # Prepare comment data
        data = {
            'fb_dtsg': fb_dtsg,
            'comment_text': comment_text,
            'source': 'feed'
        }
        
        # Make the comment request
        comment_url = f'https://www.facebook.com/ajax/ufi/modify.php'
        response = requests.post(comment_url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200 and '"error":0' in response.text:
            print(f"Comment posted successfully using cookie")
            return True
        else:
            print(f"Error posting comment: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception while posting comment: {str(e)}")
        return False

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)