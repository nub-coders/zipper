"""plugins/admin_handlers.py — Admin Diagnostic, Broadcasting, and Stats Dashboard with Bot API 10.2 & 10.3 Rich UI."""

import asyncio
import os
import time
from datetime import datetime

import config
from config import collection
from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.errors import FloodWait
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)
from rate_limiter import (
    allow_broadcast,
    broadcast_semaphore,
    broadcast_state_lock,
    wait_broadcast_slot,
)
from tools import is_admin
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


@Client.on_message(filters.private & filters.command("ping"))
async def ping_handler(client: Client, message: Message):
    import config as cfg
    start = time.time()
    reply = await rich_reply(message, f"{EmojiTag.PING} <b>Measuring latency…</b>", client=client)
    latency = (time.time() - start) * 1000

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

    diag_pairs = [
        ("Response Latency", f"<code>{latency:.2f} ms</code>"),
        ("System Uptime", f"<code>{uptime_str}</code>"),
        ("API Architecture", "<code>Bot API 10.3 / Kurigram</code>"),
        ("Service Status", "<code>Operational ✅</code>"),
    ]
    diag_table = rich_kv_table(diag_pairs, headers=["System Diagnostic", "Status"])

    text = (
        f"{EmojiTag.PING} {rich_heading('System Diagnostic & Latency', level=1)}\n"
        f"{diag_table}"
    )

    await rich_edit(reply, text, client=client)


@Client.on_message(filters.private & filters.command("skip"))
async def skip_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Admin command received:</b> Task skipped.",
            client=client,
        )


# ─── Broadcast State ────────────────────────────────────────────────────────

_broadcast_state = {
    "payload": None,
    "include_users": set(),
    "exclude_users": set(),
    "forward_mode": False,
}

_bcast_input_mode: dict[int, tuple[str, float]] = {}
_INPUT_MODE_TTL = 300.0


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
    async with broadcast_state_lock():
        _broadcast_state["payload"] = None
        _broadcast_state["include_users"].clear()
        _broadcast_state["exclude_users"].clear()
        _broadcast_state["forward_mode"] = False


# ─── Broadcast Settings UI ──────────────────────────────────────────────────

async def _show_broadcast_settings(client: Client, target):
    async with broadcast_state_lock():
        include_count = len(_broadcast_state["include_users"])
        exclude_count = len(_broadcast_state["exclude_users"])
        forward = _broadcast_state["forward_mode"]
        has_payload = _broadcast_state["payload"] is not None

    bcast_pairs = [
        ("Message Payload", "<code>✅ Configured</code>" if has_payload else "<code>❌ Not Set (Reply with /broadcast)</code>"),
        ("Include Filter", f"<code>{include_count} user(s)</code>"),
        ("Exclude Filter", f"<code>{exclude_count} user(s)</code>"),
        ("Delivery Mode", "<code>Forward Mode</code>" if forward else "<code>Copy Mode</code>"),
        ("Rate Limiter", "<code>Token Bucket Active</code>"),
    ]
    settings_table = rich_kv_table(bcast_pairs, headers=["Broadcast Parameter", "Setting"])

    text = (
        f"{EmojiTag.BROADCAST} {rich_heading('Broadcast Control Center', level=1)}\n"
        f"{settings_table}\n\n"
        f"{rich_note('Configure filters, delivery mode, or tap <b>Start Broadcast</b> to dispatch messages safely.')}"
    )

    btns = [
        [
            InlineKeyboardButton("➕ Include Users", callback_data="bcast_add_include", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.USER),
            InlineKeyboardButton("➖ Exclude Users", callback_data="bcast_add_exclude", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.TRASH),
        ],
        [
            InlineKeyboardButton("📋 View Include", callback_data="bcast_view_include", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.FILE),
            InlineKeyboardButton("📋 View Exclude", callback_data="bcast_view_exclude", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.FILE),
        ],
        [
            InlineKeyboardButton("🗑️ Clear Include", callback_data="bcast_clear_include", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.TRASH),
            InlineKeyboardButton("🗑️ Clear Exclude", callback_data="bcast_clear_exclude", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.TRASH),
        ],
        [
            InlineKeyboardButton(f"{'✅' if forward else '❌'} Forward Mode", callback_data="bcast_toggle_forward", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.REFRESH),
        ],
        [
            InlineKeyboardButton("🚀 START BROADCAST", callback_data="bcast_start", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.ROCKET),
        ],
        [
            InlineKeyboardButton("✖️ Close Menu", callback_data="bcast_close", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE),
        ],
    ]
    markup = InlineKeyboardMarkup(btns)

    if isinstance(target, CallbackQuery):
        await rich_edit(target, text, reply_markup=markup, client=client)
    else:
        await rich_reply(target, text, reply_markup=markup, client=client)


async def _arm_broadcast(message: Message, forward: bool):
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


_ID_PROMPT = (
    "Send the user IDs to add to the <b>{list_name}</b> list.\n\n"
    "Space or comma separated, e.g. <code>123456 789012</code>\n"
    "You can also reply to a forwarded message from that user.\n\n"
    "<i>This prompt expires in 5 minutes.</i>"
)


@Client.on_callback_query(filters.regex(r"^bcast_add_include$"))
async def bcast_add_include(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    _set_input_mode(callback_query.from_user.id, "include")
    await rich_edit(
        callback_query,
        f"{EmojiTag.USER} {rich_heading('Add to Include List', level=2)}\n\n" + _ID_PROMPT.format(list_name="include"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="bcast_back", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK)]
        ]),
        client=client,
    )


@Client.on_callback_query(filters.regex(r"^bcast_add_exclude$"))
async def bcast_add_exclude(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("Admin only.", show_alert=True)

    _set_input_mode(callback_query.from_user.id, "exclude")
    await rich_edit(
        callback_query,
        f"{EmojiTag.TRASH} {rich_heading('Add to Exclude List', level=2)}\n\n" + _ID_PROMPT.format(list_name="exclude"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="bcast_back", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK)]
        ]),
        client=client,
    )


async def _answer_with_list(callback_query: CallbackQuery, key: str, label: str):
    async with broadcast_state_lock():
        users = sorted(_broadcast_state[key])

    if not users:
        text = f"{label} list is empty."
    else:
        text = f"{label} list ({len(users)}):\n" + ", ".join(str(u) for u in users)

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

        if include:
            target_users = [u for u in stored_users if u in include]
        else:
            target_users = [u for u in stored_users if u not in exclude]

        if not target_users:
            return await callback_query.answer("No targets left after filtering.", show_alert=True)

        total = len(target_users)
        await rich_edit(
            callback_query,
            f"{EmojiTag.ROCKET} {rich_heading('Dispatching Broadcast', level=2)}\n\n"
            f"Target Audience: <code>{total} user(s)</code>\n"
            f"Mode: <code>{'Forward' if forward else 'Direct Copy'}</code>",
            client=client,
        )

        sent = 0
        failed = 0
        last_edit = time.time()

        for uid in target_users:
            await wait_broadcast_slot(max_wait=1.0)

            try:
                if forward:
                    await payload.forward(uid)
                else:
                    await payload.copy(uid)
                sent += 1
            except FloodWait as e:
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
                pct = (sent + failed) * 100 / total
                bar_len = 16
                ticks = int(pct / (100 / bar_len))
                bar = "█" * ticks + "░" * (bar_len - ticks)

                progress_table = rich_kv_table([
                    ("Sent Successfully", f"<code>{sent}</code>"),
                    ("Failed", f"<code>{failed}</code>"),
                    ("Progress", f"<code>[{bar}] {pct:.1f}%</code>"),
                ])
                try:
                    await rich_edit(
                        callback_query,
                        f"{EmojiTag.BROADCAST} {rich_heading('Broadcasting in Progress', level=2)}\n"
                        f"{progress_table}",
                        client=client,
                    )
                except Exception:
                    pass

        summary_table = rich_kv_table([
            ("Total Delivered", f"<code>{sent}</code>"),
            ("Delivery Failures", f"<code>{failed}</code>"),
            ("Total Targets", f"<code>{total}</code>"),
        ])
        await rich_edit(
            callback_query,
            f"{EmojiTag.SUCCESS} {rich_heading('Broadcast Completed', level=1)}\n"
            f"{summary_table}",
            reply_markup=home_buttons,
            client=client,
        )
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
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>No valid numeric user IDs found.</b> Send IDs like <code>123456 789012</code>.",
            client=client,
        )

    key = "include_users" if mode == "include" else "exclude_users"
    async with broadcast_state_lock():
        before = len(_broadcast_state[key])
        _broadcast_state[key].update(ids)
        added = len(_broadcast_state[key]) - before

    _clear_input_mode(message.from_user.id)
    await rich_reply(
        message,
        f"{EmojiTag.SUCCESS} Added <code>{added}</code> new user(s) to the <b>{mode}</b> list.",
        client=client,
    )
    await _show_broadcast_settings(client, message)


@Client.on_message(filters.private & filters.command("reboot"))
async def reboot_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await rich_reply(
            message,
            f"{EmojiTag.REFRESH} <b>Rebooting bot process…</b>",
            client=client,
        )
        os.system(f"kill -9 {os.getpid()}")


@Client.on_message(filters.private & filters.command("users"))
async def list_users(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    user_ids_list = [str(u["user_id"]) for u in collection.find({}, {"user_id": 1})]
    if not user_ids_list:
        return await rich_reply(message, f"{EmojiTag.INFO} <b>No users found in database.</b>", client=client)

    user_list = "\n".join(user_ids_list) + f"\n\nTotal registered users: {len(user_ids_list)}"
    for i in range(0, len(user_list), 4000):
        await rich_reply(
            message,
            f"<code>{rich_esc(user_list[i:i + 4000])}</code>",
            client=client,
        )


@Client.on_message(filters.private & filters.command("stats"))
async def stats_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    today = datetime.now().date()
    day_start_ts = int(time.mktime(today.timetuple()))

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
        if s.get("last_reset", 0) >= day_start_ts:
            active_today += 1
            for key in today_stats:
                today_stats[key] += s.get(key, 0)

    import config as cfg
    queue_size = cfg.download_queue.qsize()
    active_uids = cfg.downloading_users | cfg.zipping_users | cfg.uploading_users

    today_pairs = [
        ("Files Processed", f"<code>{today_stats['files_sent']}</code>"),
        ("Password ZIPs", f"<code>{today_stats['zip_with_pass']}</code>"),
        ("Regular ZIPs", f"<code>{today_stats['zip_without_pass']}</code>"),
        ("Cloud Uploads", f"<code>{today_stats['external_uploads']}</code>"),
        ("Active Users Today", f"<code>{active_today}</code>"),
    ]
    today_table = rich_kv_table(today_pairs, headers=[f"Today ({today.strftime('%d %b %Y')})", "Metrics"])

    overall_pairs = [
        ("Total Files", f"<code>{overall['files_sent']}</code>"),
        ("Total Password ZIPs", f"<code>{overall['zip_with_pass']}</code>"),
        ("Total Regular ZIPs", f"<code>{overall['zip_without_pass']}</code>"),
        ("Total Cloud Uploads", f"<code>{overall['external_uploads']}</code>"),
        ("Registered Users", f"<code>{total_users}</code>"),
        ("Queue Backlog", f"<code>{queue_size}</code>"),
        ("Active Operations", f"<code>{len(active_uids)}</code>"),
    ]
    overall_table = rich_kv_table(overall_pairs, headers=["All-Time Totals", "Metrics"])

    text = (
        f"{EmojiTag.STATS} {rich_heading('Global Bot Usage Statistics', level=1)}\n"
        f"{today_table}\n\n"
        f"{overall_table}"
    )

    await rich_reply(message, text, client=client)
