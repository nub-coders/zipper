"""batch_manager.py — Multi-File Debounced Batch Downloader with Dynamic Status Relocation.

Features:
  1. Debounced multi-file queuing (1.0s delay): Collects rapid/album file uploads into a single batch
     without sending spammy individual replies.
  2. Sequential FIFO downloading starting from the very first file.
  3. Single persistent status card sent after the latest message (no reply parameter).
  4. Real-time batch progress tracking (completed / remaining / total + active transfer metrics).
  5. Mid-download dynamic additions: When user sends another file while download is active,
     the old bot status message is deleted and a new status card is posted at the very bottom
     with updated total counts, ensuring the bot message is always the latest message.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config
from config import collection
from plugins.ui_components import file_buttons, home_buttons
from pyrogram import Client, StopTransmission
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from rate_limiter import rate_limiter
from safe_download import (
    DownloadFailed,
    DownloadTooLarge,
    RedirectLimitExceeded,
    SSRFBlocked,
    safe_download,
    safe_head,
)
from safe_paths import UnsafePathError, resolve_in_user_dir
from stats_manager import update_stats
from tools import (
    Timer,
    get_file_size_info,
    get_user_status,
    is_compressed,
    is_user_on_chat,
)
from user_state import (
    clear_cancel,
    is_cancel_requested,
    is_user_busy,
    set_downloading,
)
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import (
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_reply,
    rich_send,
)


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def _get_media_size(message: Message) -> tuple[int, bool]:
    checks = [
        ("document", lambda m: m.document.file_size if m.document else None, True),
        ("photo", lambda m: getattr(m.photo, "file_size", 100), False),
        ("video", lambda m: m.video.file_size if m.video else None, True),
        ("audio", lambda m: m.audio.file_size if m.audio else None, True),
        ("voice", lambda m: m.voice.file_size if m.voice else None, False),
        ("video_note", lambda m: m.video_note.file_size if m.video_note else None, False),
        ("sticker", lambda m: m.sticker.file_size if m.sticker else None, False),
        ("animation", lambda m: m.animation.file_size if m.animation else None, True),
    ]
    for attr, getter, enforce_limit in checks:
        if getattr(message, attr, None):
            size = getter(message)
            if size is not None:
                return size, enforce_limit
    return 0, False


def _get_filename(message: Message, user_id: int) -> str:
    ts = int(time.time())
    if message.document and message.document.file_name:
        return message.document.file_name
    if message.photo:
        return f"photo_{user_id}_{ts}.jpg"
    if message.video:
        return message.video.file_name or f"video_{user_id}_{ts}.mp4"
    if message.audio:
        return message.audio.file_name or f"audio_{user_id}_{ts}.mp3"
    if message.voice:
        return f"voice_{user_id}_{ts}.ogg"
    if message.video_note:
        return f"video_note_{user_id}_{ts}.mp4"
    if message.sticker:
        return f"sticker_{user_id}_{ts}.webp"
    if message.animation:
        return f"animation_{user_id}_{ts}.gif"
    if message.text and message.text.startswith("http"):
        raw = message.text.split("?")[0].split("#")[0].split("/")[-1]
        return raw or f"download_{user_id}_{ts}"
    return f"file_{user_id}_{ts}"

MAX_BATCH_QUEUE = 20


@dataclass
class UserDownloadBatch:
    user_id: int
    chat_id: int
    client: Client
    queue: List[Message] = field(default_factory=list)
    active_msg: Optional[Message] = None
    status_msg: Optional[Message] = None
    downloaded_count: int = 0
    total_in_batch: int = 0
    debounce_task: Optional[asyncio.Task] = None
    worker_task: Optional[asyncio.Task] = None
    is_running: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_progress_info: dict = field(default_factory=dict)
    last_relocate_time: float = 0.0


_batches: Dict[int, UserDownloadBatch] = {}
_batches_lock = asyncio.Lock()


async def get_user_batch(user_id: int, chat_id: int, client: Client) -> UserDownloadBatch:
    async with _batches_lock:
        if user_id not in _batches:
            _batches[user_id] = UserDownloadBatch(
                user_id=user_id,
                chat_id=chat_id,
                client=client,
            )
        else:
            _batches[user_id].chat_id = chat_id
            _batches[user_id].client = client
        return _batches[user_id]


def _build_progress_card(
    batch: UserDownloadBatch,
    current: int = 0,
    total: int = 0,
    speed: float = 0,
    eta: float = 0,
    elapsed: float = 0,
) -> str:
    active_idx = batch.downloaded_count + 1
    total_files = batch.total_in_batch or (batch.downloaded_count + (1 if batch.active_msg else 0) + len(batch.queue))
    remaining_in_queue = len(batch.queue)

    if batch.active_msg:
        filename = _get_filename(batch.active_msg, batch.user_id)
    elif batch.queue:
        filename = _get_filename(batch.queue[0], batch.user_id)
    else:
        filename = "Processing…"

    bar_len = 14
    pct = (current / total * 100) if total > 0 else 0
    ticks = int(pct / (100 / bar_len)) if bar_len > 0 else 0
    bar = "█" * ticks + "░" * (bar_len - ticks)

    rows = [
        ("Current File", f"<code>{rich_esc(filename[:20] + '...' if len(filename) > 23 else filename)}</code>"),
        ("File Transfer", f"<code>{_fmt_size(current)} / {_fmt_size(total)}</code>"),
        ("Files Downloaded", f"<code>{batch.downloaded_count} / {total_files}</code>"),
        ("Remaining in Queue", f"<code>{remaining_in_queue} file(s)</code>"),
    ]
    if speed > 0:
        rows.append(("Transfer Speed", f"<code>{speed:.2f} MB/s</code>"))
    if eta > 0:
        rows.append(("Estimated ETA", f"<code>{eta:.1f}s</code>"))

    card = (
        f"{rich_heading(f'{EmojiTag.DOWNLOAD} Downloading Files ({active_idx}/{total_files})', level=2)}\n"
        f"<b>Batch Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
        + rich_kv_table(rows, headers=["Transfer Metric", "Status"])
    )
    return card


async def _relocate_status_message_to_bottom(batch: UserDownloadBatch):
    """Delete the previous bot status message and send a new one at the bottom of the chat, throttled to prevent FloodWait."""
    now = time.time()
    if now - batch.last_relocate_time < 2.0:
        return
    batch.last_relocate_time = now

    old_msg = batch.status_msg
    batch.status_msg = None

    if old_msg:
        try:
            await old_msg.delete()
        except Exception:
            pass

    info = batch.last_progress_info or {}
    card = _build_progress_card(
        batch,
        current=info.get("current", 0),
        total=info.get("total", 0),
        speed=info.get("speed", 0),
        eta=info.get("eta", 0),
        elapsed=info.get("elapsed", 0),
    )
    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL)]
    ])
    try:
        new_msg = await rich_send(batch.client, batch.chat_id, card, reply_markup=cancel_markup)
        batch.status_msg = new_msg
    except Exception:
        pass


async def enqueue_media_message(client: Client, message: Message):
    """Enqueue an incoming media message with 1.0s debounce and dynamic status relocation."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
        ])
        text = f"{EmojiTag.LOCK} <b>Membership Required</b>\n\nYou must join @nub_coders and @nub_coder_s to use this bot."
        return await rich_send(client, chat_id, text, reply_markup=button)

    if not rate_limiter.is_allowed(user_id):
        return await rich_send(
            client,
            chat_id,
            f"{EmojiTag.CLOCK} <b>Rate limit exceeded.</b>\nPlease slow down.",
        )

    is_busy = await is_user_busy(user_id)
    if is_busy:
        from user_state import get_busy_reason
        reason = await get_busy_reason(user_id)
        if reason in ("zipping", "uploading", "extracting"):
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nPlease send files after the current process finishes.",
            )

    size, enforce_limit = _get_media_size(message)
    _, max_storage, max_file_size = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    if enforce_limit and size > max_file_size:
        size_gb = max_file_size / (1024 ** 3)
        return await rich_send(
            client,
            chat_id,
            f"{EmojiTag.ERROR} <b>File exceeds limit.</b> Maximum single file size is <code>{size_gb:.1f} GB</code>.",
        )

    batch = await get_user_batch(user_id, chat_id, client)
    async with batch.lock:
        if len(batch.queue) >= MAX_BATCH_QUEUE:
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.ERROR} <b>Batch queue full (max {MAX_BATCH_QUEUE} files).</b>\nPlease wait for the current batch to complete.",
            )

        pending_bytes = sum(_get_media_size(m)[0] for m in batch.queue)
        if size + pending_bytes > remaining_storage:
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.ERROR} <b>Not enough storage quota remaining.</b>\nRequired: <code>{_fmt_size(size + pending_bytes)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
            )

        batch.queue.append(message)
        batch.total_in_batch = batch.downloaded_count + (1 if batch.active_msg else 0) + len(batch.queue)

        if batch.is_running:
            await _relocate_status_message_to_bottom(batch)
        else:
            if batch.debounce_task and not batch.debounce_task.done():
                batch.debounce_task.cancel()
            batch.debounce_task = asyncio.create_task(_debounce_worker_trigger(batch, 1.0))


async def enqueue_link_message(client: Client, message: Message):
    """Enqueue an incoming direct download link with 1.0s debounce and dynamic status relocation."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    link = message.text.strip()

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
        ])
        text = f"{EmojiTag.LOCK} <b>Membership Required</b>\n\nYou must join @nub_coders and @nub_coder_s to use this bot."
        return await rich_send(client, chat_id, text, reply_markup=button)

    if not rate_limiter.is_allowed(user_id):
        return await rich_send(
            client,
            chat_id,
            f"{EmojiTag.CLOCK} <b>Rate limit exceeded.</b>\nPlease slow down.",
        )

    is_busy = await is_user_busy(user_id)
    if is_busy:
        from user_state import get_busy_reason
        reason = await get_busy_reason(user_id)
        if reason in ("zipping", "uploading", "extracting"):
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nPlease send links after the current process finishes.",
            )

    _, max_storage, _ = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    try:
        declared_length, final_url = safe_head(link, max_bytes=remaining_storage)
    except SSRFBlocked as e:
        return await rich_send(client, chat_id, f"{EmojiTag.ERROR} <b>Blocked:</b> <code>{rich_esc(e)}</code>")
    except DownloadTooLarge as e:
        return await rich_send(client, chat_id, f"{EmojiTag.ERROR} <b>File too large:</b> <code>{rich_esc(e)}</code>")
    except (DownloadFailed, RedirectLimitExceeded) as e:
        return await rich_send(client, chat_id, f"{EmojiTag.ERROR} <b>Link verification failed:</b> <code>{rich_esc(e)}</code>")

    content_length = declared_length if declared_length is not None else 0

    batch = await get_user_batch(user_id, chat_id, client)
    async with batch.lock:
        if len(batch.queue) >= MAX_BATCH_QUEUE:
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.ERROR} <b>Batch queue full (max {MAX_BATCH_QUEUE} files).</b>\nPlease wait for the current batch to complete.",
            )

        pending_bytes = sum(_get_media_size(m)[0] for m in batch.queue)
        if (content_length + pending_bytes) > remaining_storage:
            return await rich_send(
                client,
                chat_id,
                f"{EmojiTag.ERROR} <b>Not enough storage quota.</b> Required: <code>{_fmt_size(content_length + pending_bytes)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
            )

        batch.queue.append(message)
        batch.total_in_batch = batch.downloaded_count + (1 if batch.active_msg else 0) + len(batch.queue)

        if batch.is_running:
            await _relocate_status_message_to_bottom(batch)
        else:
            if batch.debounce_task and not batch.debounce_task.done():
                batch.debounce_task.cancel()
            batch.debounce_task = asyncio.create_task(_debounce_worker_trigger(batch, 1.0))


async def _debounce_worker_trigger(batch: UserDownloadBatch, delay: float = 1.0):
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    async with batch.lock:
        if batch.is_running or not batch.queue:
            return
        batch.is_running = True
        batch.downloaded_count = 0
        batch.total_in_batch = len(batch.queue)
        batch.worker_task = asyncio.create_task(_process_batch(batch))


async def _process_batch(batch: UserDownloadBatch):
    user_id = batch.user_id
    chat_id = batch.chat_id
    client = batch.client

    await set_downloading(user_id, True)
    config.user_ids[user_id] = True

    _, max_storage, _ = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    status_timer = Timer(time_between=3.0)
    cancelled = False

    try:
        while True:
            if await is_cancel_requested(user_id):
                cancelled = True
                break

            async with batch.lock:
                if not batch.queue:
                    batch.active_msg = None
                    break
                batch.active_msg = batch.queue.pop(0)

            msg = batch.active_msg
            file_start_time = time.time()

            async def progress_bar(current, total):
                if await is_cancel_requested(user_id):
                    raise StopTransmission

                elapsed = time.time() - file_start_time
                speed = current / elapsed if elapsed > 0 else 0
                eta = (total - current) / speed if speed > 0 else 0

                batch.last_progress_info = {
                    "current": current,
                    "total": total,
                    "speed": speed / (1024 * 1024),
                    "eta": eta,
                    "elapsed": elapsed,
                }

                if status_timer.can_send() and batch.status_msg:
                    card = _build_progress_card(
                        batch,
                        current=current,
                        total=total,
                        speed=speed / (1024 * 1024),
                        eta=eta,
                        elapsed=elapsed,
                    )
                    cancel_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL)]
                    ])
                    try:
                        await rich_edit(batch.status_msg, card, reply_markup=cancel_markup, client=client)
                    except Exception:
                        pass

            try:
                # Direct URL link
                if msg.text and msg.text.startswith("http"):
                    link = msg.text.strip()
                    _, rem_storage, _ = get_file_size_info(user_dir, max_storage)
                    if rem_storage <= 0:
                        raise DownloadTooLarge("No remaining storage quota")
                    raw_filename = link.split("?")[0].split("#")[0].split("/")[-1] or "download"
                    dest_path = resolve_in_user_dir(user_dir, raw_filename, fallback="download")
                    max_allowed = min(rem_storage, config.MAX_DOWNLOAD_BYTES)
                    await safe_download(
                        link,
                        dest_path,
                        max_bytes=max_allowed,
                        progress_callback=lambda c, t: asyncio.create_task(progress_bar(c, t)),
                    )
                # Media Telegram File
                else:
                    raw_name = _get_filename(msg, user_id)
                    dest_path = resolve_in_user_dir(user_dir, raw_name)
                    await asyncio.wait_for(
                        msg.download(file_name=dest_path, progress=progress_bar),
                        timeout=1500,
                    )

                batch.downloaded_count += 1
                await update_stats(user_id, "files_sent")
            except (StopTransmission, asyncio.CancelledError):
                cancelled = True
                break
            except Exception as e:
                print(f"Error downloading batch item: {e}")
                batch.downloaded_count += 1

    except (StopTransmission, asyncio.CancelledError):
        cancelled = True
    finally:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        await clear_cancel(user_id)

        async with batch.lock:
            batch.is_running = False
            batch.active_msg = None
            batch.queue.clear()
            final_count = batch.downloaded_count
            status_msg = batch.status_msg
            batch.status_msg = None
            batch.downloaded_count = 0
            batch.total_in_batch = 0

        if cancelled:
            if status_msg:
                try:
                    await rich_edit(
                        status_msg,
                        f"{rich_heading(f'{EmojiTag.CANCEL} Download Cancelled', level=2)}\n\n"
                        f"Batch download was cancelled by user.",
                        reply_markup=home_buttons,
                        client=client,
                    )
                except Exception:
                    pass
        elif final_count > 0:
            total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)
            used_gb = total_size / (1024 ** 3)
            free_gb = remaining_storage / (1024 ** 3)

            summary_table = rich_kv_table([
                ("Downloaded in Batch", f"<code>{final_count} file(s)</code>"),
                ("Total Files in Storage", f"<code>{len(files)}</code>"),
                ("Used Storage", f"<code>{used_gb:.2f} GB</code>"),
                ("Available Storage", f"<code>{free_gb:.2f} GB</code>"),
            ], headers=["Batch Result", "Details"])

            completion_text = (
                f"{rich_heading(f'{EmojiTag.SUCCESS} Batch Download Complete', level=1)}\n"
                f"{summary_table}\n\n"
                f"<i>All <code>{final_count}</code> file(s) downloaded and stored successfully.<br>"
                f"Use <b>Compress Files</b> to pack them into a ZIP archive.</i>"
            )
            if status_msg:
                try:
                    await rich_edit(
                        status_msg,
                        completion_text,
                        reply_markup=file_buttons,
                        client=client,
                    )
                except Exception:
                    await rich_send(client, chat_id, completion_text, reply_markup=file_buttons)


async def cancel_user_batch(user_id: int):
    """Abort an active user batch and clear its queue."""
    async with _batches_lock:
        batch = _batches.get(user_id)
    if not batch:
        return

    async with batch.lock:
        if batch.debounce_task and not batch.debounce_task.done():
            batch.debounce_task.cancel()
        batch.queue.clear()
