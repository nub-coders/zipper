import os
import asyncio
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

class SafeQueue:
    """Thread-safe and async-safe queue with locking."""
    def __init__(self):
        self._list = []
        self._lock = asyncio.Lock()

    def put(self, item):
        """Add item to queue (sync method)."""
        self._list.append(item)

    def get(self, *args, **kwargs):
        """Remove and return item from front of queue."""
        if self._list:
            return self._list.pop(0)
        raise IndexError("pop from empty queue")

    def empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._list) == 0

    def qsize(self) -> int:
        """Return queue size."""
        return len(self._list)

    @property
    def queue(self):
        """Return underlying list for iteration."""
        return self._list

    async def async_remove(self, item):
        """Atomically remove an item from queue (async-safe)."""
        async with self._lock:
            try:
                self._list.remove(item)
                return True
            except ValueError:
                return False

# Global runtime state
ggg = os.getcwd()
download_queue = SafeQueue()
# Per-user state tracking (sets of user_ids)
downloading_users = set()
zipping_users = set()
uploading_users = set()
user_ids = {}
time_left = 0
timeout = None
cancel_requested = set()  # set of user_ids requesting cancellation