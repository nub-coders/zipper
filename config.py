import os
import queue
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Bot configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
FORCE_SUBSCRIBE = os.getenv("FORCE_SUBSCRIBE", "true").lower() == "true"

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# Binance API credentials for deposit verification
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Dynamic conversion based on env var (default 95)
USDT_TO_INR = float(os.getenv("USDT_TO_INR", "95"))

# Crypto payment amounts (USDT)
CRYPTO_USDT_AMOUNTS = {
    "weekly": round(15 / USDT_TO_INR, 2),
    "monthly": round(50 / USDT_TO_INR, 2)
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
# Per-user state tracking (sets of user_ids)
downloading_users = set()
zipping_users = set()
uploading_users = set()
user_ids = {}
time_left = 0
timeout = None
cancel_requested = set()  # set of user_ids requesting cancellation