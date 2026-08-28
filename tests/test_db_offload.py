"""tests/test_db_offload.py — the synchronous Mongo driver must not block the event loop."""

import asyncio
import time

from unittest.mock import patch

import stats_manager
from memory_db import InMemoryCollection
from stats_manager import get_user_stats, update_stats
from tools import get_text, get_user_lang, get_user_status, set_user_lang


class SlowCollection:
    """Collection stand-in whose queries block the calling thread, like pymongo does."""

    def __init__(self, delay: float = 0.25, doc: dict | None = None):
        self.delay = delay
        self.doc = doc
        self.calls: list[str] = []

    def find_one(self, filter):
        time.sleep(self.delay)
        self.calls.append("find_one")
        return self.doc

    def update_one(self, filter, update, upsert=False):
        time.sleep(self.delay)
        self.calls.append("update_one")


async def _ticks_during(awaitable):
    """Await `awaitable` while counting how many times the loop got to run."""
    ticks = 0
    done = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await awaitable
    finally:
        done.set()
        await task
    return result, ticks


async def test_get_user_status_does_not_block_event_loop():
    """Regression: a slow query used to stall every other task in the process.

    The driver is synchronous, so the query has to run in a worker thread; the
    ticker must keep making progress while it is in flight.
    """
    coll = SlowCollection(delay=0.25, doc={"user_id": 1})

    result, ticks = await _ticks_during(get_user_status(coll, 1))

    assert result[0] is True
    assert ticks >= 5, f"event loop was starved during the query ({ticks} ticks)"


async def test_update_stats_does_not_block_event_loop():
    """update_stats runs after every download, so it must not stall the loop either."""
    coll = SlowCollection(delay=0.2, doc={"user_id": 2, "stats": {"last_reset": 2**31}})

    with patch.object(stats_manager, "collection", coll):
        _, ticks = await _ticks_during(update_stats(2, "files_sent"))

    assert ticks >= 5, f"event loop was starved during the update ({ticks} ticks)"
    assert coll.calls.count("update_one") == 2


async def test_get_user_status_creates_missing_user():
    """An unknown user is inserted on first lookup, and the limits come back."""
    coll = InMemoryCollection()

    verified, max_storage, max_file_size = await get_user_status(coll, 4242)

    assert verified is True
    assert max_storage == int(4.5 * 1024**3)
    assert max_file_size == 2 * 1024**3
    assert coll.find_one({"user_id": 4242}) is not None


async def test_language_round_trip():
    """set_user_lang persists, and get_user_lang / get_text read it back."""
    coll = InMemoryCollection()

    assert await get_user_lang(coll, 99) == "en"

    await set_user_lang(coll, 99, "fa")
    assert await get_user_lang(coll, 99) == "fa"

    text = await get_text(coll, 99, "start_msg")
    assert isinstance(text, str) and text


async def test_get_text_falls_back_for_unknown_language():
    """An unrecognised stored language falls back to English instead of raising."""
    coll = InMemoryCollection()
    await set_user_lang(coll, 100, "zz")

    text = await get_text(coll, 100, "start_msg")

    assert isinstance(text, str) and text


async def test_get_user_stats_defaults_for_new_user():
    """A user with no stored stats gets a zeroed dict, not None."""
    coll = InMemoryCollection()

    with patch.object(stats_manager, "collection", coll):
        stats = await get_user_stats(31337)

    assert stats["files_sent"] == 0
    assert "last_reset" in stats
