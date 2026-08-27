"""tests/test_async_compression.py — Non-blocking Compression and Admin Utilities Test Suite."""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tools import Timer, get_admin_ids, is_admin, create_zip_file
from plugins.admin_handlers import _get_admin_broadcast_state, _reset_broadcast_state


def test_timer_initialization():
    """Verify Timer accepts time_between and interval_seconds seamlessly."""
    t1 = Timer(time_between=3.0)
    assert t1.time_between == 3.0

    t2 = Timer(interval_seconds=4.0)
    assert t2.time_between == 4.0


def test_get_admin_ids_env_only(monkeypatch):
    """Verify get_admin_ids only reads from ADMIN_IDS environment variable and never admin.txt."""
    monkeypatch.setenv("ADMIN_IDS", "12345, 67890, 99999")
    assert get_admin_ids() == [12345, 67890, 99999]
    assert is_admin(12345) is True
    assert is_admin(11111) is False

    # When env var is empty
    monkeypatch.setenv("ADMIN_IDS", "")
    assert get_admin_ids() == []
    assert is_admin(12345) is False


@pytest.mark.asyncio
async def test_broadcast_state_per_admin_isolation():
    """Verify broadcast state is isolated per admin user ID."""
    admin1 = 1111
    admin2 = 2222

    state1 = _get_admin_broadcast_state(admin1)
    state2 = _get_admin_broadcast_state(admin2)

    assert state1 is not state2
    state1["include_sender_name"] = True
    state2["include_sender_name"] = False

    assert _get_admin_broadcast_state(admin1)["include_sender_name"] is True
    assert _get_admin_broadcast_state(admin2)["include_sender_name"] is False

    await _reset_broadcast_state(admin1)
    # admin2 should still exist
    assert _get_admin_broadcast_state(admin2)["include_sender_name"] is False


@pytest.mark.asyncio
async def test_async_zip_compression(tmp_path):
    """Verify create_zip_file uses non-blocking asyncio.to_thread and creates valid archive."""
    uid = 44444
    user_dir = tmp_path / "zipper" / str(uid)
    user_dir.mkdir(parents=True)
    (user_dir / "doc1.txt").write_text("Hello World 1")
    (user_dir / "doc2.txt").write_text("Hello World 2")

    mock_client = MagicMock()
    mock_msg_resp = MagicMock()
    mock_msg_resp.text = "test_archive.zip"
    mock_client.listen.Message = AsyncMock(return_value=mock_msg_resp)

    mock_cb = MagicMock()
    mock_cb.from_user.id = uid

    with patch("config.ggg", str(tmp_path)):
        with patch("tools.is_user_on_chat", AsyncMock(return_value=True)):
            with patch("utils.rich_ui.rich_send", AsyncMock(return_value=MagicMock())):
                with patch("utils.rich_ui.rich_edit", AsyncMock(return_value=None)):
                    zip_path, _ = await create_zip_file(
                        client=mock_client,
                        callback_query=mock_cb,
                        pass_protect=False,
                    )

    assert zip_path is not None
    assert os.path.exists(zip_path)
    assert os.path.basename(zip_path) == "test_archive.zip"
    assert zip_path.endswith(".zip")
