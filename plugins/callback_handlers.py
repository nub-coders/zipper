import config
from config import collection
from pyrogram import Client, filters, StopTransmission
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.ui_components import home_buttons, back_buttons, pass_button, common_buttons
from tools import Timer, upload_to_gofile, get_queue_status
from stats_manager import update_stats
import os
import shutil
import time
import random
import asyncio
import subprocess
import tempfile


# ─── ZIP Creation Callbacks ──────────────────────────────────────────────────

def _is_busy(user_id):
    """Check if THIS user has a download or upload in progress."""
    return user_id in config.downloading_users or user_id in config.uploading_users


@Client.on_callback_query(filters.regex("no_password"))
async def without_pass(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if _is_busy(user_id):
        reason = "downloading" if user_id in config.downloading_users else "uploading"
        return await callback_query.answer(
            f"⏳ Can't zip now — your file is {reason}. Try after it finishes.",
            show_alert=True,
        )

    await callback_query.edit_message_text(
        "📦 **Creating Regular ZIP**\n\n"
        "• Starting compression process\n"
        "• Please provide a name for your ZIP file"
    )
    user_id = callback_query.from_user.id
    await update_stats(user_id, "zip_without_pass")
    await create_zip(client, callback_query, None)


@Client.on_callback_query(filters.regex("set_password"))
async def with_pass(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if _is_busy(user_id):
        reason = "downloading" if user_id in config.downloading_users else "uploading"
        return await callback_query.answer(
            f"⏳ Can't zip now — your file is {reason}. Try after it finishes.",
            show_alert=True,
        )

    await callback_query.edit_message_text(
        "🔐 **Creating Protected ZIP**\n\n"
        "• Starting secure compression process\n"
        "• Please provide a name for your ZIP file\n"
        "• You'll be asked for a password next"
    )
    user_id = callback_query.from_user.id
    await update_stats(user_id, "zip_with_pass")
    await create_zip(client, callback_query, True)


# ─── Cancel Callback ─────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("cancel_task"))
async def cancel_task(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if (user_id in config.downloading_users or user_id in config.zipping_users
            or user_id in config.uploading_users):
        config.cancel_requested.add(user_id)
        await callback_query.answer("🛑 Cancellation requested for current task…", show_alert=True)
        try:
            await callback_query.edit_message_text(
                "🛑 **Cancellation requested**\n\n"
                "The current operation will be stopped shortly.",
                reply_markup=home_buttons,
            )
        except Exception:
            pass
    else:
        await callback_query.answer("No active task to cancel right now.", show_alert=True)

@Client.on_callback_query(filters.regex("cancel_all"))
async def cancel_all(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Atomically drain all queue items for this user
    removed = 0
    new_queue_items = []
    while not config.download_queue.empty():
        item = config.download_queue.get()
        if item.from_user.id == user_id:
            removed += 1
        else:
            new_queue_items.append(item)
            
    for item in new_queue_items:
        config.download_queue.put(item)

    # Mark user as cancelled so process_queues won't pick up any remaining items
    config.cancel_requested.add(user_id)
    
    # Clean up user state (do this after adding to cancel_requested to prevent races)
    config.user_ids.pop(user_id, None)

    if (user_id in config.downloading_users or user_id in config.zipping_users
            or user_id in config.uploading_users):
        msg_text = f"🛑 **Cancellation requested**\n\nThe active operation and {removed} queued task(s) will be stopped."
    else:
        msg_text = f"✅ Removed {removed} file(s) from the download queue."

    await callback_query.answer("Action processed.", show_alert=True)
    try:
        await callback_query.edit_message_text(msg_text, reply_markup=home_buttons)
    except Exception:
        pass


# ─── Queue / Cancel Callbacks ─────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("cancel_download"))
async def cancel_download(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in config.user_ids:
        # Remove user's items from queue
        new_items = []
        while not config.download_queue.empty():
            item = config.download_queue.get()
            if item.from_user.id != user_id:
                new_items.append(item)
        for item in new_items:
            config.download_queue.put(item)

        config.user_ids.pop(user_id, None)
        await callback_query.edit_message_text("Download canceled.")
    else:
        await callback_query.edit_message_text("No ongoing download to cancel.")


@Client.on_callback_query(filters.regex("bhad"))
async def callback_queue(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    response_text = get_queue_status(user_id)
    await callback_query.answer(response_text, show_alert=True)


# ─── Navigation Callbacks ────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("lang_menu"))
async def callback_lang_menu(client: Client, callback_query: CallbackQuery):
    from tools import get_text
    user_id = callback_query.from_user.id
    lang_text = get_text(collection, user_id, "choose_lang")
    btn_en = get_text(collection, user_id, "lang_btn_en")
    btn_fa = get_text(collection, user_id, "lang_btn_fa")
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_en, callback_data="setlang_en")],
        [InlineKeyboardButton(btn_fa, callback_data="setlang_fa")]
    ])
    await callback_query.edit_message_text(lang_text, reply_markup=markup)



@Client.on_callback_query(filters.regex("help"))
async def callback_help(client: Client, callback_query: CallbackQuery):
    from plugins.basic_commands import help_command

    class _MessageLike:
        """Adapter so help_command can work with callback queries."""
        def __init__(self, cq):
            self.from_user = cq.from_user
            self.edit_message_text = cq.edit_message_text
            self.id = cq.message.id

        async def reply_text(self, text, **kwargs):
            markup = kwargs.get("reply_markup")
            await self.edit_message_text(text, reply_markup=markup)

    await help_command(client, _MessageLike(callback_query))


@Client.on_callback_query(filters.regex("my_files"))
async def callback_my_files(client: Client, callback_query: CallbackQuery):
    from plugins.file_handlers import list_files
    await list_files(client, callback_query)


@Client.on_callback_query(filters.regex("clear"))
async def callback_clear(client: Client, callback_query: CallbackQuery):
    from tools import handle_clear_files
    user_id = callback_query.from_user.id
    text = await handle_clear_files(user_id, back_buttons)
    await callback_query.edit_message_text(text, reply_markup=back_buttons)


@Client.on_callback_query(filters.regex("home"))
async def callback_home(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if not collection.find_one({"user_id": user_id}):
        from tools import store_userr
        store_userr(collection, user_id)

    await callback_query.edit_message_text(
        "Hello! This is the File-to-ZIP bot.\n"
        "Send me any files or direct download link and I will compress them to a zip\n"
        "/help to get more details",
        reply_markup=home_buttons,
    )


@Client.on_callback_query(filters.regex("fzip"))
async def callback_fzip(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if _is_busy(user_id):
        reason = "downloading" if user_id in config.downloading_users else "uploading"
        return await callback_query.answer(
            f"⏳ Can't zip now — your file is {reason}. Try after it finishes.",
            show_alert=True,
        )

    await callback_query.edit_message_text(
        "Would you like to protect your zip file with a secure password?",
        reply_markup=pass_button,
    )


# ─── ZIP Creation + Upload Logic ─────────────────────────────────────────────

async def create_zip(client, callback_query, pass_protect=None):
    from tools import create_zip_file
    user_id = callback_query.from_user.id
    user_dir = f"{config.ggg}/zipper/{user_id}"
    # Set zipping flag for THIS user
    config.zipping_users.add(user_id)

    try:
        zip_filename, message = await create_zip_file(client, callback_query, pass_protect)
    except Exception as e:
        config.zipping_users.discard(user_id)
        await callback_query.message.reply_text(f"Error creating ZIP: {e}")
        return
    finally:
        config.zipping_users.discard(user_id)

    if not zip_filename or not os.path.exists(zip_filename):
        return

    file_size = os.path.getsize(zip_filename)

    # Reuse the single status message for upload progress (no new messages)
    msg = message

    # Set uploading flag for THIS user
    config.uploading_users.add(user_id)
    cancelled = False

    try:
        if file_size <= 2_000_000_000:  # 2 GB Telegram limit
            timer = Timer()
            try:
                await msg.edit_text("⬆️ Upload starting…")
            except Exception:
                pass

            async def progress_bar(current, total, start_time=time.time()):
                # Check for cancellation
                if user_id in config.cancel_requested:
                    config.cancel_requested.discard(user_id)
                    raise StopTransmission()

                if not timer.can_send():
                    return
                pct = current * 100 / total
                elapsed = time.time() - start_time
                speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
                eta = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)

                text = (
                    f"⬆️ **Uploading:** {pct:.2f}%\n"
                    f"Speed: {speed:.2f} MB/s\n"
                    f"Time left: {eta:.2f} seconds\n"
                    f"Size: {current / (1024*1024):.2f} MB / {total / (1024*1024):.2f} MB\n"
                    f"[{bar}]"
                )
                cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel", callback_data="cancel_task")]])
                try:
                    if random.choices([True, False], weights=[1, 999])[0]:
                        await msg.edit_text(text, reply_markup=cancel_markup)
                except Exception:
                    pass

            try:
                await client.send_document(
                    callback_query.message.chat.id,
                    zip_filename,
                    caption="zip by @FILEs_COMPRESSOR_BOT",
                    progress=progress_bar,
                )
                await msg.edit_text(
                    "Uploaded successfully\n\nPlease join @nub_coder_s",
                    reply_markup=home_buttons,
                )
            except StopTransmission:
                cancelled = True
                await msg.edit_text(
                    "❌ **Upload cancelled**\n\nYour upload has been stopped.",
                    reply_markup=home_buttons,
                )
        else:
            await upload_to_gofile(callback_query, zip_filename, message)
    finally:
        config.uploading_users.discard(user_id)
        config.cancel_requested.discard(user_id)



    # Clean up
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
        os.makedirs(user_dir, exist_ok=True)


# ─── Uncompress / Dismiss Callbacks ──────────────────────────────────────────

@Client.on_callback_query(filters.regex("dismiss"))
async def dismiss_callback(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^unzip\|"))
async def uncompress_preview(client: Client, callback_query: CallbackQuery):
    """Step 1: Show the file listing inside the archive before extracting."""
    user_id = callback_query.from_user.id
    data = callback_query.data
    filename_end = data.split("|", 1)[1]
    user_dir = f"{config.ggg}/zipper/{user_id}"

    target_file = None
    if os.path.exists(user_dir):
        for f in os.listdir(user_dir):
            if f.endswith(filename_end):
                target_file = os.path.join(user_dir, f)
                break

    if not target_file or not os.path.exists(target_file):
        return await callback_query.answer("File not found.", show_alert=True)

    await callback_query.edit_message_text(f"🔍 Reading contents of `{os.path.basename(target_file)}`...")

    try:
        out = subprocess.check_output(
            ['7z', 'l', '-slt', '-p""', target_file],
            text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        out = e.output

    # Parse file entries
    entries = []
    current = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("----------"):
            if current:
                entries.append(current)
            current = {}
        elif " = " in line:
            key, _, val = line.partition(" = ")
            current[key.strip()] = val.strip()
    if current:
        entries.append(current)

    is_encrypted = any(e.get("Encrypted") == "+" for e in entries)

    # Build listing text
    file_lines = []
    total_size = 0
    for e in entries:
        path = e.get("Path", "")
        size = e.get("Size", "0")
        attr = e.get("Attributes", "")
        if not path or attr.startswith("D"):   # skip dirs
            continue
        try:
            sz = int(size)
            total_size += sz
            size_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024**2):.2f} MB"
        except Exception:
            size_str = size
        file_lines.append(f"📄 `{path}` — {size_str}")

    if not file_lines:
        file_lines.append("_(No readable file list — may be encrypted or unsupported format)_")

    total_str = (
        f"{total_size / 1024:.1f} KB" if total_size < 1024 * 1024
        else f"{total_size / (1024**2):.2f} MB"
    )

    enc_note = "\n\n🔐 _This archive is **encrypted** — you will be asked for a password._" if is_encrypted else ""
    size_warn = "\n\n⚠️ _Total size exceeds 2 GB — extraction will be blocked._" if total_size > 2 * 1024 * 1024 * 1024 else ""

    listing = "\n".join(file_lines[:30])
    if len(file_lines) > 30:
        listing += f"\n_...and {len(file_lines) - 30} more files_"

    text = (
        f"🗜️ **Archive:** `{os.path.basename(target_file)}`\n"
        f"📦 **Files inside ({len(file_lines)}):** Total ~{total_str}\n\n"
        f"{listing}"
        f"{enc_note}{size_warn}\n\n"
        f"Would you like to uncompress and receive these files?"
    )

    # Confirm callback reuses the same filename_end
    cb_confirm = f"unzip_confirm|{filename_end}"
    if len(cb_confirm.encode("utf-8")) > 64:
        cb_confirm = f"unzip_confirm|{filename_end[-45:]}"

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Proceed", callback_data=cb_confirm),
         InlineKeyboardButton("❌ Dismiss", callback_data="dismiss")]
    ])

    try:
        await callback_query.edit_message_text(text, reply_markup=markup)
    except Exception:
        # message too long — trim
        short_text = (
            f"🗜️ **Archive:** `{os.path.basename(target_file)}`\n"
            f"📦 **{len(file_lines)} file(s)** inside, total ~{total_str}"
            f"{enc_note}{size_warn}\n\n"
            f"Would you like to uncompress and receive these files?"
        )
        await callback_query.edit_message_text(short_text, reply_markup=markup)


@Client.on_callback_query(filters.regex(r"^unzip_confirm\|"))
async def uncompress_callback(client: Client, callback_query: CallbackQuery):
    """Step 2: Actually extract and send the files."""
    user_id = callback_query.from_user.id
    data = callback_query.data
    filename_end = data.split("|", 1)[1]
    user_dir = f"{config.ggg}/zipper/{user_id}"

    target_file = None
    if os.path.exists(user_dir):
        for f in os.listdir(user_dir):
            if f.endswith(filename_end):
                target_file = os.path.join(user_dir, f)
                break

    if not target_file or not os.path.exists(target_file):
        return await callback_query.answer("File not found.", show_alert=True)

    await callback_query.edit_message_text(f"⏳ Preparing to uncompress `{os.path.basename(target_file)}`...")

    try:
        is_encrypted = False
        password = ""
        try:
            out = subprocess.check_output(['7z', 'l', '-slt', '-p""', target_file], text=True, stderr=subprocess.STDOUT)
            if "Encrypted = +" in out:
                is_encrypted = True
            else:
                total_size = 0
                for line in out.splitlines():
                    if line.startswith("Size = "):
                        try:
                            total_size += int(line.split("=")[1].strip())
                        except Exception:
                            pass
                if total_size > 2 * 1024 * 1024 * 1024:
                    return await callback_query.edit_message_text("❌ Uncompressed files exceed 2 GB limit.")
        except subprocess.CalledProcessError as e:
            if "Encrypted = +" in e.output or "Wrong password" in e.output:
                is_encrypted = True
        except Exception:
            pass

        if is_encrypted:
            await callback_query.edit_message_text("🔐 **This archive is encrypted.**\nPlease reply with the password to uncompress it:")
            try:
                get_pass = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
                password = get_pass.text
                status_msg = await callback_query.message.reply_text(f"Uncompressing {os.path.basename(target_file)}...")
            except Exception:
                return await callback_query.message.reply_text("❌ No password provided in time. Cancelled unzip operation.")
        else:
            status_msg = callback_query.message

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                subprocess.check_call(['7z', 'x', f'-o{tmpdir}', f'-p{password}', '-y', target_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                if is_encrypted:
                    return await status_msg.edit_text("❌ Failed to uncompress. It might be an incorrect password or unsupported format.")
                else:
                    return await status_msg.edit_text("❌ Failed to uncompress. Unsupported format or corrupted archive.")

            extracted_files = []
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    extracted_files.append(os.path.join(root, file))

            if not extracted_files:
                return await status_msg.edit_text("❌ No files found after uncompressing.")

            total_extracted_size = sum(os.path.getsize(f) for f in extracted_files)
            if total_extracted_size > 2 * 1024 * 1024 * 1024:
                return await status_msg.edit_text("❌ Uncompressed files exceed 2 GB limit.")

            await status_msg.edit_text(f"⏳ Sending {len(extracted_files)} extracted file(s)...")

            upload_timer = Timer()

            for idx, ext_file in enumerate(extracted_files, 1):
                file_name_only = os.path.basename(ext_file)
                file_size = os.path.getsize(ext_file)

                if file_size > 2 * 1024 * 1024 * 1024:
                    await callback_query.message.reply_text(f"Skipping {file_name_only}: exceeds 2 GB limit.")
                    continue

                upload_start = time.time()

                async def upload_progress(current, total, fname=file_name_only, fidx=idx, start=upload_start):
                    if not upload_timer.can_send() or not total:
                        return
                    pct = current * 100 / total
                    bar_len = 20
                    ticks = int(pct / (100 / bar_len))
                    bar = "█" * ticks + "░" * (bar_len - ticks)
                    elapsed = time.time() - start
                    speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
                    eta = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0
                    text = (
                        f"⬆️ **Uploading file {fidx}/{len(extracted_files)}**\n"
                        f"📄 `{fname}`\n\n"
                        f"📊 Progress: {pct:.1f}%\n"
                        f"⚡ Speed: {speed:.1f} MB/s\n"
                        f"⏱️ ETA: {eta:.0f}s\n"
                        f"📦 {current/(1024*1024):.1f}/{total/(1024*1024):.1f} MB\n"
                        f"[{bar}]"
                    )
                    try:
                        await status_msg.edit_text(text)
                    except Exception:
                        pass

                try:
                    await client.send_document(
                        callback_query.message.chat.id,
                        ext_file,
                        caption=f"Extracted: {file_name_only}",
                        progress=upload_progress,
                    )
                except Exception:
                    await callback_query.message.reply_text(f"Failed to send {file_name_only}")

        await status_msg.edit_text("✅ All files extracted and sent.")
    except Exception as e:
        try:
            await status_msg.edit_text(f"Error during uncompression: {e}")
        except Exception:
            await callback_query.message.reply_text(f"Error during uncompression: {e}")


# ─── Catch-all Callback (must be last) ───────────────────────────────────────

@Client.on_callback_query()
async def callback_query_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "bhad":
        status = get_queue_status(user_id)
        await callback_query.answer()
        await callback_query.edit_message_text(status)