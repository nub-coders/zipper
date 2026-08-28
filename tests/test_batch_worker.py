"""tests/test_batch_worker.py — Batch worker state cleanup and result accounting."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import config
from batch_manager import (
    _process_batch,
    cancel_user_batch,
    get_user_batch,
    pending_queue_counts,
)
from user_state import clear_cancel, clear_user_state, is_user_busy


def _media_message(name: str, size: int = 1024, fail: bool = False) -> MagicMock:
    """Build a Telegram media message stub that downloads (or fails to)."""
    msg = MagicMock()
    msg.text = None
    msg.document.file_name = name
    msg.document.file_size = size
    msg.photo = None
    msg.video = None
    msg.audio = None
    msg.voice = None
    msg.video_note = None
    msg.sticker = None
    msg.animation = None

    if fail:
        msg.download = AsyncMock(side_effect=OSError("simulated transfer failure"))
    else:
        async def _write(file_name=None, progress=None):
            with open(file_name, "wb") as f:
                f.write(b"x" * size)
        msg.download = AsyncMock(side_effect=_write)
    return msg


async def _run_batch(uid, tmp_path, queue, max_storage=10 * 1024 * 1024):
    """Run _process_batch against a stubbed environment and return the final card text."""
    await clear_user_state(uid)
    await clear_cancel(uid)

    batch = await get_user_batch(uid, uid, MagicMock())
    batch.queue.clear()
    batch.queue.extend(queue)
    batch.downloaded_count = 0
    batch.failed_count = 0
    batch.total_in_batch = len(queue)
    batch.status_msg = None

    delivered = {}

    async def _capture(client, chat_id, status_msg, text, reply_markup=None):
        delivered["text"] = text

    with patch.object(config, "ggg", str(tmp_path)), \
         patch("batch_manager.get_user_status", new=AsyncMock(return_value=(0, max_storage, 0))), \
         patch("batch_manager.update_stats", new=AsyncMock()), \
         patch("batch_manager._relocate_status_message_to_bottom", new=AsyncMock()), \
         patch("batch_manager._deliver_final_card", new=_capture):
        await _process_batch(batch)

    return delivered.get("text", ""), batch


@pytest.mark.asyncio
async def test_setup_failure_releases_busy_flag(tmp_path):
    """A crash before the download loop must not leave the user stuck as busy.

    get_user_status runs against a blocking Mongo client in production; when it
    raised, the busy flag set just above it was never cleared and the user could
    never start another batch.
    """
    uid = 71001
    await clear_user_state(uid)

    batch = await get_user_batch(uid, uid, MagicMock())
    batch.queue.clear()
    batch.queue.append(_media_message("a.txt"))

    delivered = {}

    async def _capture(client, chat_id, status_msg, text, reply_markup=None):
        delivered["text"] = text

    with patch.object(config, "ggg", str(tmp_path)), \
         patch("batch_manager.get_user_status", new=AsyncMock(side_effect=RuntimeError("mongo down"))), \
         patch("batch_manager._relocate_status_message_to_bottom", new=AsyncMock()), \
         patch("batch_manager._deliver_final_card", new=_capture):
        await _process_batch(batch)

    assert await is_user_busy(uid) is False
    assert uid not in config.user_ids
    assert uid not in config.downloading_users
    assert batch.is_running is False
    assert "could not be started" in delivered["text"]


@pytest.mark.asyncio
async def test_failed_download_is_not_reported_as_success(tmp_path):
    """A transfer error must be counted as a failure, not as a downloaded file."""
    uid = 71002
    text, batch = await _run_batch(uid, tmp_path, [_media_message("broken.bin", fail=True)])

    assert "Batch Download Failed" in text
    assert "Complete" not in text
    assert batch.downloaded_count == 0
    assert batch.failed_count == 0  # counters reset after the run
    assert await is_user_busy(uid) is False


@pytest.mark.asyncio
async def test_partial_failure_reports_both_counts(tmp_path):
    """A mixed batch reports how many files stored and how many failed."""
    uid = 71003
    queue = [_media_message("ok.bin"), _media_message("bad.bin", fail=True)]
    text, _ = await _run_batch(uid, tmp_path, queue)

    assert "Finished With Errors" in text
    assert "<code>1</code> file(s) stored" in text
    assert "<code>1</code> failed" in text


@pytest.mark.asyncio
async def test_all_success_reports_completion(tmp_path):
    """The success path is unchanged when every file downloads."""
    uid = 71004
    queue = [_media_message("one.bin"), _media_message("two.bin")]
    text, _ = await _run_batch(uid, tmp_path, queue)

    assert "Batch Download Complete" in text
    assert "All <code>2</code> file(s)" in text
    assert "Failed" not in text


@pytest.mark.asyncio
async def test_pending_queue_counts_reports_waiting_files():
    """The status/diagnostic helpers read queue depth straight from the batches."""
    uid = 71005
    batch = await get_user_batch(uid, uid, MagicMock())
    batch.queue.clear()

    total, per_user = pending_queue_counts()
    assert uid not in per_user

    batch.queue.extend([_media_message("q1.bin"), _media_message("q2.bin")])
    total, per_user = pending_queue_counts()
    assert per_user[uid] == 2
    assert total >= 2

    removed = await cancel_user_batch(uid)
    assert removed == 2
    assert pending_queue_counts()[1].get(uid) is None


@pytest.mark.asyncio
async def test_cancel_user_batch_without_batch_returns_zero():
    """Cancelling a user that never queued anything is a no-op."""
    assert await cancel_user_batch(999999321) == 0
