import config
from config import collection
from rate_limiter import rate_limiter
from pyrogram import Client, filters, StopTransmission
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from tools import get_user_status, Timer, get_file_size_info, is_user_on_chat, is_compressed
from safe_paths import UnsafePathError, resolve_in_user_dir
from safe_download import safe_download, safe_head, SSRFBlocked, DownloadTooLarge, DownloadFailed, RedirectLimitExceeded
from plugins.ui_components import (
    home_buttons, common_buttons, file_buttons,
    nofile_buttons, back_buttons, pass_button,
)
from stats_manager import update_stats
import os
import time
import asyncio
import random


# ─── Size Formatter ───────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    """Return a human-readable size string picking the best unit."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


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


@Client.on_message(filters.private & filters.command("del"))
async def delete_file(client: Client, message: Message):
    user_id = str(message.from_user.id)
    user_dir = f"{config.ggg}/zipper/{user_id}"

    try:
        file_number = int(message.text.split("/del ")[1]) - 1
    except (IndexError, ValueError):
        return await message.reply_text(
            "Invalid file number. Use /del <file_number> to delete a file.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    if not os.path.exists(user_dir):
        return await message.reply_text(
            "Your directory doesn't exist. Send me any file to create your directory.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    files = os.listdir(user_dir)
    if 0 <= file_number < len(files):
        target = os.path.join(user_dir, files[file_number])
        os.remove(target)
        return await message.reply_text(
            f"File '{files[file_number]}' has been deleted.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    return await message.reply_text("Invalid file number.", reply_parameters=ReplyParameters(message_id=message.id))


@Client.on_message(filters.private & filters.command("clear"))
async def clear_files(client: Client, message: Message):
    from tools import handle_clear_files
    user_id = message.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
    if hasattr(message, "edit_message_text"):
        await message.edit_message_text(message_text, reply_markup=back_buttons)
    else:
        await message.reply_text(message_text, reply_markup=back_buttons)


@Client.on_message(filters.private & filters.command("fzip"))
async def zip_files_command(client: Client, message: Message):
    user_id = message.from_user.id
    # Block zipping only if THIS user is downloading or uploading
    if user_id in config.downloading_users or user_id in config.uploading_users:
        reason = "downloading" if user_id in config.downloading_users else "uploading"
        return await message.reply_text(
            f"⏳ **Please wait**\n\n"
            f"Your file is currently {reason}.\n"
            f"You can zip your files once it's done.\n\n"
            f"Use /status to check progress or cancel.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    await message.reply_text(
        "🔐 **ZIP File Creation**\n\n"
        "Choose your ZIP security option:\n"
        "• Password-protected ZIP for extra security\n"
        "• Regular ZIP for easy access\n\n"
        "Select your preference below:",
        reply_markup=pass_button,
        reply_parameters=ReplyParameters(message_id=message.id),
    )

@Client.on_message(filters.private & filters.command("unzip"))
async def unzip_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Block only if THIS user has a task in progress
    if user_id in config.downloading_users or user_id in config.zipping_users or user_id in config.uploading_users:
        if user_id in config.downloading_users:
            reason = "downloading"
        elif user_id in config.zipping_users:
            reason = "compressing"
        else:
            reason = "uploading"
        return await message.reply_text(
            f"⏳ **Please wait**\n\n"
            f"Your file is currently {reason}.\n"
            f"You can use /unzip once it's done.\n\n"
            f"Use /status to check progress or cancel.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    
    if not os.path.exists(user_dir):
        return await message.reply_text(
            "Your directory is empty. Send me a compressed file first.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    msg = await message.reply_text("Scanning your files for compressed archives...")
    files = os.listdir(user_dir)
    compressed_files = []
    
    for f in files:
        if is_compressed(os.path.join(user_dir, f)):
            compressed_files.append(f)
            
    if not compressed_files:
        return await msg.edit_text("No compressed files found in your directory.")
        
    buttons = []
    for f in compressed_files:
        cb_data = f"unzip|{f}"
        if len(cb_data.encode('utf-8')) > 64:
            cb_data = f"unzip|{f[-50:]}"
        buttons.append([InlineKeyboardButton(f"📦 {f}", callback_data=cb_data)])
        
    buttons.append([InlineKeyboardButton("❌ Dismiss", callback_data="dismiss")])
    markup = InlineKeyboardMarkup(buttons)
    
    await msg.edit_text(
        "🗜️ **Select a compressed file to uncompress:**",
        reply_markup=markup
    )


# ─── Media Handler ────────────────────────────────────────────────────────────

@Client.on_message(
    filters.private
    & (filters.document | filters.photo | filters.video | filters.audio
       | filters.voice | filters.video_note | filters.sticker | filters.animation)
)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    # Block file sending only if THIS user is zipping or uploading
    if user_id in config.zipping_users or user_id in config.uploading_users:
        reason = "compressing" if user_id in config.zipping_users else "uploading"
        return await message.reply_text(
            f"⏳ **Please wait**\n\n"
            f"Your file is currently {reason}.\n"
            f"Please send your files after the current process finishes.\n\n"
            f"Use /status to check progress or cancel.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    await download(message)


@Client.on_message(
    filters.private
    & filters.text
    & ~filters.command([
        "start", "help", "my_files", "clear", "del", "fzip", "unzip",
        "status", "rst", "users", "set", "ad", "get", "broadcast",
        "reboot", "skip",
    ])
)
async def handle_links(client: Client, message: Message):
    if message.text.startswith("http"):
        user_id = message.from_user.id
        if user_id in config.zipping_users or user_id in config.uploading_users:
            reason = "compressing" if user_id in config.zipping_users else "uploading"
            return await message.reply_text(
                f"⏳ **Please wait**\n\n"
                f"Your file is currently {reason}.\n"
                f"Please send your links after the current process finishes.\n\n"
                f"Use /status to check progress or cancel.",
                reply_markup=common_buttons,
                reply_parameters=ReplyParameters(message_id=message.id),
            )
        await link_download(message)


# ─── Queue Processor ─────────────────────────────────────────────────────────

async def process_queues():
    """Continuously process the download queue.
    
    Atomically dequeues items before any async operations to prevent:
    - Queue corruption from overlapping iterations
    - Duplicate processing of the same item
    - Lost items due to concurrent modifications
    
    Uses create_task() to prevent the queue loop from blocking during long downloads.
    """
    while True:
        try:
            if not config.download_queue.empty():
                items = list(config.download_queue.queue)
                for item in items:
                    uid = item.from_user.id
                    # Check: user is not already active AND not in cancellation queue
                    if (uid not in config.downloading_users
                            and uid not in config.zipping_users
                            and uid not in config.uploading_users
                            and uid not in config.cancel_requested):
                        # Atomically remove BEFORE any await to prevent races
                        removed = await config.download_queue.async_remove(item)
                        if removed:
                            # Now safe to dispatch async tasks (won't block the queue loop)
                            if getattr(item, "text", None) and item.text.startswith("http"):
                                asyncio.create_task(link_download(item, queued=True))
                            else:
                                asyncio.create_task(download(item, queued=True))
                            break  # Process one item per iteration to prevent starvation
        except Exception as e:
            print(f"Error in process_queues: {e}")
        await asyncio.sleep(1)


# ─── File Listing ─────────────────────────────────────────────────────────────

async def list_files(client, message):
    user_id = message.from_user.id

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders")],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s")],
        ])
        text = "You need to join both @nub_coders and @nub_coder_s channels to use this bot.\n\nClick below to Join!"
        if hasattr(message, "edit_message_text"):
            return await message.edit_message_text(text, reply_markup=button)
        return await message.reply_text(text, reply_markup=button)

    _, max_storage, _ = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

    if not files:
        msg_text = "Your directory is empty, send me any file"
        if hasattr(message, "edit_message_text"):
            return await message.edit_message_text(msg_text, reply_markup=nofile_buttons)
        return await message.reply_text(msg_text, reply_markup=nofile_buttons)

    file_entries = [
        f"{i+1}. {f} - {_fmt_size(os.path.getsize(os.path.join(user_dir, f)))}"
        for i, f in enumerate(files)
    ]

    header = (
        f"📊 **Storage Overview**\n\n"
        f"💾 Used Space: {_fmt_size(total_size)}\n"
        f"💿 Available Space: {_fmt_size(remaining_storage)}\n"
        f"📁 Total Files: {len(files)}\n\n"
        f"📋 **Your Files:**\n"
        f"• Use /del <number> to remove a file\n"
        f"• Use /fzip to compress files\n"
        f"• Use /clear to remove all files\n\n"
    )

    # Split long messages to stay within Telegram's 4096-char limit
    chunks = []
    current = header
    for entry in file_entries:
        line = f"<blockquote>{entry}</blockquote>\n"
        if len(current) + len(line) > 4096:
            chunks.append(current)
            current = line
        else:
            current += line
    chunks.append(current)

    for i, chunk in enumerate(chunks):
        markup = file_buttons if i == len(chunks) - 1 else None
        if hasattr(message, "edit_message_text") and i == 0:
            await message.edit_message_text(chunk, reply_markup=markup)
        else:
            await message.reply_text(chunk, reply_markup=markup)


# ─── File Size Helper ─────────────────────────────────────────────────────────

def _get_media_size(message: Message):
    """Extract file size and determine if it should be size-checked."""
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
    """Determine the *untrusted* display name for the downloaded media.

    The returned value is attacker-controlled for documents/videos/audio (it is
    a client-supplied MTProto attribute) and must never be used as a filesystem
    path without passing through ``resolve_in_user_dir``.
    """
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


# ─── Download Handler ─────────────────────────────────────────────────────────

async def download(message, queued: bool = False):
    user_id = message.from_user.id

    user_queue_count = sum(1 for item in list(config.download_queue.queue) if item.from_user.id == user_id)
    if user_id in config.downloading_users:
        user_queue_count += 1

    if user_queue_count >= 40:
        return await message.reply_text(
            "You can only have 40 files in the queue at a time. Please wait for some files to finish.",
            reply_markup=common_buttons,
            reply_to_message_id=message.id,
        )

    # Rate limiting (bypassed for queued files)
    if not queued and not rate_limiter.is_allowed(user_id):
        return await message.reply_text(
            "You are sending files too frequently. Please wait before sending more files.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)
    size, enforce_limit = _get_media_size(message)

    if enforce_limit and size > max_file_size:
        size_gb = max_file_size / (1024**3)
        return await message.reply_text(
            f"Please send a file smaller than {size_gb:.1f}GB.\n/my_files to show your files",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    if size > remaining_storage:
        await message.reply_text(
            "Not enough storage space to download this file.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        return

    if await is_user_busy(user_id):
        # This user already has an active download — enqueue
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Check your queue", callback_data="bhad")]]
        )
        await message.reply_text(
            "I have added your file in queue to download",
            reply_markup=queue_button,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        config.download_queue.put(message)
        return

    raw_name = _get_filename(message, user_id)

    # SECURITY (Z-01): never hand a bare directory to message.download(). Pyrogram
    # would then derive the filename from the client-supplied MTProto attribute and
    # os.path.join/abspath would honour "../" and absolute paths, allowing writes
    # anywhere the process can reach. Compute a contained absolute path ourselves.
    #
    # Resolved before the busy flags are set: an early return after
    # downloading_users.add() would leak the flag and lock the user out until
    # restart, since only the download's own completion path clears it.
    try:
        dest_path = resolve_in_user_dir(user_dir, raw_name)
    except UnsafePathError:
        return await message.reply_text(
            "❌ That file's name isn't usable. Please rename it and send it again.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    # Start downloading - use async state manager
    if not await set_downloading(user_id, True):
        # This should not happen since we checked is_user_busy above
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Check your queue", callback_data="bhad")]]
        )
        await message.reply_text(
            "I have added your file in queue to download",
            reply_markup=queue_button,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        config.download_queue.put(message)
        return

    timer = Timer()

    # Display name only -- kept separate from the path so a hostile name cannot
    # break message formatting or be mistaken for a real location.
    fi_encoded = os.path.basename(dest_path)
    msg = None

    async def progress_bar(current, total, start_time=time.time()):
        nonlocal msg
        # Check for cancellation
        if user_id in config.cancel_requested:
            config.cancel_requested.discard(user_id)
            raise StopTransmission()

        if not (timer.can_send() and total and msg):
            return

        config.time_left = 0
        pct = current * 100 / total
        bar_len = 30
        ticks = int(pct / (100 / bar_len))
        bar = "█" * ticks + "░" * (bar_len - ticks)

        elapsed = time.time() - start_time
        speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
        config.time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

        text = (
            f"⏬ **Downloading: {fi_encoded}**\n\n"
            f"📊 Progress: {pct:.1f}%\n"
            f"⚡ Speed: {speed:.1f} MB/s\n"
            f"⏱️ Remaining: {config.time_left:.1f}s\n"
            f"📦 Size: {current/(1024*1024):.1f}/{total/(1024*1024):.1f} MB\n"
            f"{bar}\n\n"
            f"Please wait while I process your file…"
        )

        cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task")]])
        try:
            await msg.edit_text(text, reply_markup=cancel_markup)
        except Exception as e:
            print(e)

    cancelled = False
    try:
        msg = await message.reply_text("Downloading started", reply_parameters=ReplyParameters(message_id=message.id))
        file_path = await asyncio.wait_for(
            message.download(file_name=dest_path, progress=progress_bar),
            timeout=1500  # 25 minutes auto-cancel
        )
        await update_stats(user_id, "files_sent")
        
        if file_path and is_compressed(file_path):
            filename_only = os.path.basename(file_path)
            dl_size = os.path.getsize(file_path) if os.path.exists(file_path) else size
            _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)
            total_size_used = max_storage - remaining_storage
            cb_data = f"unzip|{filename_only}"
            if len(cb_data.encode('utf-8')) > 64:
                cb_data = f"unzip|{filename_only[-50:]}"
            uncompress_btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("uncompress", callback_data=cb_data),
                 InlineKeyboardButton("dismiss", callback_data="dismiss")]
            ])
            await msg.edit_text(
                f"✅ **Finished downloading**\n"
                f"📄 `{filename_only}` — {_fmt_size(dl_size)}\n"
                f"💾 Used: {_fmt_size(total_size_used)} / Available: {_fmt_size(remaining_storage)}\n"
                f"/my_files to see your files\n\n"
                f"🗜️ **Compressed file detected!**\n"
                f"Would you like to uncompress it and receive the files? (only if uncompressed file/files size not more than 2 GB)",
                reply_markup=uncompress_btn
            )
        else:
            filename_only = os.path.basename(file_path) if file_path else "file"
            dl_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else size
            _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)
            total_size_used = max_storage - remaining_storage
            await msg.edit_text(
                f"✅ **Finished downloading**\n"
                f"📄 `{filename_only}` — {_fmt_size(dl_size)}\n"
                f"💾 Used: {_fmt_size(total_size_used)} / Available: {_fmt_size(remaining_storage)}\n"
                f"/my_files to see your files"
            )

        await _sleep_after_download(dl_size, queued=queued)
    except asyncio.TimeoutError:
        cancelled = True
        if msg:
            await msg.edit_text("❌ **Download timed out**\n\nThis file took more than 25 minutes and was auto-cancelled to free the queue.")
    except StopTransmission:
        cancelled = True
        if msg:
            await msg.edit_text("❌ **Download cancelled**\n\nYour download has been stopped.")
    except Exception as e:
        error_text = f"Download failed: {e}\nPlease resend this file"
        if msg:
            await msg.edit_text(error_text)
        else:
            await message.reply_text(error_text, reply_parameters=ReplyParameters(message_id=message.id))

    await set_downloading(user_id, False)
    config.user_ids.pop(user_id, None)
    await clear_cancel(user_id)

    if cancelled:
        # Clean up partially downloaded file
        pass  # Don't call timeout on cancel — just stop


# ─── Link Download ────────────────────────────────────────────────────────────

async def link_download(message, queued: bool = False):
    user_id = message.from_user.id

    user_queue_count = sum(1 for item in list(config.download_queue.queue) if item.from_user.id == user_id)
    if await is_user_busy(user_id):
        user_queue_count += 1

    if user_queue_count >= 40:
        return await message.reply_text(
            "You can only have 40 files in the queue at a time. Please wait for some files to finish.",
            reply_markup=common_buttons,
            reply_to_message_id=message.id,
        )

    # Rate limiting (bypassed for queued links)
    if not queued and not rate_limiter.is_allowed(user_id):
        return await message.reply_text(
            "You are sending links too frequently. Please wait before sending more links.",
            reply_markup=common_buttons,
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    link = message.text
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    _, remaining_storage, _ = get_file_size_info(user_dir, max_storage)

    # Pre-flight HEAD check using safe_download's validation (SSRF + size + redirects)
    try:
        declared_length, final_url = safe_head(link, max_bytes=remaining_storage)
    except SSRFBlocked as e:
        return await message.reply_text(
            f"❌ Blocked: {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    except DownloadTooLarge as e:
        return await message.reply_text(
            f"❌ {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    except (DownloadFailed, RedirectLimitExceeded) as e:
        return await message.reply_text(
            f"Download failed: {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    # Use the declared length for queue decision and progress reporting
    content_length = declared_length if declared_length is not None else 0
    if content_length and content_length > remaining_storage:
        return await message.reply_text(
            "Not enough storage space.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    if user_id in config.downloading_users:
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Check your queue", callback_data="bhad")]]
        )
        await message.reply_text(
            "I have added your link in queue to download",
            reply_markup=queue_button,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        config.download_queue.put(message)
        return

    # SECURITY (Z-20): the URL's last path segment is untrusted. It cannot contain
    # "/", but it can be "..", exceed NAME_MAX, carry a query string or control
    # characters, or silently overwrite an existing file. Contain it and make it
    # unique so concurrent jobs cannot target the same path (Z-12).
    raw_filename = link.split("?")[0].split("#")[0].split("/")[-1]
    try:
        file_path = resolve_in_user_dir(user_dir, raw_filename, fallback="download")
    except UnsafePathError:
        return await message.reply_text(
            "❌ Could not derive a safe filename from that URL.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    filename = os.path.basename(file_path)

    msg_obj = await message.reply_text(
        f"Downloading {filename}\nFile size: {content_length or 'unknown'} bytes\nStarting download",
        reply_parameters=ReplyParameters(message_id=message.id),
    )

    if not await set_downloading(user_id, True):
        # Should not happen since we checked above, but fall back to queue
        config.user_ids[user_id] = True
        queue_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Check your queue", callback_data="bhad")]]
        )
        await message.reply_text(
            "I have added your link in queue to download",
            reply_markup=queue_button,
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        config.download_queue.put(message)
        return

    config.user_ids[user_id] = True
    start_time = time.time()

    timer = Timer()

    async def progress_bar(current, total, start_time, msg, fi_encoded):
        # Check for cancellation
        if await is_cancel_requested(user_id):
            await clear_cancel(user_id)
            raise asyncio.CancelledError()

        if not (timer.can_send() and total and msg):
            return

        config.time_left = 0
        pct = current * 100 / total
        bar_len = 30
        ticks = int(pct / (100 / bar_len))
        bar = "█" * ticks + "░" * (bar_len - ticks)

        elapsed = time.time() - start_time
        speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
        config.time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

        text = (
            f"⏬ **Downloading: {fi_encoded}**\n\n"
            f"📊 Progress: {pct:.1f}%\n"
            f"⚡ Speed: {speed:.1f} MB/s\n"
            f"⏱️ Remaining: {config.time_left:.1f}s\n"
            f"📦 Size: {current/(1024*1024):.1f}/{total/(1024*1024):.1f} MB\n"
            f"{bar}\n\n"
            f"Please wait while I process your file..."
        )

        cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task")]])
        try:
            await msg.edit_text(text, reply_markup=cancel_markup)
        except Exception as e:
            print(e)

    try:
        await safe_download(
            link,
            file_path,
            max_bytes=max(remaining_storage, config.MAX_EXTRACT_BYTES),
            progress_callback=lambda c, t: asyncio.create_task(progress_bar(c, t, start_time, msg_obj, filename)),
        )
    except SSRFBlocked as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await message.reply_text(
            f"❌ Blocked: {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    except DownloadTooLarge as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await message.reply_text(
            f"❌ {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    except (DownloadFailed, RedirectLimitExceeded) as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        return await message.reply_text(
            f"Download failed: {e}",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
    except asyncio.CancelledError:
        # Already handled in progress_bar
        return
    except asyncio.TimeoutError:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        if 'msg_obj' in dir():
            await msg_obj.edit_text("❌ **Download timed out**\n\nThis file took more than 25 minutes and was auto-cancelled to free the queue.")
        return
    except Exception as e:
        await set_downloading(user_id, False)
        config.user_ids.pop(user_id, None)
        await message.reply_text(str(e), reply_parameters=ReplyParameters(message_id=message.id))
        return

    if is_compressed(file_path):
        filename_only = os.path.basename(file_path)
        dl_size = os.path.getsize(file_path) if os.path.exists(file_path) else content_length
        _, remaining_storage_now, _ = get_file_size_info(user_dir, max_storage)
        total_size_used = max_storage - remaining_storage_now
        cb_data = f"unzip|{filename_only}"
        if len(cb_data.encode('utf-8')) > 64:
            cb_data = f"unzip|{filename_only[-50:]}"
        uncompress_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("uncompress", callback_data=cb_data),
             InlineKeyboardButton("dismiss", callback_data="dismiss")]
        ])
        await msg_obj.edit_text(
            f"✅ **Downloaded successfully**\n"
            f"📄 `{filename}` — {_fmt_size(dl_size)}\n"
            f"💾 Used: {_fmt_size(total_size_used)} / Available: {_fmt_size(remaining_storage_now)}\n"
            f"/my_files to check all your files\n\n"
            f"🗜️ **Compressed file detected!**\n"
            f"Would you like to uncompress it and receive the files? (only if uncompressed file/files size not more than 2 GB)",
            reply_markup=uncompress_btn
        )
    else:
        dl_size = os.path.getsize(file_path) if os.path.exists(file_path) else content_length
        _, remaining_storage_now, _ = get_file_size_info(user_dir, max_storage)
        total_size_used = max_storage - remaining_storage_now
        await msg_obj.edit_text(
            f"✅ **Downloaded successfully**\n"
            f"📄 `{filename}` — {_fmt_size(dl_size)}\n"
            f"💾 Used: {_fmt_size(total_size_used)} / Available: {_fmt_size(remaining_storage_now)}\n"
            f"/my_files to check all your files"
        )

    await _sleep_after_download(
        os.path.getsize(file_path) if os.path.exists(file_path) else content_length,
        queued,
    )
    config.downloading_users.discard(user_id)
    config.user_ids.pop(user_id, None)
    config.cancel_requested.discard(user_id)

    if not queued:
        await update_stats(user_id, "link_downloads")
