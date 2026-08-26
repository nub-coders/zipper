import config
import os
import asyncio
import time
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import (
    Message,
    ReplyParameters,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from tools import is_admin
from config import collection
from rate_limiter import (
    broadcast_semaphore,
    allow_broadcast,
    wait_broadcast_slot,
    broadcast_state_lock,
)


@Client.on_message(filters.private & filters.command("ping"))
async def ping_handler(client: Client, message: Message):
    import config as cfg
    start = time.time()
    reply = await message.reply_text("🏓 Pong!", reply_parameters=ReplyParameters(message_id=message.id))
    latency = (time.time() - start) * 1000

    # Calculate uptime
    uptime_secs = int(time.time() - cfg.START_TIME)
    d, rem = divmod(uptime_secs, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    uptime_str = (
        (f"{d}d " if d else "") +
        (f"{h}h " if h else "") +
        (f"{m}m " if m else "") +
        f"{s}s"
    )

    await reply.edit_text(
        f"🏓 **Pong!**\n"
        f"⚡ Latency: `{latency:.2f} ms`\n"
        f"🕐 Uptime: `{uptime_str}`"
    )


@Client.on_message(filters.private & filters.command("skip"))
async def skip_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await message.reply_text(
            "Admin command received. Skipping the task…",
            reply_parameters=ReplyParameters(message_id=message.id),
        )


# ─── Broadcast State ────────────────────────────────────────────────────────
#
# Ported from nub-music-bot's broadcast: a single global payload plus an
# interactive settings menu, with all sends gated by a token-bucket rate
# limiter and a semaphore so two admins cannot double-spend Telegram's global
# message budget. Chat-type toggles are intentionally omitted (zipper is
# private-chat only); an include/exclude user-ID list replaces them.

# Protected by rate_limiter.broadcast_state_lock().
_broadcast_state = {
    "payload": None,        # Message object to broadcast
    "include_users": set(),  # Explicit allowlist of user IDs (empty = everyone)
    "exclude_users": set(),  # User IDs to skip
    "forward_mode": False,   # Forward instead of copy
}

# Admin -> (mode, expires_at). Deliberately NOT config.user_ids, which tracks
# users with queued downloads and is read by /status and the cancel callbacks.
_bcast_input_mode: dict[int, tuple[str, float]] = {}

_INPUT_MODE_TTL = 300.0  # seconds an "send me IDs" prompt stays armed


def _set_input_mode(user_id: int, mode: str) -> None:
    _bcast_input_mode[user_id] = (mode, time.time() + _INPUT_MODE_TTL)


def _get_input_mode(user_id: int) -> str | None:
    entry = _bcast_input_mode.get(user_id)
    if not entry:
        return None
    mode, expires_at = entry
    if time.time() > expires_at:
        _bcast_input_mode.pop(user_id, None)
        return None
    return mode


def _clear_input_mode(user_id: int) -> None:
    _bcast_input_mode.pop(user_id, None)


async def _reset_broadcast_state():
    """Clear broadcast state in place (callers may hold a reference)."""
    async with broadcast_state_lock():
        _broadcast_state["payload"] = None
        _broadcast_state["include_users"].clear()
        _broadcast_state["exclude_users"].clear()
        _broadcast_state["forward_mode"] = False


# ─── Broadcast Settings UI ──────────────────────────────────────────────────

async def _show_broadcast_settings(client: Client, target):
    """Render the broadcast settings menu.

    `target` may be a Message (replies) or a CallbackQuery (edits in place).
    """
    async with broadcast_state_lock():
        include_count = len(_broadcast_state["include_users"])
        exclude_count = len(_broadcast_state["exclude_users"])
        forward = _broadcast_state["forward_mode"]
        has_payload = _broadcast_state["payload"] is not None

    text = (
        f"📢 **Broadcast Settings**\n\n"
        f"📝 Message: {'✅ Set' if has_payload else '❌ Not set'}\n"
        f"👥 Include list: `{include_count}` user(s)"
        f"{' (allowlist active)' if include_count else ''}\n"
        f"🚫 Exclude list: `{exclude_count}` user(s)\n"
        f"↗️ Forward mode: {'✅ ON' if forward else '❌ OFF'}\n\n"
        f"{'' if has_payload else 'Reply to a message with /broadcast to set the content.'}"
    )

    btns = [
        [InlineKeyboardButton("➕ Add Include", callback_data="bcast_add_include"),
         InlineKeyboardButton("➖ Add Exclude", callback_data="bcast_add_exclude")],
        [InlineKeyboardButton("📋 View Include", callback_data="bcast_view_include"),
         InlineKeyboardButton("📋 View Exclude", callback_data="bcast_view_exclude")],
        [InlineKeyboardButton("🗑️ Clear Include", callback_data="bcast_clear_include"),
         InlineKeyboardButton("🗑️ Clear Exclude", callback_data="bcast_clear_exclude")],
        [InlineKeyboardButton(f"{'✅' if forward else '❌'} Forward Mode", callback_data="bcast_toggle_forward")],
        [InlineKeyboardButton("🚀 START BROADCAST", callback_data="bcast_start")],
        [InlineKeyboardButton("✖️ Close", callback_data="bcast_close")],
    ]
    markup = InlineKeyboardMarkup(btns)

    if isinstance(target, CallbackQuery):
        try:
            await target.edit_message_text(text, reply_markup=markup)
        except Exception:
            pass
    else:
        await target.reply_text(
            text,
            reply_markup=markup,
            reply_parameters=ReplyParameters(message_id=target.id),
        )


async def _arm_broadcast(message: Message, forward: bool):
    """Store the replied-to message as the broadcast payload."""
    async with broadcast_state_lock():
        _broadcast_state["payload"] = message.reply_to_message
        _broadcast_state["forward_mode"] = forward
        _broadcast_state["include_users"].clear()
        _broadcast_state["exclude_users"].clear()


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_command_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if message.reply_to_message:
        await _arm_broadcast(message, forward=False)

    await _show_broadcast_settings(client, message)


@Client.on_message(filters.private & filters.command("fbroadcast"))
async def fbroadcast_command_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to the message you want to forward-broadcast.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    await _arm_broadcast(message, forward=True)
    await _show_broadcast_settings(client, message)


# ─── Callback Handlers for Broadcast Settings ───────────────────────────────

_ID_PROMPT = (
    "Send the user IDs to add to the **{list_name}** list.\n\n"
    "Space or comma separated, e.g. `123456 789012`\n"
    "You can also reply to a forwarded message from that user.\n\n"
    "This prompt expires in 5 minutes."
)


@Client.on_callback_query(filters.regex(r"^bcast_add_include$"))
async def bcast_add_include(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    _set_input_mode(callback_query.from_user.id, "include")
    await callback_query.edit_message_text(
        _ID_PROMPT.format(list_name="include"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="bcast_back")]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^bcast_add_exclude$"))
async def bcast_add_exclude(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    _set_input_mode(callback_query.from_user.id, "exclude")
    await callback_query.edit_message_text(
        _ID_PROMPT.format(list_name="exclude"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="bcast_back")]
        ]),
    )


async def _answer_with_list(callback_query: CallbackQuery, key: str, label: str):
    async with broadcast_state_lock():
        users = sorted(_broadcast_state[key])

    if not users:
        text = f"{label} list is empty."
    else:
        text = f"{label} list ({len(users)}):\n" + ", ".join(str(u) for u in users)

    # Telegram alerts cap at 200 chars.
    if len(text) > 200:
        text = text[:197] + "..."
    await callback_query.answer(text, show_alert=True)


@Client.on_callback_query(filters.regex(r"^bcast_view_include$"))
async def bcast_view_include(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)
    await _answer_with_list(callback_query, "include_users", "Include")


@Client.on_callback_query(filters.regex(r"^bcast_view_exclude$"))
async def bcast_view_exclude(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)
    await _answer_with_list(callback_query, "exclude_users", "Exclude")


@Client.on_callback_query(filters.regex(r"^bcast_clear_include$"))
async def bcast_clear_include(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        _broadcast_state["include_users"].clear()
    await callback_query.answer("Include list cleared.")
    await _show_broadcast_settings(client, callback_query)


@Client.on_callback_query(filters.regex(r"^bcast_clear_exclude$"))
async def bcast_clear_exclude(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        _broadcast_state["exclude_users"].clear()
    await callback_query.answer("Exclude list cleared.")
    await _show_broadcast_settings(client, callback_query)


@Client.on_callback_query(filters.regex(r"^bcast_toggle_forward$"))
async def bcast_toggle_forward(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        _broadcast_state["forward_mode"] = not _broadcast_state["forward_mode"]
        forward = _broadcast_state["forward_mode"]

    await callback_query.answer(f"Forward mode: {'ON' if forward else 'OFF'}")
    await _show_broadcast_settings(client, callback_query)


def _fetch_stored_user_ids() -> list[int]:
    """Blocking pymongo read — call via asyncio.to_thread."""
    return [
        u["user_id"]
        for u in collection.find({}, {"user_id": 1})
        if isinstance(u.get("user_id"), int)
    ]


@Client.on_callback_query(filters.regex(r"^bcast_start$"))
async def bcast_start(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        payload = _broadcast_state["payload"]
        include = set(_broadcast_state["include_users"])
        exclude = set(_broadcast_state["exclude_users"])
        forward = _broadcast_state["forward_mode"]

    if payload is None:
        return await callback_query.answer(
            "No message set. Reply to a message with /broadcast first.", show_alert=True
        )

    # Race-free single-broadcast guard: acquire or bail, never queue.
    sem = broadcast_semaphore()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=0.01)
    except asyncio.TimeoutError:
        return await callback_query.answer("Another broadcast is already running.", show_alert=True)

    try:
        if not await allow_broadcast():
            return await callback_query.answer("Rate limited, try again shortly.", show_alert=True)

        stored_users = await asyncio.to_thread(_fetch_stored_user_ids)
        if not stored_users:
            return await callback_query.answer("No users in database.", show_alert=True)

        # A non-empty include list acts as an allowlist; otherwise everyone
        # except the exclude list.
        if include:
            target_users = [u for u in stored_users if u in include]
        else:
            target_users = [u for u in stored_users if u not in exclude]

        if not target_users:
            return await callback_query.answer("No targets left after filtering.", show_alert=True)

        total = len(target_users)
        await callback_query.edit_message_text(
            f"🚀 Broadcasting to `{total}` user(s)…\n"
            f"Forward mode: {'ON' if forward else 'OFF'}"
        )

        sent = 0
        failed = 0
        last_edit = time.time()

        for uid in target_users:
            # Global pacing: one token per outgoing message.
            await wait_broadcast_slot(max_wait=1.0)

            try:
                if forward:
                    await payload.forward(uid)
                else:
                    await payload.copy(uid)
                sent += 1
            except FloodWait as e:
                # Respect Telegram's backoff, then retry this user once.
                await asyncio.sleep(int(getattr(e, "value", 5)) + 1)
                try:
                    if forward:
                        await payload.forward(uid)
                    else:
                        await payload.copy(uid)
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1

            if time.time() - last_edit > 3:
                last_edit = time.time()
                try:
                    await callback_query.edit_message_text(
                        f"📢 **Broadcasting…**\n\n"
                        f"✅ Sent: `{sent}`\n"
                        f"❌ Failed: `{failed}`\n"
                        f"📊 Progress: `{sent + failed}` / `{total}`"
                    )
                except Exception:
                    pass

        try:
            await callback_query.edit_message_text(
                f"✅ **Broadcast complete**\n\n"
                f"✅ Sent: `{sent}`\n"
                f"❌ Failed: `{failed}`\n"
                f"📊 Total: `{sent + failed}` / `{total}`"
            )
        except Exception:
            pass
    finally:
        sem.release()


@Client.on_callback_query(filters.regex(r"^bcast_back$"))
async def bcast_back(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)
    _clear_input_mode(callback_query.from_user.id)
    await _show_broadcast_settings(client, callback_query)


@Client.on_callback_query(filters.regex(r"^bcast_close$"))
async def bcast_close(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)
    _clear_input_mode(callback_query.from_user.id)
    await _reset_broadcast_state()
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("Closed.")


# ─── Capture User ID Input for Include/Exclude ──────────────────────────────
#
# This must NOT be a bare `filters.private & filters.text` handler: pyrogram's
# dispatcher stops at the first matching handler within a group, and
# `admin_handlers` sorts before `file_handlers`, so an unscoped handler would
# swallow every private text message and break URL downloads. It is therefore
# scoped to admins with an armed input prompt AND registered in group=1.

async def _bcast_awaiting_ids(_, __, message: Message) -> bool:
    if not message.from_user or not message.text:
        return False
    if message.text.startswith("/"):
        return False
    if not is_admin(message.from_user.id):
        return False
    return _get_input_mode(message.from_user.id) is not None


bcast_awaiting_ids = filters.create(_bcast_awaiting_ids)


@Client.on_message(filters.private & filters.text & bcast_awaiting_ids, group=1)
async def bcast_capture_user_ids(client: Client, message: Message):
    """Parse user IDs sent by an admin while an include/exclude prompt is armed."""
    mode = _get_input_mode(message.from_user.id)
    if mode is None:
        return

    ids: set[int] = set()
    for part in message.text.replace(",", " ").split():
        try:
            ids.add(int(part))
        except ValueError:
            continue

    if message.reply_to_message and message.reply_to_message.from_user:
        ids.add(message.reply_to_message.from_user.id)

    if not ids:
        return await message.reply_text(
            "No valid numeric user IDs found. Send IDs like `123456 789012`, or tap Back.",
            reply_parameters=ReplyParameters(message_id=message.id),
        )

    key = "include_users" if mode == "include" else "exclude_users"
    async with broadcast_state_lock():
        before = len(_broadcast_state[key])
        _broadcast_state[key].update(ids)
        added = len(_broadcast_state[key]) - before

    _clear_input_mode(message.from_user.id)
    await message.reply_text(
        f"Added `{added}` new user(s) to the **{mode}** list "
        f"({len(ids) - added} already present).",
        reply_parameters=ReplyParameters(message_id=message.id),
    )
    await _show_broadcast_settings(client, message)


@Client.on_message(filters.private & filters.command("reboot"))
async def reboot_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await message.reply_text(
            "Admin command received. Stopping the bot…",
            reply_parameters=ReplyParameters(message_id=message.id),
        )
        os.system(f"kill -9 {os.getpid()}")


@Client.on_message(filters.private & filters.command("users"))
async def list_users(client: Client, message: Message):
    from config import collection
    if not is_admin(message.from_user.id):
        return

    user_ids_list = [str(u["user_id"]) for u in collection.find({}, {"user_id": 1})]
    if not user_ids_list:
        return await message.reply_text("No users found.", reply_parameters=ReplyParameters(message_id=message.id))

    user_list = "\n".join(user_ids_list) + f"\nTotal users: {len(user_ids_list)}"
    for i in range(0, len(user_list), 4000):
        await message.reply_text(
            user_list[i:i + 4000],
            reply_parameters=ReplyParameters(message_id=message.id),
        )


@Client.on_message(filters.private & filters.command("stats"))
async def stats_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    # ── Today's date range ──────────────────────────────────────────
    from config import collection
    today = datetime.now().date()
    day_start_ts = int(time.mktime(today.timetuple()))

    # ── Aggregate across all user documents ─────────────────────────
    all_users = list(collection.find({}, {"stats": 1, "user_id": 1}))
    total_users = collection.count_documents({"user_id": {"$exists": True}})

    overall = {"files_sent": 0, "zip_with_pass": 0, "zip_without_pass": 0, "external_uploads": 0}
    today_stats = {"files_sent": 0, "zip_with_pass": 0, "zip_without_pass": 0, "external_uploads": 0}
    active_today = 0

    for user in all_users:
        s = user.get("stats", {})
        if not s:
            continue
        for key in overall:
            overall[key] += s.get(key, 0)
        # Count as "today" only if the user's counters were reset today
        if s.get("last_reset", 0) >= day_start_ts:
            active_today += 1
            for key in today_stats:
                today_stats[key] += s.get(key, 0)

    # ── Current live state ───────────────────────────────────────────
    import config as cfg
    queue_size = cfg.download_queue.qsize()
    if cfg.downloading_users:
        current_state = f"⬇️ Downloading ({len(cfg.downloading_users)} user(s))"
    elif cfg.zipping_users:
        current_state = f"🗜️ Zipping ({len(cfg.zipping_users)} user(s))"
    elif cfg.uploading_users:
        current_state = f"⬆️ Uploading ({len(cfg.uploading_users)} user(s))"
    else:
        current_state = "💤 Idle"

    active_uids = cfg.downloading_users | cfg.zipping_users | cfg.uploading_users
    active_str = ", ".join(f"`{uid}`" for uid in active_uids) if active_uids else "None"

    # ── Format ───────────────────────────────────────────────────────
    text = (
        f"📊 **Bot Usage Statistics**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🔴 **Current Status**\n"
        f"  State: {current_state}\n"
        f"  Active user: {active_str}\n"
        f"  Queue length: `{queue_size}`\n\n"

        f"📅 **Today  ({today.strftime('%d %b %Y')})** — {active_today} active user(s)\n"
        f"  📁 Files sent:        `{today_stats['files_sent']}`\n"
        f"  🔐 Zips w/ password:  `{today_stats['zip_with_pass']}`\n"
        f"  📦 Zips w/o password: `{today_stats['zip_without_pass']}`\n"
        f"  ☁️  External uploads:  `{today_stats['external_uploads']}`\n"
        f"  ➕ Total zips:        `{today_stats['zip_with_pass'] + today_stats['zip_without_pass']}`\n\n"

        f"🌐 **All-Time Totals** — {total_users} registered user(s)\n"
        f"  📁 Files sent:        `{overall['files_sent']}`\n"
        f"  🔐 Zips w/ password:  `{overall['zip_with_pass']}`\n"
        f"  📦 Zips w/o password: `{overall['zip_without_pass']}`\n"
        f"  ☁️  External uploads:  `{overall['external_uploads']}`\n"
        f"  ➕ Total zips:        `{overall['zip_with_pass'] + overall['zip_without_pass']}`"
    )

    await message.reply_text(text, reply_parameters=ReplyParameters(message_id=message.id))
