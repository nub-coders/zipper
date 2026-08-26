"""tests/test_user_state.py — Concurrency and User State Synchronization Test Suite."""

import pytest
import config
from user_state import (
    clear_cancel,
    clear_user_state,
    get_busy_reason,
    get_state_manager,
    is_cancel_requested,
    is_user_busy,
    request_cancel,
    set_downloading,
    set_extracting,
    set_uploading,
    set_zipping,
)


@pytest.mark.asyncio
async def test_set_in_place_mutation_synchronization():
    """Verify that config sets (downloading_users, etc.) mutate in place without rebinding."""
    uid = 88888
    # Capture original set objects
    dl_set = config.downloading_users
    zip_set = config.zipping_users
    ext_set = config.extracting_users
    up_set = config.uploading_users
    cancel_set = config.cancel_requested

    # Transition user to downloading
    await set_downloading(uid, True)

    # Verify same object references are maintained (in-place mutation)
    assert config.downloading_users is dl_set
    assert uid in config.downloading_users

    # Transition user to zipping
    await set_downloading(uid, False)
    await set_zipping(uid, True)

    assert config.zipping_users is zip_set
    assert uid not in config.downloading_users
    assert uid in config.zipping_users

    # Clean up
    await clear_user_state(uid)
    assert uid not in config.zipping_users


@pytest.mark.asyncio
async def test_request_cancel_uninitialized_user():
    """Verify that request_cancel initializes state and sets cancel_requested=True."""
    uid = 99999
    # Ensure user has no prior state
    await clear_user_state(uid)

    # Request cancel
    await request_cancel(uid)

    assert await is_cancel_requested(uid) is True
    assert uid in config.cancel_requested

    # Clear cancel
    await clear_cancel(uid)
    assert await is_cancel_requested(uid) is False
    assert uid not in config.cancel_requested


@pytest.mark.asyncio
async def test_is_user_busy_and_reasons():
    """Verify busy state queries return correct activity reasons."""
    uid = 77777
    await clear_user_state(uid)
    assert await is_user_busy(uid) is False
    assert await get_busy_reason(uid) == "idle"

    await set_downloading(uid, True)
    assert await is_user_busy(uid) is True
    assert await get_busy_reason(uid) == "downloading"

    await set_downloading(uid, False)
    await set_extracting(uid, True)
    assert await is_user_busy(uid) is True
    assert await get_busy_reason(uid) == "extracting"

    await set_extracting(uid, False)
    await set_uploading(uid, True)
    assert await is_user_busy(uid) is True
    assert await get_busy_reason(uid) == "uploading"

    await clear_user_state(uid)
    assert await is_user_busy(uid) is False
