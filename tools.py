import asyncio
import os
import shutil
import time
from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.errors import UserNotParticipant
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from safe_archive import list_archive, looks_encrypted
from safe_paths import UnsafePathError, resolve_in_user_dir
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


# ─── Channel Membership Check ────────────────────────────────────────────────

async def is_user_on_chat(client: Client, user_id: int) -> bool:
    """Return True if user is a member of required channels; fallback to True if checks fail."""
    try:
        for chan in ("nub_coders", "nub_coder_s"):
            try:
                member = await client.get_chat_member(chan, user_id)
                if member.status in ("left", "kicked", "banned"):
                    return False
            except UserNotParticipant:
                return False
            except Exception:
                continue
        return True
    except Exception:
        return True


# ─── Admin Utilities ──────────────────────────────────────────────────────────

def get_admin_ids():
    """Get list of admin IDs from ADMIN_IDS env var."""
    env = os.getenv("ADMIN_IDS", "").strip()
    if env:
        try:
            return [int(x.strip()) for x in env.split(",") if x.strip()]
        except ValueError:
            return []
    return []


def is_admin(user_id):
    """Check if user is admin."""
    return user_id in get_admin_ids()


# ─── User Management ─────────────────────────────────────────────────────────

def store_user(collection, user_id):
    """Store user in database with current timestamp and initialised stats."""
    current_time = int(time.time())
    user_data = {
        "user_id": user_id,
        "timestamp": current_time,
        "lang": "en",
        "stats": {
            "files_sent": 0,
            "zip_with_pass": 0,
            "zip_without_pass": 0,
            "external_uploads": 0,
            "last_reset": current_time,
        },
    }
    collection.update_one({"user_id": user_id}, {"$setOnInsert": user_data}, upsert=True)


def get_user_status(collection, user_id):
    """Get user storage and file-size limits.

    Returns:
        (is_verified, max_storage_bytes, max_file_size_bytes)
    """
    user_data = collection.find_one({"user_id": user_id})

    if not user_data:
        store_user(collection, user_id)

    return True, int(4.5 * 1024**3), 2 * 1024**3


def get_user_lang(collection, user_id):
    """Get the user's language preference from the database."""
    user = collection.find_one({"user_id": user_id})
    if user and "lang" in user:
        return user["lang"]
    return "en"


def set_user_lang(collection, user_id, lang_code):
    """Update the user's language preference."""
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang_code}},
        upsert=True,
    )


def get_text(collection, user_id, text_key):
    """Fetch a translated string based on the user's language."""
    from i18n import TEXTS
    lang = get_user_lang(collection, user_id)
    if lang not in TEXTS:
        lang = "en"
    return TEXTS[lang].get(text_key, TEXTS["en"].get(text_key, text_key))


# ─── File / Directory Utilities ───────────────────────────────────────────────

async def is_compressed(file_path):
    """Check if a file is a compressed archive using 7z listing."""
    if not os.path.exists(file_path):
        return False
    try:
        listing, _ = await list_archive(file_path)
        return looks_encrypted(listing) or "Path =" in listing
    except Exception:
        return False


def get_file_size_info(user_dir, max_storage):
    """Return (total_size, remaining_storage, file_list) for a user directory."""
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
        return 0, max_storage, []

    files = sorted(os.listdir(user_dir))
    total_size = 0
    valid_files = []
    for f in files:
        f_path = os.path.join(user_dir, f)
        try:
            if os.path.isfile(f_path):
                total_size += os.path.getsize(f_path)
                valid_files.append(f)
            elif os.path.isdir(f_path):
                for root, _, dirfiles in os.walk(f_path):
                    for df in dirfiles:
                        df_path = os.path.join(root, df)
                        if os.path.isfile(df_path):
                            total_size += os.path.getsize(df_path)
                valid_files.append(f)
        except OSError:
            continue

    remaining = max(0, max_storage - total_size)
    return total_size, remaining, valid_files


def cleanup_user_directory(user_dir):
    """Remove all files in user directory and recreate it."""
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
    os.makedirs(user_dir, exist_ok=True)


async def handle_clear_files(user_id, reply_markup=None):
    """Handle clearing all files for a user. Returns a status message string."""
    import config
    user_dir = f"{config.ggg}/zipper/{user_id}"
    if os.path.exists(user_dir):
        cleanup_user_directory(user_dir)
        return "All files in your storage directory have been permanently deleted."
    return "Your storage directory is already empty."


# ─── Timer (progress bar throttle) ───────────────────────────────────────────

class Timer:
    """Simple timer to throttle progress-bar edits."""

    def __init__(self, time_between=2, interval_seconds=None):
        self.start_time = time.time()
        self.time_between = interval_seconds if interval_seconds is not None else time_between

    def can_send(self):
        now = time.time()
        if now > self.start_time + self.time_between:
            self.start_time = now
            return True
        return False


# ─── Queue Status ─────────────────────────────────────────────────────────────

def get_queue_status(user_id):
    """Build a rich formatted queue-status string."""
    import config

    pending_tasks = list(config.download_queue.queue)
    active_users = len(config.downloading_users | config.zipping_users | config.uploading_users)
    active_task_users = config.downloading_users | config.zipping_users | config.uploading_users
    queue_size = len(pending_tasks)

    user_task_counts = {}
    for t in pending_tasks:
        uid = t.from_user.id
        user_task_counts[uid] = user_task_counts.get(uid, 0) + 1

    queue_pairs = [
        ("Active Workers", f"<code>{active_users} user(s)</code>"),
        ("Queue Backlog", f"<code>{queue_size} task(s)</code>"),
    ]
    if user_id in user_task_counts:
        queue_pairs.append(("Your Queued Files", f"<code>{user_task_counts[user_id]}</code>"))

    table = rich_kv_table(queue_pairs, headers=["Queue Metrics", "Status"])

    if user_id in active_task_users:
        note = rich_note(f"{EmojiTag.ROCKET} <b>Your task is actively processing right now!</b>")
    elif user_id in user_task_counts:
        note = rich_note(f"{EmojiTag.CLOCK} <b>You have {user_task_counts[user_id]} task(s) waiting in queue.</b>")
    else:
        note = rich_note(f"{EmojiTag.INFO} You have no files in queue.")

    return f"{rich_heading(f'{EmojiTag.STATS} Download Queue Monitor', level=2)}\n{table}\n\n{note}"


# ─── ZIP Creation ─────────────────────────────────────────────────────────────

async def create_zip_file(client, callback_query, pass_protect=None):
    """Interactively create a ZIP file from the user's uploaded files."""
    user_id = callback_query.from_user.id

    try:
        await rich_send(
            client,
            user_id,
            f"{EmojiTag.FILE} <b>Please reply with a name for your ZIP file</b> (e.g. <code>my_archive.zip</code>):",
        )
        response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        password = ""
        if pass_protect:
            await rich_send(
                client,
                user_id,
                f"{EmojiTag.LOCK} <b>Please reply with your desired ZIP password:</b>",
            )
            get_pass = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
    except Exception as e:
        await rich_reply(callback_query, f"{EmojiTag.ERROR} <b>Operation timed out or failed:</b> <code>{rich_esc(e)}</code>")
        return None, None

    file_name = response.text

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
        ])
        await rich_reply(
            callback_query,
            f"{EmojiTag.LOCK} <b>Channel Membership Required</b>\n\nPlease join @nub_coders and @nub_coder_s to use this bot.",
            reply_markup=button,
        )
        return None, None

    import config
    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = os.listdir(user_dir) if os.path.exists(user_dir) else []

    if not files:
        from plugins.ui_components import back_buttons
        await rich_reply(
            callback_query,
            f"{EmojiTag.INFO} <b>No files found to compress.</b> Send files first.",
            reply_markup=back_buttons,
        )
        return None, None

    try:
        zip_filename = resolve_in_user_dir(
            user_dir, file_name, fallback="archive", force_suffix=".zip"
        )
    except UnsafePathError:
        await rich_reply(
            callback_query,
            f"{EmojiTag.ERROR} <b>Filename not allowed.</b> Please choose a simple name like <code>backup.zip</code>.",
        )
        return None, None

    files = [fn for fn in files if os.path.join(user_dir, fn) != zip_filename]
    files = [
        fn for fn in files
        if os.path.isfile(os.path.join(user_dir, fn))
        and not os.path.islink(os.path.join(user_dir, fn))
    ]

    if not files:
        from plugins.ui_components import back_buttons
        await rich_reply(
            callback_query,
            f"{EmojiTag.INFO} <b>No files found to compress.</b> Send files first.",
            reply_markup=back_buttons,
        )
        return None, None

    original_size = sum(os.path.getsize(os.path.join(user_dir, fn)) for fn in files)

    message = await rich_send(
        client,
        user_id,
        f"{EmojiTag.COMPRESS} <b>Packing {len(files)} file(s) into ZIP archive…</b>",
    )

    import pyminizip
    import zipfile

    def _fmt(size_bytes):
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def _sync_compress_password(paths, prefixes, out_zip, pw):
        import pyminizip
        pyminizip.compress_multiple(paths, prefixes, out_zip, pw, 4)

    def _sync_compress_standard(paths, out_zip):
        import zipfile
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as zipf:
            for fpath in paths:
                zipf.write(fpath, os.path.basename(fpath))

    file_paths = [os.path.join(user_dir, fn) for fn in files]

    try:
        if pass_protect and password:
            prefixes = [""] * len(files)
            await asyncio.to_thread(_sync_compress_password, file_paths, prefixes, zip_filename, password)
        else:
            await asyncio.to_thread(_sync_compress_standard, file_paths, zip_filename)
    except Exception as e:
        await rich_edit(message, f"{EmojiTag.ERROR} <b>Error creating ZIP:</b> <code>{rich_esc(e)}</code>")
        return None, message

    compressed_size = os.path.getsize(zip_filename) if os.path.exists(zip_filename) else 0
    savings_pct = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    lock_status = "🔐 Password Protected" if pass_protect and password else "📦 Standard ZIP"

    summary_pairs = [
        ("Archive Name", f"<code>{rich_esc(os.path.basename(zip_filename))}</code>"),
        ("Original Size", f"<code>{_fmt(original_size)}</code>"),
        ("Compressed Size", f"<code>{_fmt(compressed_size)}</code>"),
        ("Space Saved", f"<code>{savings_pct:.1f}%</code>"),
        ("Security", f"<code>{lock_status}</code>"),
    ]
    summary_table = rich_kv_table(summary_pairs, headers=["Compression Result", "Value"])

    result_text = (
        f"{rich_heading(f'{EmojiTag.SUCCESS} ZIP Created Successfully!', level=1)}\n"
        f"{summary_table}"
    )
    await rich_edit(message, result_text)

    return zip_filename, message


# ─── External Upload (gofile.io) ──────────────────────────────────────────────

async def upload_to_gofile(callback_query, zip_filename, message):
    """Upload large files to gofile.io and return a download link."""
    import aiohttp
    try:
        from stats_manager import update_stats
        await update_stats(callback_query.from_user.id, "external_uploads")

        timeout = aiohttp.ClientTimeout(total=900, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://api.gofile.io/servers") as resp:
                if resp.status != 200:
                    return await rich_reply(
                        callback_query,
                        f"{EmojiTag.ERROR} <b>Failed to get gofile server.</b>",
                    )
                data = await resp.json()
                server = data.get("data", {}).get("servers", [{}])[0].get("name")

            if not server:
                return await rich_reply(
                    callback_query,
                    f"{EmojiTag.WARNING} <b>No storage available on gofile.io — please try again later.</b>",
                )

            transfer_url = f"https://{server}.gofile.io/uploadFile"

            with open(zip_filename, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("file", f, filename=os.path.basename(zip_filename))
                async with session.post(transfer_url, data=form) as resp:
                    if resp.status != 200:
                        return await rich_reply(
                            callback_query,
                            f"{EmojiTag.ERROR} <b>Upload to gofile.io failed.</b>",
                        )
                    text = await resp.text()

        import json
        try:
            result = json.loads(text)
            link = result["data"]["downloadPage"]
        except Exception:
            start_idx = text.find("https://gofile.io")
            if start_idx == -1:
                return await rich_reply(callback_query, f"{EmojiTag.ERROR} <b>Failed to parse gofile response.</b>")
            end_idx = text.find('"', start_idx)
            link = text[start_idx:end_idx]

        download_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬇️ Download File", url=link, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.DOWNLOAD)],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="home", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.HOME)],
        ])
        await rich_edit(
            message,
            f"{rich_heading(f'{EmojiTag.CLOUD} Uploaded to Cloud Storage', level=1)}\n\n"
            f"<i>File exceeds Telegram 2.00 GB limit. Access your archive via the cloud download link below.</i>",
            reply_markup=download_button,
        )
    except Exception as e:
        print(f"Error uploading to gofile: {e}")
