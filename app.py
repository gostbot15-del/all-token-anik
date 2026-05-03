from flask import Flask, jsonify, request
from flask_caching import Cache
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import my_pb2
import output_pb2
import json
import time
from datetime import datetime
import base64
import warnings
from urllib3.exceptions import InsecureRequestWarning
import logging
from functools import wraps

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable SSL warning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Constants
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

# Flask setup
app = Flask(__name__)

# Vercel-এ Cache কনফিগারেশন (SimpleCache কাজ করবে)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 25200})

# রেট্রি ডেকোরেটর (Vercel-এর জন্য টাইমআউট কমিয়ে ২ সেকেন্ড)
def retry(max_attempts=2, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry(max_attempts=2, delay=1)
def get_oauth_token(password, uid):
    """Access Token এবং Open ID বের করে (Vercel-এর জন্য টাইমআউট কমিয়ে 8 সেকেন্ড)"""
    try:
        url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close"
        }
        data = {
            "uid": uid,
            "password": password,
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067"
        }
        # Vercel-এর 10 সেকেন্ড টাইমআউটের মধ্যে রাখতে 8 সেকেন্ড টাইমআউট
        res = requests.post(url, headers=headers, data=data, timeout=8, verify=False)
        
        if res.status_code != 200:
            logger.error(f"OAuth failed with status: {res.status_code}")
            return None
            
        token_json = res.json()
        if "access_token" in token_json and "open_id" in token_json:
            logger.info("OAuth token obtained successfully")
            return token_json
        else:
            logger.error("Missing access_token or open_id in response")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("OAuth request timeout")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("OAuth connection error")
        return None
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return None

def encrypt_message(key, iv, plaintext):
    """Data encrypt করে"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    return cipher.encrypt(padded_message)

def parse_response(content):
    """Response parse করে"""
    response_dict = {}
    lines = content.split("\n")
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            response_dict[key.strip()] = value.strip().strip('"')
    return response_dict

def decode_jwt_payload(jwt_token):
    """JWT token থেকে payload ডিকোড করে"""
    try:
        if not jwt_token:
            return {}
        parts = jwt_token.split('.')
        if len(parts) == 3:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded_payload = base64.b64decode(payload)
            return json.loads(decoded_payload)
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
    return {}

@retry(max_attempts=2, delay=1)
def get_jwt_token(open_id, access_token):
    """JWT Token পাওয়ার চেষ্টা করে (Vercel-এর জন্য টাইমআউট কমিয়ে 8 সেকেন্ড)"""
    try:
        game_data = my_pb2.GameData()
        game_data.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_data.game_name = "free fire"
        game_data.game_version = 1
        game_data.version_code = "1.108.3"
        game_data.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
        game_data.device_type = "Handheld"
        game_data.network_provider = "Verizon Wireless"
        game_data.connection_type = "WIFI"
        game_data.screen_width = 1280
        game_data.screen_height = 960
        game_data.dpi = "240"
        game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
        game_data.total_ram = 5951
        game_data.gpu_name = "Adreno (TM) 640"
        game_data.gpu_version = "OpenGL ES 3.0"
        game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
        game_data.ip_address = "172.190.111.97"
        game_data.language = "en"
        game_data.open_id = open_id
        game_data.access_token = access_token
        game_data.platform_type = 4
        game_data.device_form_factor = "Handheld"
        game_data.device_model = "Asus ASUS_I005DA"
        game_data.field_60 = 32968
        game_data.field_61 = 29815
        game_data.field_62 = 2479
        game_data.field_63 = 914
        game_data.field_64 = 31213
        game_data.field_65 = 32968
        game_data.field_66 = 31213
        game_data.field_67 = 32968
        game_data.field_70 = 4
        game_data.field_73 = 2
        game_data.library_path = "/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/lib/arm"
        game_data.field_76 = 1
        game_data.apk_info = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/base.apk"
        game_data.field_78 = 6
        game_data.field_79 = 1
        game_data.os_architecture = "32"
        game_data.build_number = "2019117877"
        game_data.field_85 = 1
        game_data.graphics_backend = "OpenGLES2"
        game_data.max_texture_units = 16383
        game_data.rendering_api = 4
        game_data.marketplace = "3rd_party"
        game_data.encryption_key = "KqsHT2B4It60T/65PGR5PXwFxQkVjGNi+IMCK3CFBCBfrNpSUA1dZnjaT3HcYchlIFFL1ZJOg0cnulKCPGD3C3h1eFQ="
        game_data.total_storage = 111107
        game_data.field_97 = 1
        game_data.field_98 = 1
        game_data.field_99 = "4"
        game_data.field_100 = "4"

        serialized_data = game_data.SerializeToString()
        encrypted_data = encrypt_message(AES_KEY, AES_IV, serialized_data)
        edata = binascii.hexlify(encrypted_data).decode()

        url = "https://loginbp.common.ggbluefox.com/MajorLogin"
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/octet-stream",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }

        # Vercel-এর 10 সেকেন্ড টাইমআউটের জন্য 8 সেকেন্ড সেট
        response = requests.post(url, data=bytes.fromhex(edata), headers=headers, timeout=8, verify=False)

        if response.status_code == 200:
            example_msg = output_pb2.Garena_420()
            try:
                example_msg.ParseFromString(response.content)
                response_dict = parse_response(str(example_msg))
                jwt_token = response_dict.get("token")
                if jwt_token:
                    logger.info("JWT token obtained successfully")
                    return jwt_token
                else:
                    logger.warning("No token in response")
                    return None
            except Exception as e:
                logger.error(f"Parse error: {e}")
                return None
        else:
            logger.error(f"HTTP Error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("JWT request timeout")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("JWT connection error")
        return None
    except Exception as e:
        logger.error(f"JWT error: {e}")
        return None

@app.route('/token', methods=['GET'])
@cache.cached(timeout=25200, query_string=True)
def get_complete_token():
    """UID এবং Password দিয়ে লাইভ JWT টোকেন বের করে সব তথ্য দেখাবে"""
    uid = request.args.get('uid')
    password = request.args.get('password')

    if not uid or not password:
        return jsonify({
            "success": False,
            "error": "Both uid and password parameters are required",
            "example": "/token?uid=123456789&password=yourpassword"
        }), 400

    # OAuth Token পাওয়া
    try:
        token_data = get_oauth_token(password, uid)
        if not token_data:
            return jsonify({
                "success": False,
                "uid": uid,
                "status": "invalid",
                "message": "Wrong UID or Password. Please check and try again.",
                "error_code": "AUTH_FAILED"
            }), 401
    except Exception as e:
        logger.error(f"OAuth exception: {e}")
        return jsonify({
            "success": False,
            "error": "OAuth server is temporarily unavailable. Please try again.",
            "error_code": "SERVER_ERROR"
        }), 503

    open_id = token_data.get('open_id')
    access_token = token_data.get('access_token')

    # JWT Token পাওয়া
    try:
        jwt_token = get_jwt_token(open_id, access_token)
        
        if not jwt_token:
            return jsonify({
                "success": False,
                "error": "JWT Token পাওয়া যায়নি। গেম সার্ভার রেসপন্স দিচ্ছে না।",
                "uid": uid,
                "error_code": "JWT_FETCH_FAILED",
                "suggestion": "Please try again after a few seconds."
            }), 503
    except Exception as e:
        logger.error(f"JWT exception: {e}")
        return jsonify({
            "success": False,
            "error": "Game server is busy. Please try again.",
            "error_code": "SERVER_BUSY"
        }), 503

    # JWT Token ডিকোড করে তথ্য বের করা
    jwt_payload = decode_jwt_payload(jwt_token)
    
    current_time = int(time.time())
    
    response_data = {
        "success": True,
        "account_id": jwt_payload.get("account_id", uid),
        "agora_env": "live",
        "create_time": jwt_payload.get("iat", current_time),
        "expiry_time": jwt_payload.get("exp", current_time + 1296000),
        "ip_region": jwt_payload.get("country_code", "IN"),
        "lock_region": jwt_payload.get("lock_region", jwt_payload.get("noti_region", "ME")),
        "noti_region": jwt_payload.get("noti_region", "ME"),
        "main_platform": jwt_payload.get("external_type", 4),
        "platform": jwt_payload.get("external_type", 4),
        "scope": ["get_user_info", "get_friends", "payment", "send_request"],
        "server": "https://clientbp.ggpolarbear.com",
        "ttl": jwt_payload.get("exp", current_time + 1296000) - current_time,
        "data_uid": jwt_payload.get("external_uid", uid),
        "open_id": open_id,
        "token": jwt_token,
        "access_token": access_token
    }
    
    return jsonify(response_data), 200

@app.route('/health', methods=['GET'])
def health_check():
    """হেলথ চেক এন্ডপয়েন্ট"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "name": "Free Fire Live Token API",
        "version": "6.1",
        "author": "@only1piecs",
        "description": "UID এবং পাসওয়ার্ড দিয়ে লাইভ JWT টোকেন বের করে (Vercel Optimized)",
        "endpoint": "/token?uid=UID&password=PW",
        "health_check": "/health",
        "vercel_note": "Due to Vercel 10s timeout, retry mechanism reduced to 2 attempts"
    })

# Vercel-এর জন্য handler
app_handler = app

# লোকাল রানের জন্য (ঐচ্ছিক)
if __name__ == '__main__':
    print("="*60)
    print("🚀 Free Fire Live Token API Started (Vercel Optimized)")
    print("="*60)
    print(f"📍 Usage: http://localhost:5000/token?uid=YOUR_UID&password=YOUR_PW")
    print(f"📍 Health Check: http://localhost:5000/health")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)