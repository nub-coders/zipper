from datetime import datetime
import asyncio
import time
from typing import Dict, Any
from config import collection

_STAT_KEYS = ("files_sent", "zip_with_pass", "zip_without_pass", "external_uploads")


def _today_start() -> int:
    """Return the start-of-day timestamp for the current date."""
    return int(time.mktime(datetime.now().date().timetuple()))


def _zeroed_stats(start: int) -> Dict[str, Any]:
    return {**{k: 0 for k in _STAT_KEYS}, "last_reset": start}


async def update_stats(user_id: int, stat_type: str):
    """Increment a daily stat counter, resetting first if a new day started.

    stat_type: 'files_sent' | 'zip_with_pass' | 'zip_without_pass' | 'external_uploads'

    Every call goes through ``asyncio.to_thread`` because the Mongo driver is
    synchronous and this runs on the hot path of every download.
    """
    start = _today_start()

    # Ensure user document exists with initial stats
    await asyncio.to_thread(
        collection.update_one,
        {"user_id": user_id},
        {"$setOnInsert": {"stats": _zeroed_stats(start)}},
        upsert=True,
    )

    # Reset counters if a new day has started
    user = await asyncio.to_thread(collection.find_one, {"user_id": user_id})
    if user and user.get("stats", {}).get("last_reset", 0) < start:
        await asyncio.to_thread(
            collection.update_one,
            {"user_id": user_id},
            {"$set": {"stats": _zeroed_stats(start)}},
        )

    # Increment the specific stat
    await asyncio.to_thread(
        collection.update_one,
        {"user_id": user_id},
        {"$inc": {f"stats.{stat_type}": 1}},
    )


async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Return the user's daily statistics dictionary."""
    default = _zeroed_stats(_today_start())
    user = await asyncio.to_thread(collection.find_one, {"user_id": user_id})
    if not user or "stats" not in user:
        return default
    return user.get("stats", default)
