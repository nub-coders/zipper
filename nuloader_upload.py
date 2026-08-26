"""Upload archives that are too large for Telegram to a private NuLoader instance.

A Telegram bot cannot send a document larger than 2 GB, so anything bigger has
to leave the platform. This posts the archive to NuLoader and replies with the
public download-page link.

Why a hand-rolled multipart body instead of ``aiohttp.FormData``: FormData built
around a file object gives no way to observe how many bytes have actually gone
out, and the bot needs that to drive the Telegram progress message. Streaming
the body from an async generator with a pre-computed Content-Length keeps
progress reporting *and* a declared length, so NuLoader's body-size middleware
can reject an oversized upload before reading a byte of it (instead of spooling
gigabytes first and only then answering 413).
"""
import asyncio
import os
import re
import time
import uuid

import aiohttp
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import clear_cancel, is_cancel_requested
from tools import Timer

# NuLoader's own MAX_UPLOAD_SIZE. Checked client-side so an oversized archive
# fails immediately with a clear message rather than after a long upload.
NULOADER_MAX_BYTES = 5 * 1024 * 1024 * 1024

# 1 MiB read granularity: small enough for a responsive progress bar, large
# enough that the per-chunk overhead is irrelevant at multi-GB sizes.
CHUNK_SIZE = 1024 * 1024

API_URL = os.getenv("NULOADER_API_URL", "https://files.nubcoders.com").rstrip("/")
API_KEY = os.getenv("NULOADER_API_KEY", "")
# days_7      -> expires after 7 days, unlimited downloads
# downloads_5 -> deleted after 5 downloads (30 day hard cap)
EXPIRY_MODE = os.getenv("NULOADER_EXPIRY_MODE", "days_7")

# Total wall-clock budget for the upload. Matches the reverse proxy's
# respondingTimeouts.readTimeout, so the bot gives up at the same moment the
# server would rather than hanging on a connection that is already dead.
UPLOAD_TIMEOUT_SECONDS = 1800

# The API key travels in a header, so a plaintext endpoint would leak it to
# anyone on the path. Loopback is exempt so a developer can point this at a
# local instance.
_LOCAL_PREFIXES = ("http://127.0.0.1", "http://localhost", "http://[::1]")


class UploadCancelled(Exception):
    """Raised inside the body generator when the user presses Cancel."""


class UploadTruncated(Exception):
    """Raised when the archive no longer matches the size that was declared."""


def _fmt(size_bytes):
    """Human-readable size, matching the formatting used elsewhere in the bot."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def _md_code(value):
    """Make a value safe to sit inside a Markdown code span.

    Pyrogram parses these messages as Markdown, so a backtick in a
    user-controlled filename closes the span early and everything after it is
    parsed as markup. Verified against ``pyrogram.parser.markdown``: a file
    named ``x`[CLICK HERE](https://evil.example)`.zip`` makes the bot emit a
    real MessageEntityTextUrl -- i.e. a clickable attacker-chosen link inside
    the bot's own trusted message. Backslashes go too, since they escape.
    """
    return str(value).replace("\\", "_").replace("`", "_")


def _safe_field(value):
    """Neutralise CR/LF and quotes so a filename cannot forge multipart headers."""
    return re.sub(r'[\r\n"\\]', "_", value)


def _build_envelope(filename, expiry_mode):
    """Return (preamble, epilogue, content_type) for a two-field multipart body.

    The file part is placed last so the whole preamble can be emitted in one
    write and the remainder of the body is pure file bytes.
    """
    boundary = "----ZipperBoundary" + uuid.uuid4().hex
    preamble = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="expiry_mode"\r\n\r\n'
        f"{_safe_field(expiry_mode)}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{_safe_field(filename)}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode()
    epilogue = f"\r\n--{boundary}--\r\n".encode()
    return preamble, epilogue, f"multipart/form-data; boundary={boundary}"


async def _stream_body(path, preamble, epilogue, total, user_id, on_progress, state):
    """Yield the multipart body, reporting progress and honouring cancellation.

    Exactly ``total`` file bytes are emitted, no matter what the file does after
    its size was measured. That matters because Content-Length is already on the
    wire: under-delivering leaves the server waiting for bytes that never arrive
    until the 30 minute timeout expires, and the user's upload lock is held for
    that entire time. A file that shrank is reported as UploadTruncated instead;
    a file that grew is simply cut at the declared length.

    The read runs in a worker thread: a multi-GB synchronous read on the event
    loop would stall every other user's task for the duration.

    ``state`` flags are set before raising because aiohttp catches whatever a
    body generator raises and re-raises it as a ClientConnectionError, so the
    flag is the only thing that survives to tell these cases apart from a
    genuine network failure.
    """
    yield preamble
    remaining = total
    with open(path, "rb") as fh:
        while remaining > 0:
            if await is_cancel_requested(user_id):
                state["cancelled"] = True
                raise UploadCancelled()
            chunk = await asyncio.to_thread(fh.read, min(CHUNK_SIZE, remaining))
            if not chunk:
                state["truncated"] = True
                raise UploadTruncated()
            yield chunk
            remaining -= len(chunk)
            await on_progress(total - remaining, total)
    yield epilogue


async def upload_to_nuloader(callback_query, zip_filename, message):
    """Upload an over-2 GB archive to NuLoader and reply with the download link.

    Same signature as the old ``upload_to_gofile`` so the call site is a
    one-line change. Falls back to gofile.io when NuLoader is not configured,
    so a deployment without NULOADER_API_KEY keeps working exactly as before.
    """
    user_id = callback_query.from_user.id
    home_buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Join @nub_coder_s", url="https://t.me/nub_coder_s")]]
    )

    async def fail(reason, detail=None):
        """Report a failure to the user.

        ``reason`` is a trusted literal from this module. ``detail`` is
        untrusted -- an exception string, or a message chosen by the storage
        server -- and is escaped and wrapped in a code span here rather than at
        each call site, so a value cannot reach the Markdown parser unescaped
        just because a caller forgot to call _md_code.
        """
        text = f"❌ **Upload failed**\n\n{reason}"
        if detail is not None:
            text += f"\n\n`{_md_code(detail)}`"
        return await message.edit_text(text, reply_markup=home_buttons)

    if not API_KEY:
        # Not configured: keep the previous behaviour rather than failing.
        from tools import upload_to_gofile

        return await upload_to_gofile(callback_query, zip_filename, message)

    if not API_URL.startswith("https://") and not API_URL.startswith(_LOCAL_PREFIXES):
        # Refuse rather than put the API key on the wire in plaintext.
        return await fail("Storage endpoint is not HTTPS, so the upload was not attempted.")

    try:
        file_size = os.path.getsize(zip_filename)
    except OSError as exc:
        return await fail("The archive is no longer on disk.", exc)

    if file_size > NULOADER_MAX_BYTES:
        return await message.edit_text(
            "❌ **Too large to host**\n\n"
            f"Archive is `{_fmt(file_size)}`, over the `{_fmt(NULOADER_MAX_BYTES)}` limit."
        )

    filename = os.path.basename(zip_filename)
    preamble, epilogue, content_type = _build_envelope(filename, EXPIRY_MODE)
    # Declared up front so the server can reject an oversized body immediately
    # and so the transfer is not chunked.
    content_length = len(preamble) + file_size + len(epilogue)

    timer = Timer()
    started = time.time()
    state = {"cancelled": False, "truncated": False}
    cancel_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task")]]
    )

    async def report_cancelled():
        await clear_cancel(user_id)
        await message.edit_text(
            "❌ **Upload cancelled**\n\nYour upload has been stopped.",
            reply_markup=home_buttons,
        )

    try:
        await message.edit_text("☁️ **Uploading to cloud…**", reply_markup=cancel_markup)
    except Exception:
        pass

    async def on_progress(sent, total):
        if not timer.can_send():
            return
        pct = sent * 100 / total if total else 0
        elapsed = time.time() - started
        speed = sent / elapsed if elapsed > 0 else 0
        eta = (total - sent) / speed if speed > 0 else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        text = (
            f"☁️ **Uploading to cloud:** {pct:.2f}%\n"
            f"Speed: {speed / (1024 * 1024):.2f} MB/s\n"
            f"Time left: {eta:.0f} seconds\n"
            f"Size: {_fmt(sent)} / {_fmt(total)}\n"
            f"[{bar}]"
        )
        try:
            await message.edit_text(text, reply_markup=cancel_markup)
        except Exception:
            # Telegram rejects an unchanged edit and flood-limits rapid ones;
            # neither is a reason to abort a multi-GB transfer.
            pass

    body = _stream_body(
        zip_filename, preamble, epilogue, file_size, user_id, on_progress, state
    )

    try:
        timeout = aiohttp.ClientTimeout(total=UPLOAD_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{API_URL}/api/v1/files",
                data=body,
                headers={
                    "X-API-Key": API_KEY,
                    "Content-Type": content_type,
                    "Content-Length": str(content_length),
                },
            ) as resp:
                payload = {}
                try:
                    parsed = await resp.json(content_type=None)
                    # A bare `null` body decodes to None, and a non-object body
                    # to a list/str; neither has .get().
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    pass

                if resp.status != 201:
                    # NuLoader's error envelope is {"error": ..., "message": ...}.
                    reason = payload.get("message") or f"HTTP {resp.status}"
                    return await fail("The storage server rejected the upload.", reason)

        link = payload.get("download_page_url")
        if not link:
            return await fail("Server returned no download link.")

        # Counted only now: incrementing before the transfer inflated
        # external_uploads with every failure and cancellation.
        try:
            from stats_manager import update_stats

            await update_stats(user_id, "external_uploads")
        except Exception:
            # Statistics are best-effort and must never mask a successful upload.
            pass

        expiry_note = (
            "Expires in 7 days."
            if EXPIRY_MODE == "days_7"
            else "Deleted after 5 downloads (30 days max)."
        )
        await message.edit_text(
            "✅ **Uploaded to cloud**\n\n"
            f"`{_md_code(filename)}` is `{_fmt(file_size)}` — over Telegram's 2 GB limit, "
            "so here is a download link instead.\n\n"
            f"_{expiry_note}_",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⬇️ Download File", url=link)],
                    [InlineKeyboardButton("Join @nub_coder_s", url="https://t.me/nub_coder_s")],
                ]
            ),
        )
    except asyncio.TimeoutError:
        await fail("The connection was too slow to finish in time.")
    except Exception as exc:
        # aiohttp re-raises anything a body generator throws as a
        # ClientConnectionError, so `except UploadCancelled` here would be dead
        # code -- the flags are what actually distinguish these cases.
        if state["cancelled"]:
            return await report_cancelled()
        if state["truncated"]:
            return await fail("The archive changed on disk while it was uploading.")
        # Logged in full server-side; the user gets no internal detail.
        print(f"NuLoader upload failed: {type(exc).__name__}: {exc}")
        await fail("Could not reach the storage server. Please try again.")
