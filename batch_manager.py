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

MAX_BATCH_QUEUE = int(os.getenv("MAX_BATCH_QUEUE", 20))
WARNING_COOLDOWN_SECONDS = 5.0

_user_warning_times: Dict[tuple[int, str], float] = {}
_warning_lock = asyncio.Lock()


async def _send_throttled_warning(
    client: Client,
    chat_id: int,
    user_id: int,
    warning_type: str,
    text: str,
    cooldown: float = WARNING_COOLDOWN_SECONDS,
    reply_markup=None,
) -> Optional[Message]:
    """Send a warning message with cooldown throttling to prevent spamming on rapid/album uploads."""
    now = time.time()
    key = (user_id, warning_type)
    async with _warning_lock:
        last_time = _user_warning_times.get(key, 0.0)
        if now - last_time < cooldown:
            return None
        _user_warning_times[key] = now

    try:
        return await rich_send(client, chat_id, text, reply_markup=reply_markup)
    except Exception:
        return None


@dataclass
class UserDownloadBatch:
    user_id: int
    chat_id: int
    client: Client
    queue: List[Message] = field(default_factory=list)
    active_msg: Optional[Message] = None
    status_msg: Optional[Message] = None
    downloaded_count: int = 0
    failed_count: int = 0
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
    active_idx = batch.downloaded_count + batch.failed_count + 1
    total_files = batch.total_in_batch or (
        batch.downloaded_count + batch.failed_count + (1 if batch.active_msg else 0) + len(batch.queue)
    )
    remaining_in_queue = len(batch.queue)

    if batch.active_msg:
        filename = _get_filename(batch.active_msg, batch.user_id)
        if total == 0:
            total, _ = _get_media_size(batch.active_msg)
    elif batch.queue:
        filename = _get_filename(batch.queue[0], batch.user_id)
        if total == 0:
            total, _ = _get_media_size(batch.queue[0])
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
    if batch.failed_count:
        rows.append(("Failed", f"<code>{batch.failed_count} file(s)</code>"))
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


async def _relocate_status_message_to_bottom(batch: UserDownloadBatch, force: bool = False):
    """Delete the previous bot status message and send a new one at the bottom of the chat, throttled to prevent FloodWait."""
    now = time.time()
    if not force and batch.status_msg and (now - batch.last_relocate_time < 2.0):
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
        [InlineKeyboardButton("Cancel", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL)]
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
        return await _send_throttled_warning(client, chat_id, user_id, "membership", text, reply_markup=button)

    if not rate_limiter.is_allowed(user_id):
        return await _send_throttled_warning(
            client,
            chat_id,
            user_id,
            "rate_limit",
            f"{EmojiTag.CLOCK} <b>Rate limit exceeded.</b>\nPlease slow down.",
        )

    is_busy = await is_user_busy(user_id)
    if is_busy:
        from user_state import get_busy_reason
        reason = await get_busy_reason(user_id)
        if reason in ("zipping", "uploading", "extracting"):
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                f"busy_{reason}",
                f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nPlease send files after the current process finishes.",
            )

    size, enforce_limit = _get_media_size(message)
    _, max_storage, max_file_size = await get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    if enforce_limit and size > max_file_size:
        size_gb = max_file_size / (1024 ** 3)
        return await _send_throttled_warning(
            client,
            chat_id,
            user_id,
            "file_size",
            f"{EmojiTag.ERROR} <b>File exceeds limit.</b> Maximum single file size is <code>{size_gb:.1f} GB</code>.",
        )

    batch = await get_user_batch(user_id, chat_id, client)
    async with batch.lock:
        if len(batch.queue) >= MAX_BATCH_QUEUE:
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                "queue_full",
                f"{EmojiTag.ERROR} <b>Batch queue full (max {MAX_BATCH_QUEUE} files).</b>\nPlease wait for the current batch to complete.",
            )

        pending_bytes = sum(_get_media_size(m)[0] for m in batch.queue)
        if size + pending_bytes > remaining_storage:
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                "storage_quota",
                f"{EmojiTag.ERROR} <b>Not enough storage quota remaining.</b>\nRequired: <code>{_fmt_size(size + pending_bytes)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
            )

        batch.queue.append(message)
        batch.total_in_batch = (
            batch.downloaded_count + batch.failed_count + (1 if batch.active_msg else 0) + len(batch.queue)
        )

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
        return await _send_throttled_warning(client, chat_id, user_id, "membership", text, reply_markup=button)

    if not rate_limiter.is_allowed(user_id):
        return await _send_throttled_warning(
            client,
            chat_id,
            user_id,
            "rate_limit",
            f"{EmojiTag.CLOCK} <b>Rate limit exceeded.</b>\nPlease slow down.",
        )

    is_busy = await is_user_busy(user_id)
    if is_busy:
        from user_state import get_busy_reason
        reason = await get_busy_reason(user_id)
        if reason in ("zipping", "uploading", "extracting"):
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                f"busy_{reason}",
                f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nPlease send links after the current process finishes.",
            )

    _, max_storage, _ = await get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    try:
        declared_length, final_url = await safe_head(link, max_bytes=remaining_storage)
    except SSRFBlocked as e:
        return await _send_throttled_warning(client, chat_id, user_id, "ssrf", f"{EmojiTag.ERROR} <b>Blocked:</b> <code>{rich_esc(e)}</code>")
    except DownloadTooLarge as e:
        return await _send_throttled_warning(client, chat_id, user_id, "link_size", f"{EmojiTag.ERROR} <b>File too large:</b> <code>{rich_esc(e)}</code>")
    except (DownloadFailed, RedirectLimitExceeded) as e:
        return await _send_throttled_warning(client, chat_id, user_id, "link_verify", f"{EmojiTag.ERROR} <b>Link verification failed:</b> <code>{rich_esc(e)}</code>")

    content_length = declared_length if declared_length is not None else 0

    batch = await get_user_batch(user_id, chat_id, client)
    async with batch.lock:
        if len(batch.queue) >= MAX_BATCH_QUEUE:
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                "queue_full",
                f"{EmojiTag.ERROR} <b>Batch queue full (max {MAX_BATCH_QUEUE} files).</b>\nPlease wait for the current batch to complete.",
            )

        pending_bytes = sum(_get_media_size(m)[0] for m in batch.queue)
        if (content_length + pending_bytes) > remaining_storage:
            return await _send_throttled_warning(
                client,
                chat_id,
                user_id,
                "storage_quota",
                f"{EmojiTag.ERROR} <b>Not enough storage quota.</b> Required: <code>{_fmt_size(content_length + pending_bytes)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
            )

        batch.queue.append(message)
        batch.total_in_batch = (
            batch.downloaded_count + batch.failed_count + (1 if batch.active_msg else 0) + len(batch.queue)
        )

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
        batch.failed_count = 0
        batch.total_in_batch = len(batch.queue)
        batch.worker_task = asyncio.create_task(_process_batch(batch))
        batch.worker_task.add_done_callback(_log_worker_result)


def _log_worker_result(task: asyncio.Task) -> None:
    """Surface crashes from the detached batch worker instead of swallowing them."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        print(f"Batch worker crashed: {exc!r}")


async def _deliver_final_card(
    client: Client,
    chat_id: int,
    status_msg: Optional[Message],
    text: str,
    reply_markup=None,
) -> None:
    """Edit the batch status card in place, falling back to a fresh message."""
    if status_msg:
        try:
            await rich_edit(status_msg, text, reply_markup=reply_markup, client=client)
            return
        except Exception:
            pass
    try:
        await rich_send(client, chat_id, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"Failed to deliver final batch card to {chat_id}: {e}")


async def _process_batch(batch: UserDownloadBatch):
    user_id = batch.user_id
    chat_id = batch.chat_id
    client = batch.client

    user_dir = f"{config.ggg}/zipper/{user_id}"
    status_timer = Timer(time_between=3.0)
    cancelled = False
    max_storage = 0
    fatal_error: Optional[str] = None

    # Once the busy flag is set, every path below has to reach the `finally` that
    # clears it. Setup work (a blocking Mongo read, makedirs, the first status
    # edit) used to run outside the try, so a failure there left the user
    # permanently marked as downloading with no way to recover.
    await set_downloading(user_id, True)
    config.user_ids[user_id] = True

    try:
        _, max_storage, _ = await get_user_status(collection, user_id)
        os.makedirs(user_dir, exist_ok=True)

        # Immediately show the initial status card so the user gets instant feedback
        if not batch.status_msg:
            await _relocate_status_message_to_bottom(batch, force=True)

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

                if status_timer.can_send():
                    card = _build_progress_card(
                        batch,
                        current=current,
                        total=total,
                        speed=speed / (1024 * 1024),
                        eta=eta,
                        elapsed=elapsed,
                    )
                    cancel_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Cancel", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL)]
                    ])
                    if batch.status_msg:
                        try:
                            await rich_edit(batch.status_msg, card, reply_markup=cancel_markup, client=client)
                        except Exception:
                            pass
                    else:
                        try:
                            new_status = await rich_send(client, chat_id, card, reply_markup=cancel_markup)
                            batch.status_msg = new_status
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
                        # Passed directly, not wrapped in create_task: the callback
                        # must be awaited by the download loop so the
                        # StopTransmission it raises on cancel actually aborts it.
                        progress_callback=progress_bar,
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
                # A failed item must not be counted as downloaded, otherwise the
                # completion card reports it as a success.
                print(f"Error downloading batch item: {e}")
                batch.failed_count += 1

    except (StopTransmission, asyncio.CancelledError):
        cancelled = True
    except Exception as e:
        fatal_error = str(e)
        print(f"Batch aborted for user {user_id}: {e!r}")
    finally:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        await clear_cancel(user_id)

        async with batch.lock:
            batch.is_running = False
            batch.active_msg = None
            batch.queue.clear()
            final_count = batch.downloaded_count
            final_failed = batch.failed_count
            status_msg = batch.status_msg
            batch.status_msg = None
            batch.downloaded_count = 0
            batch.failed_count = 0
            batch.total_in_batch = 0

        if cancelled:
            final_card = (
                f"{rich_heading(f'{EmojiTag.CANCEL} Download Cancelled', level=2)}\n\n"
                f"Batch download was cancelled by user."
            )
            final_markup = home_buttons
        elif final_count or final_failed:
            total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)
            used_gb = total_size / (1024 ** 3)
            free_gb = remaining_storage / (1024 ** 3)

            rows = [("Downloaded in Batch", f"<code>{final_count} file(s)</code>")]
            if final_failed:
                rows.append(("Failed", f"<code>{final_failed} file(s)</code>"))
            rows += [
                ("Total Files in Storage", f"<code>{len(files)}</code>"),
                ("Used Storage", f"<code>{used_gb:.2f} GB</code>"),
                ("Available Storage", f"<code>{free_gb:.2f} GB</code>"),
            ]
            summary_table = rich_kv_table(rows, headers=["Batch Result", "Details"])

            if final_failed and not final_count:
                heading = rich_heading(f"{EmojiTag.ERROR} Batch Download Failed", level=1)
                footer = (
                    f"<i>None of the <code>{final_failed}</code> file(s) could be downloaded.<br>"
                    f"Please check the files or links and try again.</i>"
                )
            elif final_failed:
                heading = rich_heading(f"{EmojiTag.WARNING} Batch Finished With Errors", level=1)
                footer = (
                    f"<i><code>{final_count}</code> file(s) stored, "
                    f"<code>{final_failed}</code> failed.<br>"
                    f"Use <b>Compress Files</b> to pack the stored files into a ZIP archive.</i>"
                )
            else:
                heading = rich_heading(f"{EmojiTag.SUCCESS} Batch Download Complete", level=1)
                footer = (
                    f"<i>All <code>{final_count}</code> file(s) downloaded and stored successfully.<br>"
                    f"Use <b>Compress Files</b> to pack them into a ZIP archive.</i>"
                )

            final_card = f"{heading}\n{summary_table}\n\n{footer}"
            final_markup = file_buttons if final_count else home_buttons
        elif fatal_error:
            final_card = (
                f"{rich_heading(f'{EmojiTag.ERROR} Batch Download Failed', level=2)}\n\n"
                f"The batch could not be started: <code>{rich_esc(fatal_error)}</code>"
            )
            final_markup = home_buttons
        else:
            final_card = None
            final_markup = None

        if final_card:
            await _deliver_final_card(client, chat_id, status_msg, final_card, final_markup)


async def cancel_user_batch(user_id: int) -> int:
    """Abort an active user batch and clear its queue.

    Returns the number of queued items that were dropped.
    """
    async with _batches_lock:
        batch = _batches.get(user_id)
    if not batch:
        return 0

    async with batch.lock:
        if batch.debounce_task and not batch.debounce_task.done():
            batch.debounce_task.cancel()
        removed = len(batch.queue)
        batch.queue.clear()
        return removed


def pending_queue_counts() -> tuple[int, Dict[int, int]]:
    """Return (total queued files, {user_id: queued files}) across all batches.

    Only list lengths are read and there is no await point, so the snapshot is
    consistent within a single event-loop step and needs no lock. This keeps the
    function callable from the synchronous status/diagnostic helpers.
    """
    per_user = {uid: len(batch.queue) for uid, batch in _batches.items() if batch.queue}
    return sum(per_user.values()), per_user
