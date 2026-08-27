import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
FORCE_SUBSCRIBE = os.getenv("FORCE_SUBSCRIBE", "true").lower() == "true"

# ── Storage backend ───────────────────────────────────────────────────────────
# MongoDB is optional. When MONGO_URL is unset or unreachable we fall back to an
# in-memory collection so the bot can run without any database. In-memory data
# is not persisted across restarts.
MONGO_URL = os.getenv("MONGO_URL", "")

# ── Extraction resource ceilings ──────────────────────────────────────────────
# Enforced *during* extraction by safe_archive, not inferred from archive
# headers (which are attacker-controlled). The default is well below the 2 GB
# upload ceiling because the runtime's ephemeral disk is much smaller than that
# and a decompression bomb otherwise fills it before anything notices.
MAX_EXTRACT_BYTES = int(os.getenv("MAX_EXTRACT_BYTES", 1024 * 1024 * 1024))
MAX_EXTRACT_ENTRIES = int(os.getenv("MAX_EXTRACT_ENTRIES", 2000))
MAX_EXTRACT_SECONDS = int(os.getenv("MAX_EXTRACT_SECONDS", 600))
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", 2 * 1024 * 1024 * 1024))

# ── NuLoader Cloud Storage ────────────────────────────────────────────────────
NULOADER_API_URL = os.getenv("NULOADER_API_URL", "https://files.nubcoders.com").rstrip("/")
NULOADER_API_KEY = os.getenv("NULOADER_API_KEY", "")
NULOADER_EXPIRY_MODE = os.getenv("NULOADER_EXPIRY_MODE", "days_7")


def _init_collection():
    if not MONGO_URL:
        from memory_db import InMemoryCollection
        print("No MONGO_URL set — using in-memory storage (data will not persist).")
        return InMemoryCollection()

    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        # Force a round-trip so an unreachable server fails fast instead of
        # blowing up on the first query.
        client.admin.command("ping")
        print("MongoDB initialized successfully")
        return client["telegram_bot"]["users"]
    except Exception as e:
        from memory_db import InMemoryCollection
        print(f"MongoDB unavailable ({e}) — falling back to in-memory storage.")
        return InMemoryCollection()


collection = _init_collection()

# Bot start time (for uptime calculation)
START_TIME = __import__("time").time()

# Global runtime state
ggg = os.getcwd()

# Import and expose the new user state manager
from user_state import (
    get_state_manager,
    set_downloading,
    set_zipping,
    set_uploading,
    set_extracting,
    is_user_busy,
    get_busy_reason,
    request_cancel,
    clear_cancel,
    is_cancel_requested,
    enqueue_item,
    dequeue_item,
    get_user_queue_size,
    get_total_queue_size,
    get_next_fair_user,
    # Backward-compat sets (kept in sync by the state manager)
    downloading_users,
    zipping_users,
    uploading_users,
    extracting_users,
    cancel_requested,
)

user_ids = {}
time_left = 0
timeout = None