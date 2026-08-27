"""plugins/file_handlers.py — File Management, Downloads, and Directory Actions with Bot API 10.2 & 10.3 Rich UI."""

import asyncio
import os
import random
import shutil
import time

import config
from config import collection
from plugins.ui_components import (
    back_buttons,
    cancel_markup,
    common_buttons,
    file_buttons,
    home_buttons,
    nofile_buttons,
    pass_button,
)
from pyrogram import Client, StopTransmission, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)
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
from batch_manager import enqueue_link_message, enqueue_media_message
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
    get_busy_reason,
    is_cancel_requested,
    is_user_busy,
    request_cancel,
    set_downloading,
    set_extracting,
    set_uploading,
    set_zipping,
)
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import (
    rich_details,
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_reply,
    rich_send,
    rich_table,
)


# ─── Size Formatter ───────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    """Return a human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def _detect_file_badge(filename: str) -> str:
    """Return an icon badge for the file type."""
    lower = filename.lower()
    if lower.endswith((".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".tbz2", ".txz", ".zst", ".iso", ".cab", ".arj", ".lzh", ".apk", ".jar", ".deb", ".rpm", ".cbz", ".cbr")):
        return f"{EmojiTag.ZIP} ZIP"
    elif lower.endswith((".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".vob", ".wmv")):
        return f"{EmojiTag.VIDEO} Video"
    elif lower.endswith((".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus", ".wma")):
        return f"{EmojiTag.AUDIO} Audio"
    elif lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".ico", ".tiff")):
        return f"{EmojiTag.IMAGE} Image"
    elif lower.endswith((".py", ".js", ".html", ".css", ".json", ".sh", ".c", ".cpp", ".rs", ".go", ".java", ".ts", ".php", ".rb")):
        return f"{EmojiTag.CODE} Code"
    elif lower.endswith((".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".epub")):
        return f"{EmojiTag.DOCUMENT} Doc"
    return f"{EmojiTag.FILE} File"


async def _sleep_after_download(size_bytes: int, queued: bool = False):
    """Pause after a successful queued download based on file size."""
    if not queued:
        return

    delay = (size_bytes / (1024 * 1024)) / 10
    if delay > 0:
        await asyncio.sleep(delay)


# ─── Commands ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("my_files"))
async def list_files_command(client: Client, message: Message):
    await list_files(client, message)


@Client.on_callback_query(filters.regex(r"^my_files$"))
async def list_files_callback(client: Client, callback_query: CallbackQuery):
    await list_files(client, callback_query)


@Client.on_message(filters.private & filters.command("del"))
async def delete_file(client: Client, message: Message):
    user_id = message.from_user.id
    user_dir = f"{config.ggg}/zipper/{user_id}"

    try:
        file_number = int(message.text.split("/del ")[1]) - 1
    except (IndexError, ValueError):
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Invalid file number.</b>\n\nUsage: <code>/del &lt;number&gt;</code> (check numbers via <code>/my_files</code>)",
            reply_markup=file_buttons,
            client=client,
        )

    if not os.path.exists(user_dir):
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me any file to get started.",
            reply_markup=nofile_buttons,
            client=client,
        )

    files = sorted(os.listdir(user_dir))
    if 0 <= file_number < len(files):
        target = os.path.join(user_dir, files[file_number])
        deleted_name = files[file_number]
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                os.remove(target)
            return await rich_reply(
                message,
                f"{EmojiTag.SUCCESS} <b>File deleted successfully!</b>\n\n🗑️ Removed: <code>{rich_esc(deleted_name)}</code>",
                reply_markup=file_buttons,
                client=client,
            )
        except OSError as e:
            return await rich_reply(
                message,
                f"{EmojiTag.ERROR} <b>Failed to delete:</b> <code>{rich_esc(e)}</code>",
                reply_markup=file_buttons,
                client=client,
            )

    return await rich_reply(
        message,
        f"{EmojiTag.ERROR} <b>Invalid file number.</b> Use <code>/my_files</code> to view valid indices.",
        reply_markup=file_buttons,
        client=client,
    )


@Client.on_message(filters.private & filters.command("clear"))
async def clear_files(client: Client, message: Message):
    from tools import handle_clear_files
    user_id = message.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
    formatted = f"{EmojiTag.TRASH} <b>{message_text}</b>"
    await rich_reply(message, formatted, reply_markup=back_buttons, client=client)


@Client.on_callback_query(filters.regex(r"^clear$"))
async def clear_files_callback(client: Client, callback_query: CallbackQuery):
    from tools import handle_clear_files
    user_id = callback_query.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
    formatted = f"{EmojiTag.TRASH} <b>{message_text}</b>"
    await rich_edit(callback_query, formatted, reply_markup=back_buttons, client=client)


@Client.on_message(filters.private & filters.command("fzip"))
async def zip_files_command(client: Client, message: Message):
    user_id = message.from_user.id
    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can zip your files once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))] if os.path.exists(user_dir) else []

    if not files:
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>You don't have files to zip yet.</b>\n\nSend me any files or direct links first, then use <code>/fzip</code>.",
            reply_markup=back_buttons,
            client=client,
        )

    total_bytes = sum(os.path.getsize(os.path.join(user_dir, f)) for f in files)

    html_content = (
        f"{rich_heading(f'{EmojiTag.LOCK} ZIP Archive Creation', level=1)}\n"
        f"<b>Files to bundle:</b> <code>{len(files)}</code>\n"
        f"<b>Total uncompressed size:</b> <code>{_fmt_size(total_bytes)}</code>\n\n"
        f"<b>Select your ZIP security preference:</b>\n"
        f"• <b>Protected ZIP:</b> Encrypted with custom password\n"
        f"• <b>Regular ZIP:</b> Standard fast archive without password"
    )
    await rich_reply(message, html_content, reply_markup=pass_button, client=client)


@Client.on_callback_query(filters.regex(r"^fzip$"))
async def zip_files_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_edit(
            callback_query,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can zip your files once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))] if os.path.exists(user_dir) else []

    if not files:
        return await rich_edit(
            callback_query,
            f"{EmojiTag.INFO} <b>You don't have files to zip yet.</b>\n\nSend me any files or direct links first, then use <code>/fzip</code>.",
            reply_markup=back_buttons,
            client=client,
        )

    total_bytes = sum(os.path.getsize(os.path.join(user_dir, f)) for f in files)

    html_content = (
        f"{rich_heading(f'{EmojiTag.LOCK} ZIP Archive Creation', level=1)}\n"
        f"<b>Files to bundle:</b> <code>{len(files)}</code>\n"
        f"<b>Total uncompressed size:</b> <code>{_fmt_size(total_bytes)}</code>\n\n"
        f"<b>Select your ZIP security preference:</b>\n"
        f"• <b>Protected ZIP:</b> Encrypted with custom password\n"
        f"• <b>Regular ZIP:</b> Standard fast archive without password"
    )
    await rich_edit(callback_query, html_content, reply_markup=pass_button, client=client)


@Client.on_message(filters.private & filters.command("unzip"))
async def unzip_command(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can use <code>/unzip</code> once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    if not os.path.exists(user_dir):
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me a compressed file first.",
            reply_markup=nofile_buttons,
            client=client,
        )

    files = [f for f in sorted(os.listdir(user_dir)) if os.path.isfile(os.path.join(user_dir, f))]
    if not files:
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me a compressed file first.",
            reply_markup=nofile_buttons,
            client=client,
        )

    # Check if a specific file index or name was passed: e.g. /unzip 1 or /unzip archive.zip
    text_parts = message.text.strip().split(maxsplit=1) if message.text else []
    if len(text_parts) > 1 and text_parts[1].strip():
        arg = text_parts[1].strip()
        matched_file = None
        # Try as 1-based index from /my_files
        try:
            idx = int(arg) - 1
            if 0 <= idx < len(files):
                target = files[idx]
                if await is_compressed(os.path.join(user_dir, target)):
                    matched_file = target
        except ValueError:
            pass

        # Try as exact filename or suffix match
        if not matched_file:
            for f in files:
                if f == arg or f.endswith(arg):
                    if await is_compressed(os.path.join(user_dir, f)):
                        matched_file = f
                        break

        if matched_file:
            cb_data = f"unzip|{matched_file}"
            if len(cb_data.encode("utf-8")) > 64:
                cb_data = f"unzip|{matched_file[-50:]}"
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"📦 Inspect {matched_file}", callback_data=cb_data, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ZIP)
                ],
                [
                    InlineKeyboardButton("❌ Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE)
                ]
            ])
            return await rich_reply(
                message,
                f"{rich_heading(f'{EmojiTag.EXTRACT} Archive Selected', level=2)}\n\n"
                f"Selected: <code>{rich_esc(matched_file)}</code>\n\nClick below to inspect and extract contents:",
                reply_markup=markup,
                client=client,
            )

    compressed_files = []
    for f in files:
        if await is_compressed(os.path.join(user_dir, f)):
            compressed_files.append(f)

    if not compressed_files:
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>No compressed archive found in your storage.</b>",
            reply_markup=nofile_buttons,
            client=client,
        )

    buttons = []
    for f in compressed_files:
        cb_data = f"unzip|{f}"
        if len(cb_data.encode("utf-8")) > 64:
            cb_data = f"unzip|{f[-50:]}"
        buttons.append([
            InlineKeyboardButton(f"📦 {f}", callback_data=cb_data, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ZIP)
        ])

    buttons.append([InlineKeyboardButton("❌ Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE)])
    markup = InlineKeyboardMarkup(buttons)

    await rich_reply(
        message,
        f"{rich_heading(f'{EmojiTag.EXTRACT} Select Archive to Extract', level=2)}\n\n"
        f"Select a compressed archive from your storage below:",
        reply_markup=markup,
        client=client,
    )


# ─── Media & Link Dispatchers ─────────────────────────────────────────────────

@Client.on_message(
    filters.private
    & (filters.document | filters.photo | filters.video | filters.audio
       | filters.voice | filters.video_note | filters.sticker | filters.animation)
)
async def handle_media(client: Client, message: Message):
    await enqueue_media_message(client, message)


@Client.on_message(
    filters.private
    & filters.text
    & ~filters.command([
        "start", "help", "my_files", "clear", "del", "fzip", "unzip",
        "status", "rst", "users", "set", "ad", "get", "broadcast",
        "reboot", "skip", "ping", "stats", "lang",
    ])
)
async def handle_links(client: Client, message: Message):
    if message.text.startswith("http"):
        await enqueue_link_message(client, message)


# ─── Queue Processor ─────────────────────────────────────────────────────────

async def process_queues():
    """Continuously process the download queue atomically."""
    while True:
        try:
            if not config.download_queue.empty():
                items = list(config.download_queue.queue)
                for item in items:
                    uid = item.from_user.id
                    if (uid not in config.downloading_users
                            and uid not in config.zipping_users
                            and uid not in config.uploading_users
                            and uid not in config.cancel_requested):
                        removed = await config.download_queue.async_remove(item)
                        if removed:
                            if getattr(item, "text", None) and item.text.startswith("http"):
                                asyncio.create_task(link_download(item, queued=True))
                            else:
                                asyncio.create_task(download(item, queued=True))
                            break
        except Exception as e:
            print(f"Error in process_queues: {e}")
        await asyncio.sleep(1)


# ─── File Listing ─────────────────────────────────────────────────────────────

async def list_files(client, message):
    user_id = message.from_user.id

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
        ])
        text = f"{EmojiTag.LOCK} <b>Membership Required</b>\n\nYou must join @nub_coders and @nub_coder_s to use this bot."
        return await rich_reply(message, text, reply_markup=button, client=client)

    _, max_storage, _ = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

    if not files:
        msg_text = (
            f"{rich_heading(f'{EmojiTag.FOLDER} Your Storage Directory', level=1)}\n\n"
            f"Your storage is currently empty.\n\n"
            f"<i>Send any document, photo, video, or direct HTTP link to get started!</i>"
        )
        return await rich_reply(message, msg_text, reply_markup=nofile_buttons, client=client)

    # Build native rich table
    table_rows = []
    for i, f in enumerate(files):
        f_path = os.path.join(user_dir, f)
        f_size = os.path.getsize(f_path) if os.path.exists(f_path) else 0
        badge = _detect_file_badge(f)
        table_rows.append((
            f"<code>{i+1}</code>",
            f"<code>{rich_esc(f[:24] + '...' if len(f) > 27 else f)}</code>",
            f"<code>{_fmt_size(f_size)}</code>",
            badge,
        ))

    headers = ["#", "File Name", "Size", "Type"]
    files_table = rich_table(headers, table_rows)

    used_gb = total_size / (1024 ** 3)
    free_gb = remaining_storage / (1024 ** 3)

    summary_pairs = [
        ("Total Files", f"<code>{len(files)}</code>"),
        ("Used Space", f"<code>{used_gb:.2f} GB</code>"),
        ("Available Space", f"<code>{free_gb:.2f} GB</code>"),
    ]
    summary_table = rich_kv_table(summary_pairs, headers=["Storage Overview", "Value"])

    content = (
        f"{rich_heading(f'{EmojiTag.FOLDER} Your Files in Storage', level=1)}\n"
        f"{files_table}\n\n"
        f"{summary_table}\n\n"
        f"💡 <b>Quick Tips:</b>\n"
        f"• Use <code>/del &lt;number&gt;</code> to delete a specific file\n"
        f"• Click <b>Compress Files</b> to pack into a ZIP archive"
    )

    await rich_reply(message, content, reply_markup=file_buttons, client=client)


# ─── File Size Helper ─────────────────────────────────────────────────────────

def _get_media_size(message: Message):
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
            return getter(message), enforce_limit
    return 0, False


def _get_filename(message: Message, user_id) -> str:
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
    return f"file_{user_id}_{ts}"


# ─── Download Handlers with Rich Progress ─────────────────────────────────────

async def download(message, queued: bool = False):
    user_id = message.from_user.id

    user_queue_count = sum(1 for item in list(config.download_queue.queue) if item.from_user.id == user_id)
    if user_id in config.downloading_users:
        user_queue_count += 1

    if user_queue_count >= 40:
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Queue limit reached.</b> You can have maximum 40 files in queue.",
            reply_markup=common_buttons,
        )

    if not queued and not rate_limiter.is_allowed(user_id):
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Sending files too frequently.</b> Please slow down.",
            reply_markup=common_buttons,
        )

    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)
    size, enforce_limit = _get_media_size(message)

    if enforce_limit and size > max_file_size:
        size_gb = max_file_size / (1024 ** 3)
        return await rich_reply(
            message,
            f"{EmojiTag.ERROR} <b>File exceeds limit.</b> Maximum single file size is <code>{size_gb:.1f} GB</code>.",
            reply_markup=common_buttons,
        )

    if size > remaining_storage:
        return await rich_reply(
            message,
            f"{EmojiTag.ERROR} <b>Not enough storage quota remaining.</b>\nRequired: <code>{_fmt_size(size)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
            reply_markup=common_buttons,
        )

    if await is_user_busy(user_id):
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Check Queue Status", callback_data="status", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.STATS)]
        ])
        await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>File added to download queue.</b>\nIt will start processing automatically when your turn arrives.",
            reply_markup=queue_button,
        )
        config.download_queue.put(message)
        return

    raw_name = _get_filename(message, user_id)
    try:
        dest_path = resolve_in_user_dir(user_dir, raw_name)
    except UnsafePathError:
        return await rich_reply(
            message,
            f"{EmojiTag.ERROR} <b>Invalid filename detected.</b> Please rename and re-upload.",
            reply_markup=common_buttons,
        )

    if not await set_downloading(user_id, True):
        config.user_ids[user_id] = True
        config.download_queue.put(message)
        return

    timer = Timer()
    fi_encoded = os.path.basename(dest_path)
    msg = None
    start_time = time.time()

    async def progress_bar(current, total):
        nonlocal msg
        if user_id in config.cancel_requested:
            config.cancel_requested.discard(user_id)
            raise StopTransmission()

        if not (timer.can_send() and total and msg):
            return

        pct = current * 100 / total
        bar_len = 16
        ticks = int(pct / (100 / bar_len))
        bar = "█" * ticks + "░" * (bar_len - ticks)

        elapsed = time.time() - start_time
        speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
        time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

        progress_card = (
            f"{rich_heading(f'{EmojiTag.DOWNLOAD} Downloading File', level=2)}\n"
            f"<b>File:</b> <code>{rich_esc(fi_encoded)}</code>\n"
            f"<b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
            + rich_kv_table([
                ("Transferred", f"<code>{_fmt_size(current)} / {_fmt_size(total)}</code>"),
                ("Speed", f"<code>{speed:.2f} MB/s</code>"),
                ("ETA", f"<code>{time_left:.1f}s</code>"),
                ("Elapsed", f"<code>{elapsed:.1f}s</code>"),
            ])
        )

        try:
            await rich_edit(msg, progress_card, reply_markup=cancel_markup)
        except Exception:
            pass

    cancelled = False
    try:
        msg = await rich_reply(
            message,
            f"{EmojiTag.DOWNLOAD} <b>Starting download:</b> <code>{rich_esc(fi_encoded)}</code>…",
            reply_markup=cancel_markup,
        )
        file_path = await asyncio.wait_for(
            message.download(file_name=dest_path, progress=progress_bar),
            timeout=1500,
        )
        await update_stats(user_id, "files_sent")

        dl_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else size
        _, remaining_storage_now, _ = get_file_size_info(user_dir, max_storage)
        used_now = max_storage - remaining_storage_now
        filename_only = os.path.basename(file_path) if file_path else fi_encoded

        summary_table = rich_kv_table([
            ("File Name", f"<code>{rich_esc(filename_only)}</code>"),
            ("File Size", f"<code>{_fmt_size(dl_size)}</code>"),
            ("Used Storage", f"<code>{_fmt_size(used_now)}</code>"),
            ("Available", f"<code>{_fmt_size(remaining_storage_now)}</code>"),
        ])

        if file_path and await is_compressed(file_path):
            cb_data = f"unzip|{filename_only}"
            if len(cb_data.encode("utf-8")) > 64:
                cb_data = f"unzip|{filename_only[-50:]}"
            uncompress_btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🗜️ Extract Archive", callback_data=cb_data, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.EXTRACT),
                    InlineKeyboardButton("🗂️ My Files", callback_data="my_files", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.FILE),
                ],
                [
                    InlineKeyboardButton("❌ Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE),
                ]
            ])
            await rich_edit(
                msg,
                f"{rich_heading(f'{EmojiTag.SUCCESS} Download Complete', level=2)}\n"
                f"{summary_table}\n\n"
                f"<i>📦 Compressed archive detected! Inspect or extract its contents below:</i>",
                reply_markup=uncompress_btn,
            )
        else:
            await rich_edit(
                msg,
                f"{rich_heading(f'{EmojiTag.SUCCESS} Download Complete', level=2)}\n"
                f"{summary_table}\n\n"
                f"<i>Use <code>/my_files</code> to view all files or <code>/fzip</code> to compress.</i>",
                reply_markup=file_buttons,
            )

        await _sleep_after_download(dl_size, queued=queued)
    except asyncio.TimeoutError:
        cancelled = True
        if msg:
            await rich_edit(msg, f"{EmojiTag.ERROR} <b>Download timed out.</b> (25-minute cap exceeded)")
    except StopTransmission:
        cancelled = True
        if msg:
            await rich_edit(msg, f"{EmojiTag.CANCEL} <b>Download cancelled by user.</b>")
    except Exception as e:
        if msg:
            await rich_edit(msg, f"{EmojiTag.ERROR} <b>Download failed:</b> <code>{rich_esc(e)}</code>")

    await set_downloading(user_id, False)
    config.user_ids.pop(user_id, None)
    await clear_cancel(user_id)


# ─── Direct Link Downloader ──────────────────────────────────────────────────

async def link_download(message, queued: bool = False):
    user_id = message.from_user.id

    user_queue_count = sum(1 for item in list(config.download_queue.queue) if item.from_user.id == user_id)
    if await is_user_busy(user_id):
        user_queue_count += 1

    if user_queue_count >= 40:
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Queue limit reached.</b> Maximum 40 files in queue.",
            reply_markup=common_buttons,
        )

    if not queued and not rate_limiter.is_allowed(user_id):
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Sending links too frequently.</b> Please slow down.",
            reply_markup=common_buttons,
        )

    link = message.text
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    try:
        declared_length, final_url = safe_head(link, max_bytes=remaining_storage)
    except SSRFBlocked as e:
        return await rich_reply(message, f"{EmojiTag.ERROR} <b>Blocked:</b> <code>{rich_esc(e)}</code>")
    except DownloadTooLarge as e:
        return await rich_reply(message, f"{EmojiTag.ERROR} <b>File too large:</b> <code>{rich_esc(e)}</code>")
    except (DownloadFailed, RedirectLimitExceeded) as e:
        return await rich_reply(message, f"{EmojiTag.ERROR} <b>Link verification failed:</b> <code>{rich_esc(e)}</code>")

    content_length = declared_length if declared_length is not None else 0
    if content_length and content_length > remaining_storage:
        return await rich_reply(
            message,
            f"{EmojiTag.ERROR} <b>Not enough storage quota.</b> Required: <code>{_fmt_size(content_length)}</code> | Available: <code>{_fmt_size(remaining_storage)}</code>",
        )

    if await is_user_busy(user_id):
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Check Queue Status", callback_data="status", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.STATS)]
        ])
        await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>Link added to download queue.</b>\nIt will start processing automatically.",
            reply_markup=queue_button,
        )
        config.download_queue.put(message)
        return

    raw_filename = link.split("?")[0].split("#")[0].split("/")[-1]
    try:
        file_path = resolve_in_user_dir(user_dir, raw_filename, fallback="download")
    except UnsafePathError:
        return await rich_reply(message, f"{EmojiTag.ERROR} <b>Could not derive safe filename from URL.</b>")

    filename = os.path.basename(file_path)

    msg_obj = await rich_reply(
        message,
        f"{EmojiTag.DOWNLOAD} <b>Initializing link download:</b> <code>{rich_esc(filename)}</code>…",
        reply_markup=cancel_markup,
    )

    if not await set_downloading(user_id, True):
        config.user_ids[user_id] = True
        config.download_queue.put(message)
        return

    config.user_ids[user_id] = True
    start_time = time.time()
    timer = Timer()

    async def progress_bar(current, total):
        if await is_cancel_requested(user_id):
            await clear_cancel(user_id)
            raise asyncio.CancelledError()

        if not (timer.can_send() and total and msg_obj):
            return

        pct = current * 100 / total
        bar_len = 16
        ticks = int(pct / (100 / bar_len))
        bar = "█" * ticks + "░" * (bar_len - ticks)

        elapsed = time.time() - start_time
        speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
        time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

        progress_card = (
            f"{rich_heading(f'{EmojiTag.DOWNLOAD} Downloading via Link', level=2)}\n"
            f"<b>File:</b> <code>{rich_esc(filename)}</code>\n"
            f"<b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
            + rich_kv_table([
                ("Transferred", f"<code>{_fmt_size(current)} / {_fmt_size(total)}</code>"),
                ("Speed", f"<code>{speed:.2f} MB/s</code>"),
                ("ETA", f"<code>{time_left:.1f}s</code>"),
                ("Elapsed", f"<code>{elapsed:.1f}s</code>"),
            ])
        )

        try:
            await rich_edit(msg_obj, progress_card, reply_markup=cancel_markup)
        except Exception:
            pass

    try:
        max_allowed = min(remaining_storage, config.MAX_DOWNLOAD_BYTES)
        await safe_download(
            link,
            file_path,
            max_bytes=max_allowed,
            progress_callback=lambda c, t: asyncio.create_task(progress_bar(c, t)),
        )
    except SSRFBlocked as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.ERROR} <b>Blocked:</b> <code>{rich_esc(e)}</code>")
    except DownloadTooLarge as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.ERROR} <b>File exceeds storage limits:</b> <code>{rich_esc(e)}</code>")
    except (DownloadFailed, RedirectLimitExceeded) as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.ERROR} <b>Download failed:</b> <code>{rich_esc(e)}</code>")
    except asyncio.CancelledError:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.CANCEL} <b>Download cancelled by user.</b>")
    except asyncio.TimeoutError:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.ERROR} <b>Download timed out (25-minute limit exceeded).</b>")
    except Exception as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await rich_edit(msg_obj, f"{EmojiTag.ERROR} <b>Error:</b> <code>{rich_esc(e)}</code>")

    dl_size = os.path.getsize(file_path) if os.path.exists(file_path) else content_length
    _, remaining_storage_now, _ = get_file_size_info(user_dir, max_storage)
    used_now = max_storage - remaining_storage_now
    filename_only = os.path.basename(file_path)

    summary_table = rich_kv_table([
        ("File Name", f"<code>{rich_esc(filename_only)}</code>"),
        ("File Size", f"<code>{_fmt_size(dl_size)}</code>"),
        ("Used Storage", f"<code>{_fmt_size(used_now)}</code>"),
        ("Available", f"<code>{_fmt_size(remaining_storage_now)}</code>"),
    ])

    if await is_compressed(file_path):
        cb_data = f"unzip|{filename_only}"
        if len(cb_data.encode("utf-8")) > 64:
            cb_data = f"unzip|{filename_only[-50:]}"
        uncompress_btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗜️ Extract Archive", callback_data=cb_data, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.EXTRACT),
                InlineKeyboardButton("🗂️ My Files", callback_data="my_files", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.FILE),
            ],
            [
                InlineKeyboardButton("❌ Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE),
            ]
        ])
        await rich_edit(
            msg_obj,
            f"{rich_heading(f'{EmojiTag.SUCCESS} Download Complete', level=2)}\n"
            f"{summary_table}\n\n"
            f"<i>📦 Compressed archive detected! Inspect or extract its contents below:</i>",
            reply_markup=uncompress_btn,
        )
    else:
        await rich_edit(
            msg_obj,
            f"{rich_heading(f'{EmojiTag.SUCCESS} Download Complete', level=2)}\n"
            f"{summary_table}\n\n"
            f"<i>Use <code>/my_files</code> to view all files or <code>/fzip</code> to compress.</i>",
            reply_markup=file_buttons,
        )

    await _sleep_after_download(dl_size, queued)
    await set_downloading(user_id, False)
    config.downloading_users.discard(user_id)
    config.user_ids.pop(user_id, None)
    config.cancel_requested.discard(user_id)

    if not queued:
        await update_stats(user_id, "link_downloads")
