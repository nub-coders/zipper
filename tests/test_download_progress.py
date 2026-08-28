"""tests/test_download_progress.py — safe_download progress reporting and cancellation."""

import asyncio
import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pyrogram import StopTransmission

from safe_download import CHUNK_SIZE, safe_download


def _body_response(total_bytes: int, *, declare_length: bool = True) -> MagicMock:
    """Build a fake aiohttp response that streams `total_bytes` in CHUNK_SIZE pieces."""
    resp = MagicMock()
    resp.status = 200
    resp.headers = {"Content-Length": str(total_bytes)} if declare_length else {}
    resp.close = MagicMock()

    async def iter_chunked(size):
        remaining = total_bytes
        while remaining > 0:
            n = min(size, remaining)
            remaining -= n
            yield b"\0" * n

    resp.content = MagicMock()
    resp.content.iter_chunked = iter_chunked
    return resp


def _patch_transport(resp):
    """Stub out SSRF validation and the HTTP GET, leaving the streaming loop live."""
    return (
        patch("safe_download._validate_url_target", new=AsyncMock()),
        patch("aiohttp.ClientSession.get", new=AsyncMock(return_value=resp)),
    )


async def _download(resp, dest, **kwargs):
    validate, get = _patch_transport(resp)
    with validate, get:
        return await safe_download("http://93.184.216.34/file.bin", str(dest), **kwargs)


async def test_async_progress_callback_is_awaited(tmp_path):
    """A coroutine callback receives the transferred and total byte counts."""
    dest = tmp_path / "async.bin"
    size = 4 * 1024 * 1024
    calls = []

    async def on_progress(current, total):
        calls.append((current, total))

    result = await _download(_body_response(size), dest, progress_callback=on_progress)

    assert result.content_length == size
    assert calls, "expected at least one progress report"
    assert all(total == size for _, total in calls)


async def test_sync_progress_callback_is_supported(tmp_path):
    """A plain function callback works too; awaitable results are optional."""
    dest = tmp_path / "sync.bin"
    size = 3 * 1024 * 1024
    calls = []

    await _download(
        _body_response(size),
        dest,
        progress_callback=lambda current, total: calls.append((current, total)),
    )

    assert calls
    assert calls[-1][0] == size


async def test_progress_is_throttled(tmp_path):
    """4 MiB is 512 chunks, but byte-interval throttling keeps reports in single digits."""
    dest = tmp_path / "throttled.bin"
    size = 4 * 1024 * 1024
    chunk_count = size // CHUNK_SIZE
    calls = []

    async def on_progress(current, total):
        calls.append(current)

    await _download(_body_response(size), dest, progress_callback=on_progress)

    assert chunk_count == 512
    assert len(calls) < 16, f"expected throttled reports, got {len(calls)}"


async def test_final_progress_reports_full_size(tmp_path):
    """The last report always lands on the real total, even when throttled mid-chunk."""
    dest = tmp_path / "final.bin"
    size = 1024 * 1024 + 5000  # not a multiple of the reporting interval
    calls = []

    async def on_progress(current, total):
        calls.append((current, total))

    result = await _download(_body_response(size), dest, progress_callback=on_progress)

    assert calls[-1] == (size, size)
    assert result.content_length == size


async def test_callback_raising_stop_transmission_aborts_download(tmp_path):
    """A cancelling callback must abort the transfer and delete the partial file."""
    dest = tmp_path / "cancelled.bin"

    async def on_progress(current, total):
        raise StopTransmission

    with pytest.raises(StopTransmission):
        await _download(_body_response(8 * 1024 * 1024), dest, progress_callback=on_progress)

    assert not os.path.exists(dest)


async def test_cancelled_error_removes_partial_file(tmp_path):
    """CancelledError is a BaseException; the partial file still must not survive."""
    dest = tmp_path / "aborted.bin"

    async def on_progress(current, total):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _download(_body_response(8 * 1024 * 1024), dest, progress_callback=on_progress)

    assert not os.path.exists(dest)


async def test_download_without_callback_still_completes(tmp_path):
    """progress_callback stays optional."""
    dest = tmp_path / "plain.bin"
    size = 2 * CHUNK_SIZE

    result = await _download(_body_response(size), dest)

    assert result.content_length == size
    assert os.path.getsize(dest) == size
