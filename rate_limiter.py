import time
import asyncio


class GlobalRateLimiter:
    """Rate-limit actions per user within a sliding time window.

    Uses asyncio.Lock instead of threading.Lock since the bot is fully async.
    """

    def __init__(self, max_actions: int, window_seconds: int):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self.user_actions: dict[int, list[float]] = {}
        self._lock = asyncio.Lock()

    def is_allowed(self, user_id: int) -> bool:
        """Synchronous check — safe for use from async context (no await)."""
        now = time.time()
        actions = self.user_actions.get(user_id, [])
        # Keep only actions within the time window
        actions = [t for t in actions if now - t < self.window_seconds]

        if len(actions) >= self.max_actions:
            self.user_actions[user_id] = actions
            return False

        actions.append(now)
        self.user_actions[user_id] = actions
        return True


rate_limiter = GlobalRateLimiter(max_actions=40, window_seconds=60)
