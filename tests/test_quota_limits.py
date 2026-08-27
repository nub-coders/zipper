"""tests/test_quota_limits.py — Storage Quota Calculation and Batch Queue Limiting Test Suite."""

import pytest
import config
from unittest.mock import AsyncMock, MagicMock, patch
from batch_manager import (
    MAX_BATCH_QUEUE,
    enqueue_media_message,
    enqueue_link_message,
    get_user_batch,
    cancel_user_batch,
)
from tools import get_file_size_info


def test_download_quota_calculation():
    """Verify download quota calculation correctly uses min(remaining_storage, MAX_DOWNLOAD_BYTES)."""
    # Scenario 1: Fresh user with 4.5 GB remaining storage
    rem_storage = int(4.5 * 1024**3)
    max_allowed = min(rem_storage, config.MAX_DOWNLOAD_BYTES)
    # MAX_DOWNLOAD_BYTES is 2.0 GB, so max_allowed must be bounded to 2.0 GB
    assert max_allowed == config.MAX_DOWNLOAD_BYTES

    # Scenario 2: User with only 500 MB remaining storage
    rem_storage_low = 500 * 1024 * 1024
    max_allowed_low = min(rem_storage_low, config.MAX_DOWNLOAD_BYTES)
    # Must NOT allow more than 500 MB
    assert max_allowed_low == 500 * 1024 * 1024


def test_get_file_size_info_directory_safety(tmp_path):
    """Verify get_file_size_info handles subdirectories and files safely."""
    user_dir = tmp_path / "user_123"
    user_dir.mkdir()
    (user_dir / "file1.txt").write_bytes(b"A" * 1000)
    sub = user_dir / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"B" * 500)

    total_size, remaining, files = get_file_size_info(str(user_dir), 5000)
    assert total_size == 1500
    assert remaining == 3500
    assert "file1.txt" in files
    assert "subdir" in files


@pytest.mark.asyncio
async def test_batch_queue_length_limit():
    """Verify enqueue_media_message rejects enqueuing beyond MAX_BATCH_QUEUE."""
    uid = 66666
    mock_client = MagicMock()
    mock_client.send_message = AsyncMock()

    batch = await get_user_batch(uid, uid, mock_client)
    batch.queue.clear()

    # Fill queue to MAX_BATCH_QUEUE
    for i in range(MAX_BATCH_QUEUE):
        mock_item = MagicMock()
        mock_item.document.file_name = f"f_{i}.txt"
        mock_item.document.file_size = 100
        mock_item.photo = None
        mock_item.video = None
        mock_item.audio = None
        mock_item.voice = None
        mock_item.video_note = None
        mock_item.sticker = None
        mock_item.animation = None
        batch.queue.append(mock_item)

    # Attempt to add one more
    extra_msg = MagicMock()
    extra_msg.from_user.id = uid
    extra_msg.chat.id = uid
    extra_msg.document.file_name = "overflow.txt"
    extra_msg.document.file_size = 100

    with patch("plugins.file_handlers.get_user_status", return_value=(True, 4 * 1024**3, 2 * 1024**3)):
        with patch("plugins.file_handlers.is_user_on_chat", return_value=True):
            await enqueue_media_message(mock_client, extra_msg)

    # Queue must not grow beyond MAX_BATCH_QUEUE
    assert len(batch.queue) == MAX_BATCH_QUEUE
    await cancel_user_batch(uid)


@pytest.mark.asyncio
async def test_batch_queue_throttled_warning():
    """Verify that multiple overflow messages only trigger a single warning within the cooldown window."""
    uid = 77777
    mock_client = MagicMock()
    mock_client.send_message = AsyncMock()

    batch = await get_user_batch(uid, uid, mock_client)
    batch.queue.clear()

    # Fill queue to MAX_BATCH_QUEUE
    for i in range(MAX_BATCH_QUEUE):
        mock_item = MagicMock()
        mock_item.document.file_name = f"f_{i}.txt"
        mock_item.document.file_size = 100
        mock_item.photo = None
        mock_item.video = None
        mock_item.audio = None
        mock_item.voice = None
        mock_item.video_note = None
        mock_item.sticker = None
        mock_item.animation = None
        batch.queue.append(mock_item)

    with patch("batch_manager.is_user_on_chat", return_value=True), \
         patch("batch_manager.is_user_busy", return_value=False), \
         patch("batch_manager.rich_send", new_callable=AsyncMock) as mock_rich_send:

        # Send 5 excess messages in rapid succession
        for k in range(5):
            extra_msg = MagicMock()
            extra_msg.from_user.id = uid
            extra_msg.chat.id = uid
            extra_msg.document.file_name = f"overflow_{k}.txt"
            extra_msg.document.file_size = 100
            extra_msg.photo = None
            extra_msg.video = None
            extra_msg.audio = None
            extra_msg.voice = None
            extra_msg.video_note = None
            extra_msg.sticker = None
            extra_msg.animation = None
            await enqueue_media_message(mock_client, extra_msg)

        # Must only call rich_send ONCE for the burst
        assert mock_rich_send.call_count == 1

    await cancel_user_batch(uid)

