"""Thread/async-safe user state management (audit Z-16).

Encapsulates all per-user runtime state behind a locked interface so that
concurrent handlers cannot race on the bare global sets/lists in config.py.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Set

# ──────────────────────────────────────────────────────────────────────────────
# Per-user state
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class UserState:
    """Mutable state for a single user."""
    user_id: int
    # Operation flags
    downloading: bool = False
    zipping: bool = False
    uploading: bool = False
    extracting: bool = False
    # Cancellation
    cancel_requested: bool = False
    # Queue tracking
    queued_items: Deque = field(default_factory=deque)
    # Fair-share accounting
    last_served: float = 0.0


class UserStateManager:
    """Manages per-user state with a single global lock.

    All mutating operations acquire `self._lock` so there are no TOCTOU races
    between the queue processor and the individual handlers.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._states: Dict[int, UserState] = {}
        # Fair-share queue: deque of user_ids who have pending work
        self._fair_queue: Deque[int] = deque()
        # Global idle workers count (for future use)
        self._idle_workers = 0

    # ─── Accessors ────────────────────────────────────────────────────────────

    async def get(self, user_id: int) -> UserState:
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = UserState(user_id=user_id)
            return self._states[user_id]

    # ─── Flag operations (atomic read-modify-write) ──────────────────────────

    async def set_busy(self, user_id: int, op: str, busy: bool = True) -> bool:
        """
        Set/clear a busy flag for a user.

        Returns True if the flag was successfully set (was False before),
        False if it was already True (operation would conflict).
        """
        async with self._lock:
            state = self._states.get(user_id)
            if state is None:
                state = UserState(user_id=user_id)
                self._states[user_id] = state

            flag_map = {
                "downloading": "downloading",
                "zipping": "zipping",
                "uploading": "uploading",
                "extracting": "extracting",
            }
            attr = flag_map.get(op)
            if attr is None:
                return False

            current = getattr(state, attr)
            if busy and current:
                return False  # already busy with this op

            setattr(state, attr, busy)
            return True

    async def is_busy(self, user_id: int) -> bool:
        async with self._lock:
            state = self._states.get(user_id)
            if not state:
                return False
            return state.downloading or state.zipping or state.uploading or state.extracting

    async def busy_reason(self, user_id: int) -> str:
        async with self._lock:
            state = self._states.get(user_id)
            if not state:
                return "idle"
            if state.downloading:
                return "downloading"
            if state.zipping:
                return "compressing"
            if state.uploading:
                return "uploading"
            if state.extracting:
                return "extracting"
            return "idle"

    async def request_cancel(self, user_id: int) -> bool:
        """Mark cancellation request. Returns True if there was an operation to cancel."""
        async with self._lock:
            state = self._states.get(user_id)
            if not state:
                return False
            was_busy = state.downloading or state.zipping or state.uploading or state.extracting
            if was_busy:
                state.cancel_requested = True
            return was_busy

    async def clear_cancel(self, user_id: int):
        async with self._lock:
            state = self._states.get(user_id)
            if state:
                state.cancel_requested = False

    async def is_cancel_requested(self, user_id: int) -> bool:
        async with self._lock:
            state = self._states.get(user_id)
            return state.cancel_requested if state else False

    # ─── Queue management ────────────────────────────────────────────────────

    async def enqueue(self, user_id: int, item):
        """Add an item to the user's queue."""
        async with self._lock:
            state = self._states.get(user_id)
            if state is None:
                state = UserState(user_id=user_id)
                self._states[user_id] = state
            state.queued_items.append(item)
            # Add to fair queue if not already present
            if user_id not in self._fair_queue:
                self._fair_queue.append(user_id)

    async def dequeue(self, user_id: int):
        """Remove and return the next item for a user, or None if empty."""
        async with self._lock:
            state = self._states.get(user_id)
            if not state or not state.queued_items:
                if user_id in self._fair_queue:
                    self._fair_queue.remove(user_id)
                return None
            item = state.queued_items.popleft()
            if not state.queued_items:
                # No more items, remove from fair queue
                if user_id in self._fair_queue:
                    self._fair_queue.remove(user_id)
            return item

    async def queue_size(self, user_id: int) -> int:
        async with self._lock:
            state = self._states.get(user_id)
            return len(state.queued_items) if state else 0

    async def total_queue_size(self) -> int:
        async with self._lock:
            return sum(len(s.queued_items) for s in self._states.values())

    # ─── Fair-share processor ─────────────────────────────────────────────────

    async def get_next_fair_user(self) -> Optional[int]:
        """
        Get the next user who has queued work and is not currently busy.

        Implements fair-share round-robin: users are served in order of
        their first queued item, and moved to the back after being served.
        """
        async with self._lock:
            if not self._fair_queue:
                return None

            # Rotate until we find a non-busy user or exhaust the queue
            for _ in range(len(self._fair_queue)):
                user_id = self._fair_queue[0]
                state = self._states.get(user_id)
                if state and not (state.downloading or state.zipping or state.uploading or state.extracting):
                    if state.queued_items:
                        # Found a user with work who is not busy
                        self._fair_queue.rotate(-1)  # move to back for fairness
                        return user_id
                    else:
                        # No more items for this user, remove from fair queue
                        self._fair_queue.popleft()
                else:
                    # User is busy, move to back and try next
                    self._fair_queue.rotate(-1)

            return None  # all users with queued work are busy


# ──────────────────────────────────────────────────────────────────────────────
# Global singleton (replaces the bare sets/dicts in config.py)
# ──────────────────────────────────────────────────────────────────────────────

# Backward-compatible global sets for code that hasn't been migrated yet.
# These are kept in sync by the methods below.
downloading_users: Set[int] = set()
zipping_users: Set[int] = set()
uploading_users: Set[int] = set()
extracting_users: Set[int] = set()
cancel_requested: Set[int] = set()

_state_manager: Optional[UserStateManager] = None


def get_state_manager() -> UserStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = UserStateManager()
    return _state_manager


# ─── Compatibility shims for gradual migration ───────────────────────────────

async def _sync_sets_from_manager():
    """Sync the global sets from the state manager (for backward compat)."""
    global downloading_users, zipping_users, uploading_users, extracting_users, cancel_requested
    manager = get_state_manager()
    async with manager._lock:
        downloading_users = {uid for uid, s in manager._states.items() if s.downloading}
        zipping_users = {uid for uid, s in manager._states.items() if s.zipping}
        uploading_users = {uid for uid, s in manager._states.items() if s.uploading}
        extracting_users = {uid for uid, s in manager._states.items() if s.extracting}
        cancel_requested = {uid for uid, s in manager._states.items() if s.cancel_requested}


async def set_downloading(user_id: int, busy: bool = True) -> bool:
    """Set downloading flag. Returns True if successfully acquired."""
    manager = get_state_manager()
    result = await manager.set_busy(user_id, "downloading", busy)
    await _sync_sets_from_manager()
    return result


async def set_zipping(user_id: int, busy: bool = True) -> bool:
    manager = get_state_manager()
    result = await manager.set_busy(user_id, "zipping", busy)
    await _sync_sets_from_manager()
    return result


async def set_uploading(user_id: int, busy: bool = True) -> bool:
    manager = get_state_manager()
    result = await manager.set_busy(user_id, "uploading", busy)
    await _sync_sets_from_manager()
    return result


async def set_extracting(user_id: int, busy: bool = True) -> bool:
    manager = get_state_manager()
    result = await manager.set_busy(user_id, "extracting", busy)
    await _sync_sets_from_manager()
    return result


async def is_user_busy(user_id: int) -> bool:
    manager = get_state_manager()
    return await manager.is_busy(user_id)


async def get_busy_reason(user_id: int) -> str:
    manager = get_state_manager()
    return await manager.busy_reason(user_id)


async def request_cancel(user_id: int) -> bool:
    manager = get_state_manager()
    result = await manager.request_cancel(user_id)
    await _sync_sets_from_manager()
    return result


async def clear_cancel(user_id: int):
    manager = get_state_manager()
    await manager.clear_cancel(user_id)
    await _sync_sets_from_manager()


async def is_cancel_requested(user_id: int) -> bool:
    manager = get_state_manager()
    return await manager.is_cancel_requested(user_id)


async def enqueue_item(user_id: int, item):
    manager = get_state_manager()
    await manager.enqueue(user_id, item)


async def dequeue_item(user_id: int):
    manager = get_state_manager()
    return await manager.dequeue(user_id)


async def get_user_queue_size(user_id: int) -> int:
    manager = get_state_manager()
    return await manager.queue_size(user_id)


async def get_total_queue_size() -> int:
    manager = get_state_manager()
    return await manager.total_queue_size()


async def get_next_fair_user() -> Optional[int]:
    manager = get_state_manager()
    return await manager.get_next_fair_user()