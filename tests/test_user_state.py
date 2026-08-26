"""Regression tests for UserStateManager (audit Z-16)."""

import asyncio
import pytest

from user_state import (
    UserStateManager,
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
)


@pytest.fixture()
def fresh_manager():
    """Provide a fresh UserStateManager for each test."""
    # Reset the global singleton
    import user_state
    user_state._state_manager = None
    return get_state_manager()


@pytest.mark.asyncio
async def test_busy_flags_atomic(fresh_manager):
    """Busy flag operations must be atomic and reject concurrent same-op."""
    user_id = 123
    # First acquisition succeeds
    assert await set_downloading(user_id, True) is True
    # Second acquisition fails
    assert await set_downloading(user_id, True) is False
    # Release works
    assert await set_downloading(user_id, False) is True
    # Can acquire again
    assert await set_downloading(user_id, True) is True


@pytest.mark.asyncio
async def test_busy_reason(fresh_manager):
    """busy_reason reports the correct operation."""
    user_id = 123
    await set_zipping(user_id, True)
    assert await get_busy_reason(user_id) == "compressing"
    await set_zipping(user_id, False)
    await set_extracting(user_id, True)
    assert await get_busy_reason(user_id) == "extracting"
    await set_extracting(user_id, False)
    assert await get_busy_reason(user_id) == "idle"


@pytest.mark.asyncio
async def test_is_user_busy(fresh_manager):
    """is_user_busy aggregates all operations."""
    user_id = 123
    assert await is_user_busy(user_id) is False
    await set_downloading(user_id, True)
    assert await is_user_busy(user_id) is True
    await set_downloading(user_id, False)
    assert await is_user_busy(user_id) is False
    await set_zipping(user_id, True)
    assert await is_user_busy(user_id) is True


@pytest.mark.asyncio
async def test_cancellation_flag(fresh_manager):
    """request_cancel sets flag; clear_cancel clears it."""
    user_id = 123
    await set_downloading(user_id, True)
    assert await request_cancel(user_id) is True
    assert await is_cancel_requested(user_id) is True
    await clear_cancel(user_id)
    assert await is_cancel_requested(user_id) is False
    # Requesting cancel when not busy returns False
    await set_downloading(user_id, False)
    assert await request_cancel(user_id) is False


@pytest.mark.asyncio
async def test_enqueue_dequeue(fresh_manager):
    """Basic queue operations work."""
    user_id = 123
    await enqueue_item(user_id, "item1")
    await enqueue_item(user_id, "item2")
    assert await get_user_queue_size(user_id) == 2
    assert await get_total_queue_size() == 2
    item = await dequeue_item(user_id)
    assert item == "item1"
    assert await get_user_queue_size(user_id) == 1
    item = await dequeue_item(user_id)
    assert item == "item2"
    assert await get_user_queue_size(user_id) == 0
    assert await get_total_queue_size() == 0


@pytest.mark.asyncio
async def test_fair_share_round_robin(fresh_manager):
    """Fair queue serves users in round-robin order."""
    # Enqueue work for three users
    await enqueue_item(1, "a1")
    await enqueue_item(2, "b1")
    await enqueue_item(3, "c1")
    await enqueue_item(1, "a2")
    await enqueue_item(2, "b2")

    # First call returns user 1
    u = await get_next_fair_user()
    assert u == 1
    # Mark user 1 as busy, then release
    await set_downloading(1, True)
    await set_downloading(1, False)

    # Second call returns user 2
    u = await get_next_fair_user()
    assert u == 2
    await set_downloading(2, True)
    await set_downloading(2, False)

    # Third call returns user 3
    u = await get_next_fair_user()
    assert u == 3
    await set_downloading(3, True)
    await set_downloading(3, False)

    # Back to user 1 (has a2)
    u = await get_next_fair_user()
    assert u == 1
    await set_downloading(1, True)
    await set_downloading(1, False)

    # Then user 2 (has b2)
    u = await get_next_fair_user()
    assert u == 2


@pytest.mark.asyncio
async def test_fair_share_skips_busy_users(fresh_manager):
    """Fair queue skips users who are currently busy."""
    await enqueue_item(1, "a1")
    await enqueue_item(2, "b1")

    # Make user 1 busy
    await set_downloading(1, True)
    # Should get user 2
    u = await get_next_fair_user()
    assert u == 2
    await set_downloading(2, True)

    # Both busy, returns None
    u = await get_next_fair_user()
    assert u is None

    # Release user 1
    await set_downloading(1, False)
    u = await get_next_fair_user()
    assert u == 1


@pytest.mark.asyncio
async def test_fair_share_removes_empty_users(fresh_manager):
    """Users with no queued work are removed from fair queue."""
    await enqueue_item(1, "a1")
    u = await get_next_fair_user()
    assert u == 1
    # Dequeue the only item
    await dequeue_item(1)
    # Next call returns None (no queued work)
    u = await get_next_fair_user()
    assert u is None


@pytest.mark.asyncio
async def test_concurrent_busy_flag_safety(fresh_manager):
    """Concurrent attempts to set the same flag don't race."""
    user_id = 123

    async def try_acquire():
        return await set_downloading(user_id, True)

    # Fire 10 concurrent attempts
    results = await asyncio.gather(*[try_acquire() for _ in range(10)])
    # Exactly one should succeed
    assert sum(1 for r in results if r) == 1
    # The rest should fail
    assert sum(1 for r in results if not r) == 9