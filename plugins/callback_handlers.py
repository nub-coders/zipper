"""plugins/callback_handlers.py — Callback Query Handlers with Bot API 10.2 & 10.3 Rich UI."""

import asyncio
import os
import random
import shutil
import tempfile
import time

import config
from config import collection
from nuloader_upload import upload_to_nuloader
from plugins.ui_components import (
    back_buttons,
    cancel_markup,
    common_buttons,
    home_buttons,
    lang_markup,
    pass_button,
)
from pyrogram import Client, StopTransmission, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from rate_limiter import extract_limiter
from safe_archive import (
    ArchiveError,
    ArchiveFailed,
    ArchiveTimeout,
    ArchiveTooLarge,
    collect_safe_files,
    extract_archive,
    list_archive,
    looks_encrypted,
)
from stats_manager import update_stats
from tools import Timer, get_queue_status
from user_state import (
    clear_cancel,
    get_busy_reason,
    is_cancel_requested,
    is_user_busy,
    request_cancel,
    set_extracting,
    set_uploading,
    set_zipping,
)
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import (
    rich_answer,
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


# ─── Busy Check Helpers ───────────────────────────────────────────────────────

async def _is_busy(user_id):
    return await is_user_busy(user_id)


async def _busy_reason(user_id):
    return await get_busy_reason(user_id)


# ─── ZIP Creation Callbacks ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^no_password$"))
async def without_pass(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await _is_busy(user_id):
        return await callback_query.answer(
            f"⏳ Can't zip now — your file is {await _busy_reason(user_id)}. Try after it finishes.",
            show_alert=True,
        )

    await rich_edit(
        callback_query,
        f"{rich_heading(f'{EmojiTag.ZIP} Creating Regular ZIP Archive', level=2)}\n\n"
        f"• Starting fast compression process\n"
        f"• Please provide a name for your ZIP file in chat",
        client=client,
    )
    await update_stats(user_id, "zip_without_pass")
    await create_zip(client, callback_query, None)


@Client.on_callback_query(filters.regex(r"^set_password$"))
async def with_pass(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await _is_busy(user_id):
        return await callback_query.answer(
            f"⏳ Can't zip now — your file is {await _busy_reason(user_id)}. Try after it finishes.",
            show_alert=True,
        )

    await rich_edit(
        callback_query,
        f"{rich_heading(f'{EmojiTag.LOCK} Creating Protected ZIP Archive', level=2)}\n\n"
        f"• Starting secure encryption process\n"
        f"• Please provide a name for your ZIP file\n"
        f"• You'll be asked for a password next",
        client=client,
    )
    await update_stats(user_id, "zip_with_pass")
    await create_zip(client, callback_query, True)


# ─── Cancel Callbacks ─────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^cancel_task$"))
async def cancel_task(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    from batch_manager import cancel_user_batch
    await cancel_user_batch(user_id)

    if await is_user_busy(user_id):
        await request_cancel(user_id)
        await callback_query.answer("🛑 Cancellation requested for current task…", show_alert=True)
        try:
            await rich_edit(
                callback_query,
                f"{rich_heading(f'{EmojiTag.CANCEL} Cancellation Requested', level=2)}\n\n"
                f"The active operation will be stopped shortly.",
                reply_markup=None,
                client=client,
            )
        except Exception:
            pass
    else:
        await callback_query.answer("No active task to cancel.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^cancel_all$"))
async def cancel_all(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    from batch_manager import cancel_user_batch
    await cancel_user_batch(user_id)

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

    config.cancel_requested.add(user_id)
    config.user_ids.pop(user_id, None)

    if (user_id in config.downloading_users or user_id in config.zipping_users
            or user_id in config.uploading_users):
        msg_text = (
            f"{rich_heading(f'{EmojiTag.CANCEL} Cancellation In Progress', level=2)}\n\n"
            f"The active operation and <code>{removed}</code> queued task(s) will be stopped."
        )
    else:
        msg_text = (
            f"{rich_heading(f'{EmojiTag.SUCCESS} Queue Cleared', level=2)}\n\n"
            f"Removed <code>{removed}</code> file(s) from the download queue."
        )

    await callback_query.answer("Action processed.", show_alert=True)
    try:
        await rich_edit(callback_query, msg_text, reply_markup=home_buttons, client=client)
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^cancel_download$"))
async def cancel_download(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in config.user_ids:
        new_items = []
        while not config.download_queue.empty():
            item = config.download_queue.get()
            if item.from_user.id != user_id:
                new_items.append(item)
        for item in new_items:
            config.download_queue.put(item)

        config.user_ids.pop(user_id, None)
        await rich_edit(callback_query, f"{EmojiTag.CANCEL} <b>Download cancelled.</b>", reply_markup=home_buttons, client=client)
    else:
        await rich_edit(callback_query, f"{EmojiTag.INFO} <b>No ongoing download to cancel.</b>", reply_markup=home_buttons, client=client)


@Client.on_callback_query(filters.regex(r"^bhad$"))
async def callback_queue(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    response_text = get_queue_status(user_id)
    await rich_edit(callback_query, response_text, reply_markup=home_buttons, client=client)


# ─── Navigation Callbacks ────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^dismiss$"))
async def dismiss_callback(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.message.delete()
    except Exception:
        try:
            await callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


# ─── ZIP Creation + Upload Logic ─────────────────────────────────────────────

async def create_zip(client, callback_query, pass_protect=None):
    from tools import create_zip_file
    user_id = callback_query.from_user.id
    user_dir = f"{config.ggg}/zipper/{user_id}"

    if not await set_zipping(user_id, True):
        await callback_query.answer("Already zipping. Please wait.", show_alert=True)
        return

    try:
        zip_filename, message = await create_zip_file(client, callback_query, pass_protect)
    except Exception as e:
        await set_zipping(user_id, False)
        await rich_reply(callback_query, f"{EmojiTag.ERROR} <b>Error creating ZIP:</b> <code>{rich_esc(e)}</code>")
        return
    finally:
        await set_zipping(user_id, False)

    if not zip_filename or not os.path.exists(zip_filename):
        return

    file_size = os.path.getsize(zip_filename)
    msg = message

    if not await set_uploading(user_id, True):
        await set_zipping(user_id, False)
        await rich_reply(callback_query, f"{EmojiTag.WARNING} <b>Already uploading. Please wait.</b>")
        return

    cancelled = False
    try:
        if file_size <= 2_000_000_000:  # 2 GB Telegram limit
            timer = Timer()
            try:
                await rich_edit(msg, f"{EmojiTag.UPLOAD} <b>Preparing upload to Telegram…</b>", reply_markup=cancel_markup, client=client)
            except Exception:
                pass

            start_time = time.time()

            async def progress_bar(current, total):
                if await is_cancel_requested(user_id):
                    await clear_cancel(user_id)
                    raise StopTransmission()

                if not timer.can_send() or not total:
                    return

                pct = current * 100 / total
                elapsed = time.time() - start_time
                speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
                eta = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

                bar_len = 16
                ticks = int(pct / (100 / bar_len))
                bar = "█" * ticks + "░" * (bar_len - ticks)

                text = (
                    f"{rich_heading(f'{EmojiTag.UPLOAD} Uploading Archive to Telegram', level=2)}\n"
                    f"<b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
                    + rich_kv_table([
                        ("Transferred", f"<code>{current / (1024*1024):.2f} MB / {total / (1024*1024):.2f} MB</code>"),
                        ("Speed", f"<code>{speed:.2f} MB/s</code>"),
                        ("ETA", f"<code>{eta:.1f}s</code>"),
                    ])
                )
                try:
                    await rich_edit(msg, text, reply_markup=cancel_markup, client=client)
                except Exception:
                    pass

            try:
                await client.send_document(
                    callback_query.message.chat.id,
                    zip_filename,
                    caption=f"📦 Compressed archive created by @FILEs_COMPRESSOR_BOT",
                    progress=progress_bar,
                )
                await rich_edit(
                    msg,
                    f"{rich_heading(f'{EmojiTag.SUCCESS} Archive Uploaded Successfully', level=1)}\n\n"
                    f"<i>Your compressed archive has been sent above.<br>Join our support community: @nub_coder_s</i>",
                    reply_markup=home_buttons,
                    client=client,
                )
            except StopTransmission:
                cancelled = True
                await rich_edit(
                    msg,
                    f"{rich_heading(f'{EmojiTag.CANCEL} Upload Cancelled', level=2)}\n\nYour upload was cancelled.",
                    reply_markup=home_buttons,
                    client=client,
                )
        else:
            # File exceeds Telegram's 2.00 GB limit: present interactive upload method options
            def _fmt_size(size_bytes):
                for unit in ("B", "KB", "MB", "GB"):
                    if size_bytes < 1024:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024
                return f"{size_bytes:.2f} TB"

            choice_table = rich_kv_table([
                ("Archive Name", f"<code>{rich_esc(os.path.basename(zip_filename))}</code>"),
                ("Archive Size", f"<code>{_fmt_size(file_size)}</code>"),
                ("Telegram Limit", "<code>2.00 GB</code>"),
            ], headers=["Archive Info", "Value"])

            choice_text = (
                f"{rich_heading(f'{EmojiTag.CLOUD} Cloud Upload Required', level=1)}\n"
                f"{choice_table}\n\n"
                f"<i>Telegram restricts bot uploads to 2.00 GB.<br>"
                f"Please choose your preferred cloud hosting & retention option:</i>"
            )

            upload_buttons = [
                [
                    InlineKeyboardButton(
                        "🌐 NuLoader: 7 Days (Unlimited)",
                        callback_data="upopt_days_7",
                        style=ButtonStyle.PRIMARY,
                        icon_custom_emoji_id=Emoji.CLOUD,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⚡ NuLoader: 5 Downloads Max",
                        callback_data="upopt_downloads_5",
                        style=ButtonStyle.SUCCESS,
                        icon_custom_emoji_id=Emoji.PING,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "☁️ GoFile.io Mirror",
                        callback_data="upopt_gofile",
                        style=ButtonStyle.DEFAULT,
                        icon_custom_emoji_id=Emoji.LINK,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🛑 Cancel",
                        callback_data="cancel_task",
                        style=ButtonStyle.DANGER,
                        icon_custom_emoji_id=Emoji.CANCEL,
                    )
                ],
            ]

            upload_choice_markup = InlineKeyboardMarkup(upload_buttons)

            try:
                await rich_edit(msg, choice_text, reply_markup=upload_choice_markup, client=client)
            except Exception:
                pass

            try:
                cb = await client.listen.CallbackQuery(
                    filters.user(user_id) & filters.regex(r"^(upopt_|cancel_task)"),
                    timeout=180,
                )
                try:
                    await cb.answer()
                except Exception:
                    pass

                choice = cb.data
                if choice == "cancel_task":
                    await rich_edit(
                        msg,
                        f"{rich_heading(f'{EmojiTag.CANCEL} Upload Cancelled', level=2)}\n\nYour upload was cancelled.",
                        reply_markup=home_buttons,
                        client=client,
                    )
                    return
                elif choice == "upopt_downloads_5":
                    await upload_to_nuloader(callback_query, zip_filename, msg, expiry_mode="downloads_5")
                elif choice == "upopt_gofile":
                    from tools import upload_to_gofile
                    await upload_to_gofile(callback_query, zip_filename, msg)
                else:  # upopt_days_7
                    await upload_to_nuloader(callback_query, zip_filename, msg, expiry_mode="days_7")

            except asyncio.TimeoutError:
                # Timeout fallback: proceed with default configured mode
                default_mode = getattr(config, "NULOADER_EXPIRY_MODE", "days_7") or "days_7"
                await upload_to_nuloader(callback_query, zip_filename, msg, expiry_mode=default_mode)
    finally:
        await set_uploading(user_id, False)
        await clear_cancel(user_id)

        try:
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir, ignore_errors=True)
                os.makedirs(user_dir, exist_ok=True)
        except OSError as exc:
            print(f"Failed to clean {user_dir}: {exc}")


# ─── Uncompress Callbacks ────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^unzip\|"))
async def uncompress_preview(client: Client, callback_query: CallbackQuery):
    """Step 1: Show the rich file listing inside the archive before extracting."""
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
        return await callback_query.answer("File not found in storage.", show_alert=True)

    await rich_edit(
        callback_query,
        f"{EmojiTag.LOADING} <b>Inspecting archive contents:</b> <code>{rich_esc(os.path.basename(target_file))}</code>…",
        client=client,
    )

    try:
        listing, exited_ok = await list_archive(target_file)
    except ArchiveTimeout:
        return await rich_edit(callback_query, f"{EmojiTag.ERROR} <b>Archive listing timed out.</b>", client=client)
    except ArchiveFailed as e:
        return await rich_edit(callback_query, f"{EmojiTag.ERROR} <b>Failed to list archive:</b> <code>{rich_esc(e)}</code>", client=client)

    is_encrypted = looks_encrypted(listing)

    entries = []
    current = {}
    for line in listing.splitlines():
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

    table_rows = []
    total_size = 0
    for idx, e in enumerate(entries):
        path = e.get("Path", "")
        size = e.get("Size", "0")
        attr = e.get("Attributes", "")
        if not path or attr.startswith("D"):
            continue
        try:
            sz = int(size)
            total_size += sz
            size_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024**2):.2f} MB"
        except Exception:
            size_str = size

        if len(table_rows) < 15:
            table_rows.append((
                f"<code>{len(table_rows)+1}</code>",
                f"<code>{rich_esc(path[:20] + '...' if len(path) > 23 else path)}</code>",
                f"<code>{size_str}</code>",
            ))

    total_str = (
        f"{total_size / 1024:.1f} KB" if total_size < 1024 * 1024
        else f"{total_size / (1024**2):.2f} MB"
    )

    enc_status = "🔐 Encrypted (Password Required)" if is_encrypted else "🔓 Unencrypted"

    metadata_table = rich_kv_table([
        ("Archive Name", f"<code>{rich_esc(os.path.basename(target_file))}</code>"),
        ("Total Files", f"<code>{len(entries)}</code>"),
        ("Total Size", f"<code>{total_str}</code>"),
        ("Encryption", f"<code>{enc_status}</code>"),
    ], headers=["Archive Info", "Details"])

    files_inside_table = rich_table(["#", "Path", "Size"], table_rows) if table_rows else ""

    cb_confirm = f"unzip_confirm|{filename_end}"
    if len(cb_confirm.encode("utf-8")) > 64:
        cb_confirm = f"unzip_confirm|{filename_end[-45:]}"

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Extract Files", callback_data=cb_confirm, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.EXTRACT),
            InlineKeyboardButton("❌ Dismiss", callback_data="dismiss", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
        ]
    ])

    text = (
        f"{rich_heading(f'{EmojiTag.EXTRACT} Archive Inspection', level=1)}\n"
        f"{metadata_table}\n\n"
        f"<b>📋 Contained Files (Preview):</b>\n"
        f"{files_inside_table}\n\n"
        f"<i>Would you like to extract and receive these files?</i>"
    )

    await rich_edit(callback_query, text, reply_markup=markup, client=client)


@Client.on_callback_query(filters.regex(r"^unzip_confirm\|"))
async def uncompress_callback(client: Client, callback_query: CallbackQuery):
    """Step 2: Extract and send the files with rich status tracking."""
    user_id = callback_query.from_user.id

    if not extract_limiter.is_allowed(user_id):
        return await callback_query.answer(
            "⏳ Too many extraction requests. Please wait before trying again.",
            show_alert=True,
        )

    if await _is_busy(user_id):
        return await callback_query.answer(
            f"⏳ Can't uncompress now — your file is {await _busy_reason(user_id)}.",
            show_alert=True,
        )

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

    if not await set_extracting(user_id, True):
        return await callback_query.answer("Already extracting. Please wait.", show_alert=True)

    try:
        await rich_edit(
            callback_query,
            f"{EmojiTag.LOADING} <b>Extracting archive:</b> <code>{rich_esc(os.path.basename(target_file))}</code>…",
            client=client,
        )

        password = ""
        try:
            listing, _ = await list_archive(target_file)
            is_encrypted = looks_encrypted(listing)
        except (ArchiveTimeout, ArchiveFailed) as e:
            return await rich_edit(callback_query, f"{EmojiTag.ERROR} <b>Failed to inspect archive:</b> <code>{rich_esc(e)}</code>", client=client)

        if is_encrypted:
            await rich_edit(
                callback_query,
                f"{EmojiTag.LOCK} <b>Archive is Password Protected</b>\n\nPlease reply with the password to extract:",
                client=client,
            )
            try:
                get_pass = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
                password = get_pass.text
                status_msg = await rich_reply(
                    callback_query.message,
                    f"{EmojiTag.LOADING} <b>Uncompressing</b> <code>{rich_esc(os.path.basename(target_file))}</code>…",
                )
            except Exception:
                return await rich_reply(callback_query.message, f"{EmojiTag.CANCEL} <b>No password provided in time. Operation cancelled.</b>")
        else:
            status_msg = callback_query.message

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await extract_archive(
                    target_file,
                    tmpdir,
                    password=password,
                    max_bytes=config.MAX_EXTRACT_BYTES,
                    max_entries=config.MAX_EXTRACT_ENTRIES,
                    timeout=config.MAX_EXTRACT_SECONDS,
                )
        except ArchiveTooLarge as e:
            return await rich_edit(status_msg, f"{EmojiTag.ERROR} <b>{rich_esc(e)}</b>", client=client)
        except ArchiveTimeout:
            return await rich_edit(status_msg, f"{EmojiTag.ERROR} <b>Extraction timed out.</b>", client=client)
        except ArchiveFailed as e:
            msg_fail = "Incorrect password or unsupported archive format." if is_encrypted else str(e)
            return await rich_edit(status_msg, f"{EmojiTag.ERROR} <b>Failed to extract:</b> <code>{rich_esc(msg_fail)}</code>", client=client)

        if not result.files:
            return await rich_edit(status_msg, f"{EmojiTag.ERROR} <b>No extractable files found in archive.</b>", client=client)

        await rich_edit(status_msg, f"{EmojiTag.UPLOAD} <b>Sending {len(result.files)} extracted file(s)…</b>", client=client)

        upload_timer = Timer()

        for idx, ext_file in enumerate(result.files, 1):
            file_name_only = os.path.basename(ext_file)
            file_size = os.path.getsize(ext_file)

            if file_size > config.MAX_EXTRACT_BYTES:
                await rich_reply(callback_query.message, f"{EmojiTag.WARNING} Skipping <code>{rich_esc(file_name_only)}</code> (exceeds size limit).")
                continue

            upload_start = time.time()

            async def upload_progress(current, total, fname=file_name_only, fidx=idx, start=upload_start):
                if await is_cancel_requested(user_id):
                    await clear_cancel(user_id)
                    return
                if not upload_timer.can_send() or not total:
                    return
                pct = current * 100 / total
                bar_len = 16
                ticks = int(pct / (100 / bar_len))
                bar = "█" * ticks + "░" * (bar_len - ticks)
                elapsed = time.time() - start
                speed = current / (elapsed * 1024 * 1024) if elapsed > 0 else 0
                eta = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0
                text = (
                    f"{rich_heading(f'{EmojiTag.UPLOAD} Sending Extracted File ({fidx}/{len(result.files)})', level=2)}\n"
                    f"<b>File:</b> <code>{rich_esc(fname)}</code>\n"
                    f"<b>Progress:</b> <code>[{bar}] {pct:.1f}%</code>\n\n"
                    + rich_kv_table([
                        ("Size", f"<code>{current/(1024*1024):.1f} / {total/(1024*1024):.1f} MB</code>"),
                        ("Speed", f"<code>{speed:.2f} MB/s</code>"),
                        ("ETA", f"<code>{eta:.0f}s</code>"),
                    ])
                )
                try:
                    await rich_edit(status_msg, text, client=client)
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
                await rich_reply(callback_query.message, f"{EmojiTag.ERROR} Failed to send <code>{rich_esc(file_name_only)}</code>")

        await rich_edit(
            status_msg,
            f"{rich_heading(f'{EmojiTag.SUCCESS} Extraction Complete', level=1)}\n\n"
            f"<i>All files extracted and uploaded to chat successfully.</i>",
            reply_markup=home_buttons,
            client=client,
        )
    finally:
        await set_extracting(user_id, False)