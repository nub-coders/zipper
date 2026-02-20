from datetime import datetime
import time
from typing import Dict, Any
from config import collection


class UserStats:
    """Track per-user daily statistics backed by MongoDB."""

    def __init__(self):
        self.today = datetime.now().date()

    def _get_today_range(self) -> tuple[int, int]:
        """Return (start_ts, end_ts) for the current day."""
        start = int(time.mktime(self.today.timetuple()))
        return start, start + 86400

    async def update_stats(self, user_id: int, stat_type: str):
        """Increment a daily stat counter.

        stat_type: 'files_sent' | 'zip_with_pass' | 'zip_without_pass' | 'external_uploads'
        """
        start, _ = self._get_today_range()

        # Ensure user document exists with initial stats
        collection.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {
                "stats": {
                    "files_sent": 0,
                    "zip_with_pass": 0,
                    "zip_without_pass": 0,
                    "external_uploads": 0,
                    "last_reset": start,
                }
            }},
            upsert=True,
        )

        # Reset counters if a new day has started
        user = collection.find_one({"user_id": user_id})
        if user and user.get("stats", {}).get("last_reset", 0) < start:
            collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "stats": {
                        "files_sent": 0,
                        "zip_with_pass": 0,
                        "zip_without_pass": 0,
                        "external_uploads": 0,
                        "last_reset": start,
                    }
                }},
            )

        # Increment the specific stat
        collection.update_one(
            {"user_id": user_id},
            {"$inc": {f"stats.{stat_type}": 1}},
        )

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Return the user's daily statistics dictionary."""
        start, _ = self._get_today_range()
        user = collection.find_one({"user_id": user_id})

        default = {
            "files_sent": 0,
            "zip_with_pass": 0,
            "zip_without_pass": 0,
            "external_uploads": 0,
            "last_reset": start,
        }

        if not user or "stats" not in user:
            return default

        return user.get("stats", default)


stats_manager = UserStats()