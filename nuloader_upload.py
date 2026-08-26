"""Upload archives that are too large for Telegram to a private NuLoader instance."""

import asyncio
import os
import re
import time
import uuid

import aiohttp
from config import clear_cancel, is_cancel_requested
from plugins.ui_components import home_buttons
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tools import Timer
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import (
    rich_button,
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
)

NULOADER_MAX_BYTES = 5 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
API_URL = os.getenv("NULOADER_API_URL", "https://files.nubcoders.com").rstrip("/")
API_KEY = os.getenv("NULOADER_API_KEY", "")
EXPIRY_MODE = os.getenv("NULOADER_EXPIRY_MODE", "days_7")
UPLOAD_TIMEOUT_SECONDS = 1800
_LOCAL_PREFIXES = ("http://127.0.0.1", "http://localhost", "http://[::1]")


class UploadCancelled(Exception):
    """Raised inside the body generator when the user presses Cancel."""


class UploadTruncated(Exception):
    """Raised when the archive no longer matches the size that was declared."""


def _fmt(size_bytes):
    """Human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def _safe_field(value):
    """Neutralise CR/LF and quotes so a filename cannot forge multipart headers."""
    return re.sub(r'[\r\n"\\]', "_", value)


def _build_envelope(filename, expiry_mode):
    """Return (preamble, epilogue, content_type) for a two-field multipart body."""
    boundary = "----ZipperBoundary" + uuid.uuid4().hex
    preamble = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="expiry_mode"\r\n\r\n'
        f"{_safe_field(expiry_mode)}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{_safe_field(filename)}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8")
    epilogue = f"\r\n--{boundary}--\r\n".encode("utf-8")
    content_type = f"multipart/form-data; boundary={boundary}"
    return preamble, epilogue, content_type


async def _stream_body(
    zip_filename, preamble, epilogue, file_size, user_id, on_progress, state
):
    """Async generator yielding chunks of the multipart payload."""
    yield preamble

    bytes_sent = 0
    actual_size = 0
    with open(zip_filename, "rb") as f:
        while True:
            if await is_cancel_requested(user_id):
                state["cancelled"] = True
                raise UploadCancelled()

            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            actual_size += len(chunk)
            bytes_sent += len(chunk)
            yield chunk

            if on_progress:
                try:
                    await on_progress(bytes_sent, file_size)
                except Exception:
                    pass

    if actual_size != file_size:
        state["truncated"] = True
        raise UploadTruncated()

    yield epilogue


async def upload_to_nuloader(callback_query, zip_filename, message):
    """Upload a >2GB archive to NuLoader and reply with the download link."""
    user_id = callback_query.from_user.id

    async def fail(reason, detail=None):
        text = (
            f"{EmojiTag.ERROR} {rich_heading('Upload Failed', level=2)}\n\n"
            f"{reason}"
        )
        if detail is not None:
            text += f"\n\n<code>{rich_esc(detail)}</code>"
        return await rich_edit(message, text, reply_markup=home_buttons)

    if not API_KEY:
        from tools import upload_to_gofile
        return await upload_to_gofile(callback_query, zip_filename, message)

    if not API_URL.startswith("https://") and not API_URL.startswith(_LOCAL_PREFIXES):
        return await fail("Storage endpoint is not HTTPS, so the upload was not attempted.")

    try:
        file_size = os.path.getsize(zip_filename)
    except OSError as exc:
        return await fail("The archive is no longer on disk.", exc)

    if file_size > NULOADER_MAX_BYTES:
        return await rich_edit(
            message,
            f"{EmojiTag.ERROR} {rich_heading('File Too Large', level=2)}\n\n"
            f"Archive is <code>{_fmt(file_size)}</code>, which exceeds the maximum cloud limit of <code>{_fmt(NULOADER_MAX_BYTES)}</code>.",
            reply_markup=home_buttons,
        )

    filename = os.path.basename(zip_filename)
    preamble, epilogue, content_type = _build_envelope(filename, EXPIRY_MODE)
    content_length = len(preamble) + file_size + len(epilogue)

    timer = Timer()
    started = time.time()
    state = {"cancelled": False, "truncated": False}
    cancel_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 Cancel Upload", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL)]]
    )

    async def report_cancelled():
        await clear_cancel(user_id)
        await rich_edit(
            message,
            f"{EmojiTag.CANCEL} {rich_heading('Upload Cancelled', level=2)}\n\nYour upload has been stopped.",
            reply_markup=home_buttons,
        )

    try:
        await rich_edit(
            message,
            f"{EmojiTag.CLOUD} {rich_heading('Uploading to Cloud', level=2)}\n\nConnecting to NuLoader high-speed storage…",
            reply_markup=cancel_markup,
        )
    except Exception:
        pass

    async def on_progress(sent, total):
        if not timer.can_send():
            return
        pct = sent * 100 / total if total else 0
        elapsed = time.time() - started
        speed = sent / elapsed if elapsed > 0 else 0
        eta = (total - sent) / speed if speed > 0 else 0
        bar_len = 16
        ticks = int(pct / (100 / bar_len))
        bar = "█" * ticks + "░" * (bar_len - ticks)

        progress_card = (
            f"{EmojiTag.CLOUD} {rich_heading('Uploading to Cloud', level=2)}\n"
            f"<b>File:</b> <code>{rich_esc(filename)}</code>\n"
            f"<b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
            + rich_kv_table([
                ("Transferred", f"<code>{_fmt(sent)} / {_fmt(total)}</code>"),
                ("Speed", f"<code>{speed / (1024 * 1024):.2f} MB/s</code>"),
                ("ETA", f"<code>{eta:.1f}s</code>"),
                ("Elapsed", f"<code>{elapsed:.1f}s</code>"),
            ])
        )
        try:
            await rich_edit(message, progress_card, reply_markup=cancel_markup)
        except Exception:
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
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    pass

                if resp.status != 201:
                    reason = payload.get("message") or f"HTTP {resp.status}"
                    return await fail("The storage server rejected the upload.", reason)

        link = payload.get("download_page_url")
        if not link:
            return await fail("Server returned no download link.")

        try:
            from stats_manager import update_stats
            await update_stats(user_id, "external_uploads")
        except Exception:
            pass

        expiry_desc = (
            "7 days (unlimited downloads)"
            if EXPIRY_MODE == "days_7"
            else "5 downloads (30 days hard cap)"
        )

        success_table = rich_kv_table([
            ("Archive Name", f"<code>{rich_esc(filename)}</code>"),
            ("File Size", f"<code>{_fmt(file_size)}</code>"),
            ("Expiry Policy", f"<code>{expiry_desc}</code>"),
            ("Hosting", "<code>NuLoader Cloud</code>"),
        ])

        await rich_edit(
            message,
            f"{EmojiTag.SUCCESS} {rich_heading('Uploaded to Cloud Storage', level=1)}\n"
            f"{success_table}\n\n"
            f"{rich_note('Telegram limits bot uploads to 2.00 GB. Your archive is hosted securely on our cloud storage with direct high-speed download access.')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬇️ Download Archive", url=link, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.DOWNLOAD)],
                [InlineKeyboardButton("💬 Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.LINK)],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="home", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.HOME)],
            ]),
        )
    except asyncio.TimeoutError:
        await fail("The connection was too slow to finish in time.")
    except Exception as exc:
        if state["cancelled"]:
            return await report_cancelled()
        if state["truncated"]:
            return await fail("The archive changed on disk while it was uploading.")
        print(f"NuLoader upload failed: {type(exc).__name__}: {exc}")
        await fail("Could not reach the storage server. Please try again.")
