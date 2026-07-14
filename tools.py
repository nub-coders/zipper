import shutil
import subprocess
import requests
import aiohttp
import os
import time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram import Client, filters


# ─── Channel Membership Check ────────────────────────────────────────────────

from pyrogram.errors import UserNotParticipant

async def is_user_on_chat(client: Client, user_id: int) -> bool:
    """Return True if user is a member of required channels; fallback to True if checks fail.

    We check membership in @nub_coders and @nub_coder_s. If the API call fails (e.g., bot not admin),
    we allow access to avoid blocking legit users.
    """
    try:
        for chan in ("nub_coders", "nub_coder_s"):
            try:
                member = await client.get_chat_member(chan, user_id)
                if member.status in ("left", "kicked", "banned"):
                    return False
            except UserNotParticipant:
                return False
            except Exception:
                # E.g. bot not admin, ChatAdminRequired, or PeerIdInvalid
                continue
        return True
    except Exception:
        return True


# ─── Admin Utilities ──────────────────────────────────────────────────────────

def _get_admin_file_path():
    """Return the absolute path to admin.txt."""
    return os.path.join(os.getcwd(), "admin.txt")


def get_admin_ids():
    """Get list of admin IDs from admin.txt."""
    admin_file = _get_admin_file_path()
    if os.path.exists(admin_file):
        with open(admin_file, "r") as f:
            return [int(line.strip()) for line in f if line.strip()]
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



def store_userr(collection, user_id):
    """Store user with timestamp set 6 hours in the past (unverified state)."""
    timestamp = int(time.time()) - 21600
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "timestamp": timestamp}},
        upsert=True,
    )


def get_user_status(collection, user_id):
    """Get user verification status and storage / file-size limits.

    Returns:
        (is_verified, max_storage_bytes, max_file_size_bytes)
    """
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if not user_data:
        # Auto-register the user so they exist in DB
        store_user(collection, user_id)

    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_diff = current_time - stored_time

        if time_diff < 21600:  # Verified / elite user (within 6 h)
            return True, int(4.5 * 1024**3), 2 * 1024**3  # 4.5 GB, 2 GB

    return False, 2 * 1024**3, 2 * 1024**3  # 2 GB, 2 GB


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
        upsert=True
    )


def get_text(collection, user_id, text_key):
    """Fetch a translated string based on the user's language."""
    from i18n import TEXTS
    lang = get_user_lang(collection, user_id)
    if lang not in TEXTS:
        lang = "en"
    return TEXTS[lang].get(text_key, TEXTS["en"].get(text_key, text_key))


# ─── File / Directory Utilities ───────────────────────────────────────────────

def is_compressed(file_path):
    """Check if a file is a compressed archive using the 'file' and '7z' commands."""
    if not os.path.exists(file_path):
        return False
    try:
        out = subprocess.check_output(['file', '-b', file_path], text=True, stderr=subprocess.STDOUT).lower()
        if "symmetric key encrypted" in out:
            return True
        if any(x in out for x in ['zip', '7-zip', 'bzip2', 'gzip', 'xz', 'tar', 'rar']):
            return True
    except Exception:
        pass
        
    try:
        out_7z = subprocess.check_output(['7z', 'l', '-slt', '-p""', file_path], stderr=subprocess.STDOUT, text=True)
        if "Encrypted = +" in out_7z or "Wrong password" in out_7z:
            return True
    except subprocess.CalledProcessError as e:
        if "Encrypted = +" in e.output or "Wrong password" in e.output:
            return True
    except Exception:
        pass

    return False

def get_file_size_info(user_dir, max_storage):
    """Return (total_size, remaining_storage, file_list) for a user directory."""
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
        return 0, max_storage, []

    files = os.listdir(user_dir)
    total_size = sum(os.path.getsize(os.path.join(user_dir, f)) for f in files)
    remaining = max_storage - total_size
    return total_size, remaining, files


def cleanup_user_directory(user_dir):
    """Remove all files in user directory and recreate it."""
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
    os.makedirs(user_dir, exist_ok=True)


async def handle_clear_files(user_id, reply_markup=None):
    """Handle clearing all files for a user. Returns a status message string."""
    user_path = os.path.join("zipper", str(user_id))
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
        os.makedirs(user_path, exist_ok=True)
        return "All files and directories in your directory have been removed."
    return "Your directory does not exist."


# ─── Timer (progress bar throttle) ───────────────────────────────────────────

class Timer:
    """Simple timer to throttle progress-bar edits."""

    def __init__(self, time_between=2):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        now = time.time()
        if now > self.start_time + self.time_between:
            self.start_time = now
            return True
        return False


# ─── Queue Status ─────────────────────────────────────────────────────────────

def get_queue_status(user_id):
    """Build a human-readable queue-status string from the local queue."""
    import config

    pending_tasks = list(config.download_queue.queue)
    active_users = len(config.downloading_users | config.zipping_users | config.uploading_users)
    active_task_users = config.downloading_users | config.zipping_users | config.uploading_users

    queue_size = len(pending_tasks)

    lines = []
    if active_users > 0:
        lines.append(f"🔄 **Active tasks:** {active_users} user(s)")
    else:
        lines.append("✅ **No active tasks**")

    lines.append("")
    lines.append(f"📋 **Queue:** {queue_size} task(s)")

    user_task_counts = {}
    for t in pending_tasks:
        uid = t.from_user.id
        user_task_counts[uid] = user_task_counts.get(uid, 0) + 1

    if user_task_counts:
        lines.append("")
        for uid, cnt in user_task_counts.items():
            lines.append(f"  {uid}: {cnt} task(s)")

    if user_id in active_task_users:
        lines.append("\n🎯 **Your task is currently active!**")
    elif user_id in user_task_counts:
        lines.append(f"\n⏳ **Your queued files:** {user_task_counts[user_id]}")
    else:
        lines.append("\nℹ️ You have no files in queue")

    return "\n".join(lines)


# ─── Broadcast ────────────────────────────────────────────────────────────────

# ─── ZIP Creation ─────────────────────────────────────────────────────────────

async def create_zip_file(client, callback_query, pass_protect=None):
    """Interactively create a ZIP file from the user's uploaded files."""
    user_id = callback_query.from_user.id

    try:
        await client.send_message(user_id, "Provide me a suitable filename for the zip file")
        response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        password = ""
        if pass_protect:
            await client.send_message(user_id, "Please type your password below.")
            get_pass = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
    except Exception as e:
        await callback_query.message.reply_text(str(e))
        return None, None

    file_name = response.text
    if file_name.startswith("/") or file_name.startswith("http"):
        return None, None

    # Check channel membership
    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders")],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s")],
        ])
        await callback_query.message.reply_text(
            "You need to join both @nub_coders and @nub_coder_s channels to use this bot.\n\nClick below to Join!",
            reply_markup=button,
        )
        return None, None

    import config
    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = os.listdir(user_dir) if os.path.exists(user_dir) else []

    if not files:
        from plugins.ui_components import back_buttons
        await callback_query.message.reply_text(
            "You don't have files to zip\nSend your files first",
            reply_markup=back_buttons,
        )
        return None, None

    if not file_name.endswith(".zip"):
        file_name = f"{file_name}.zip"

    zip_filename = os.path.join(user_dir, file_name)

    # Calculate total size of original files before compression
    original_size = sum(
        os.path.getsize(os.path.join(user_dir, fn))
        for fn in files
        if os.path.isfile(os.path.join(user_dir, fn))
    )

    try:
        message = await callback_query.message.edit_text("Compressing files to zip, please wait…")
    except Exception:
        message = await callback_query.message.reply_text("Compressing files to zip, please wait…")

    import zipfile
    import pyminizip

    def _fmt(size_bytes):
        """Human-readable file size."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    try:
        if pass_protect and password:
            # Level 4 = faster compression to prevent bot freezing
            file_paths = [os.path.join(user_dir, fn) for fn in files]
            prefixes = [""] * len(files)
            pyminizip.compress_multiple(file_paths, prefixes, zip_filename, password, 4)
        else:
            # ZIP_DEFLATED is much faster than LZMA and won't freeze the bot
            with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as zipf:
                for i, fn in enumerate(files, 1):
                    zipf.write(os.path.join(user_dir, fn), fn)
                    try:
                        await message.edit_text(f"Adding {fn} to ZIP… ({i}/{len(files)})")
                    except Exception:
                        pass
    except Exception as e:
        await message.edit_text(f"Error creating ZIP: {e}")
        return None, message

    # Report compression results
    compressed_size = os.path.getsize(zip_filename) if os.path.exists(zip_filename) else 0
    savings_pct = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    lock_icon = "🔐 " if pass_protect and password else ""

    result_text = (
        f"✅ {lock_icon}**ZIP created successfully!**\n\n"
        f"📂 Original size:   `{_fmt(original_size)}`\n"
        f"📦 Compressed size: `{_fmt(compressed_size)}`\n"
        f"💾 Space saved:     `{savings_pct:.1f}%`"
    )
    await message.edit_text(result_text)

    return zip_filename, message


# ─── External Upload (gofile.io) ──────────────────────────────────────────────

async def upload_to_gofile(callback_query, zip_filename, message):
    """Upload large files to gofile.io and return a download link."""
    try:
        from stats_manager import update_stats
        await update_stats(callback_query.from_user.id, "external_uploads")

        resp = requests.get("https://api.gofile.io/servers")
        server = resp.json()["data"]["servers"][0]["name"]

        if not server:
            return await callback_query.message.reply_text(
                "No storage available on gofile.io — please try again later."
            )

        transfer_url = f"https://{server}.gofile.io/uploadFile"
        proc = subprocess.Popen(
            ["curl", "-F", f"file=@{zip_filename}", transfer_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        line = ""
        for line in proc.stdout:
            line = line.strip()

        start_idx = line.find("https://gofile.io")
        end_idx = line.find('"', start_idx)
        link = line[start_idx:end_idx]

        download_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Download File", url=link)]]
        )
        await message.edit_text(
            "Not able to upload files more than 2 GB here\nSo I provided this download link:",
            reply_markup=download_button,
        )
    except Exception as e:
        print(f"Error uploading to gofile: {e}")
