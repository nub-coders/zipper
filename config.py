import os
import queue
from pymongo import MongoClient

# Bot configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# Binance configuration for crypto payments
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Crypto payment amounts (USDT)
CRYPTO_USDT_AMOUNTS = {
    "weekly": 0.18,  # Approximately ₹15 equivalent
    "monthly": 0.60  # Approximately ₹50 equivalent
}

# Initialize MongoDB (single connection for the entire app)
MONGO_URL = os.getenv("MONGO_URL", "")
try:
    client = MongoClient(MONGO_URL)
    db = client['telegram_bot']
    collection = db['users']
    print("MongoDB initialized successfully")
except Exception as e:
    print(f"MongoDB initialization failed: {e}")
    collection = None

# Bot start time (for uptime calculation)
START_TIME = __import__("time").time()

# Global runtime state
ggg = os.getcwd()
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
zipping_in_progress = False
download_in_progress = False
uploading_in_progress = False
user_ids = {}
active_user_id = None
time_left = 0
timeout = None
cancel_requested = set()  # set of user_ids requesting cancellation