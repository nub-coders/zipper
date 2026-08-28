"""plugins/admin_handlers.py — Admin Diagnostic, Broadcasting, and Stats Dashboard with Bot API 10.2 & 10.3 Rich UI."""

import asyncio
import os
import time
from datetime import datetime

import config
from config import collection
from plugins.ui_components import home_buttons
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
from tools import get_admin_ids, is_admin
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
    from batch_manager import pending_queue_counts
    start = time.time()
    sent_msg = await rich_reply(
        message,
        f"{EmojiTag.REFRESH} <b>Measuring latency…</b>",
        client=client,
    )
    latency_ms = (time.time() - start) * 1000

    uptime_str = "Operational"
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            hours, remainder = divmod(int(uptime_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"
    except Exception:
        pass

    rows = [
        ("Network Latency", f"<code>{latency_ms:.1f} ms</code>"),
        ("System Uptime", f"<code>{uptime_str}</code>"),
        ("Queue Depth", f"<code>{pending_queue_counts()[0]}</code>"),
        ("Active Workers", f"<code>{len(cfg.downloading_users | cfg.zipping_users | cfg.uploading_users)}</code>"),
    ]
    diag_table = rich_kv_table(rows, headers=["Diagnostic Probe", "Measurement"])

    html_content = (
        f"{rich_heading(f'{EmojiTag.PING} System Diagnostics & Latency', level=1)}\n"
        f"{diag_table}"
    )
    await rich_edit(sent_msg, html_content, client=client)


# ─── Admin Skip Command ──────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("skip"))
async def skip_command_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Admin command received:</b> Task skipped.",
            client=client,
        )


# ─── Broadcast State (Per-Admin) ─────────────────────────────────────────────

_broadcast_states: dict[int, dict] = {}


def _get_admin_broadcast_state(admin_id: int) -> dict:
    if admin_id not in _broadcast_states:
        _broadcast_states[admin_id] = {
            "payload": None,
            "include_sender_name": False,
        }
    return _broadcast_states[admin_id]


async def _reset_broadcast_state(admin_id: int):
    async with broadcast_state_lock():
        _broadcast_states.pop(admin_id, None)


# ─── Broadcast Settings UI ──────────────────────────────────────────────────

async def _show_broadcast_settings(client: Client, target, admin_id: int):
    async with broadcast_state_lock():
        state = _get_admin_broadcast_state(admin_id)
        include_sender = state["include_sender_name"]
        has_payload = state["payload"] is not None

    total_users = await asyncio.to_thread(_count_stored_users)

    bcast_pairs = [
        ("Message Payload", "<code>✅ Configured</code>" if has_payload else "<code>❌ Not Set (Reply to a message with /broadcast)</code>"),
        ("Include Sender Name", "<code>True</code>" if include_sender else "<code>False</code>"),
        ("Target Audience", f"<code>{total_users} user(s)</code>"),
        ("Rate Limiter", "<code>Token Bucket Active</code>"),
    ]
    settings_table = rich_kv_table(bcast_pairs, headers=["Broadcast Parameter", "Setting"])

    text = (
        f"{rich_heading(f'{EmojiTag.BROADCAST} Broadcast Control Center', level=1)}\n"
        f"{settings_table}\n\n"
        f"<i>Reply to a message with <code>/broadcast</code> to set the message, toggle sender name preference, then start broadcast.</i>"
    )

    toggle_btn_text = f"Include Sender Name ({'True' if include_sender else 'False'})"
    toggle_style = ButtonStyle.SUCCESS if include_sender else ButtonStyle.DEFAULT
    toggle_icon = Emoji.SUCCESS if include_sender else Emoji.CLOSE

    btns = [
        [
            InlineKeyboardButton(
                toggle_btn_text,
                callback_data="bcast_toggle_sender",
                style=toggle_style,
                icon_custom_emoji_id=toggle_icon,
            ),
        ],
        [
            InlineKeyboardButton(
                "START BROADCAST",
                callback_data="bcast_start",
                style=ButtonStyle.PRIMARY,
                icon_custom_emoji_id=Emoji.ROCKET,
            ),
        ],
        [
            InlineKeyboardButton(
                "Close Menu",
                callback_data="bcast_close",
                style=ButtonStyle.DANGER,
                icon_custom_emoji_id=Emoji.CLOSE,
            ),
        ],
    ]
    markup = InlineKeyboardMarkup(btns)

    if isinstance(target, CallbackQuery):
        await rich_edit(target, text, reply_markup=markup, client=client)
    else:
        await rich_reply(target, text, reply_markup=markup, client=client)


async def _arm_broadcast(admin_id: int, message: Message):
    async with broadcast_state_lock():
        state = _get_admin_broadcast_state(admin_id)
        state["payload"] = message.reply_to_message


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_command_handler(client: Client, message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    if message.reply_to_message:
        await _arm_broadcast(admin_id, message)

    await _show_broadcast_settings(client, message, admin_id)


@Client.on_callback_query(filters.regex(r"^bcast_toggle_sender$"))
async def bcast_toggle_sender(client: Client, callback_query: CallbackQuery):
    admin_id = callback_query.from_user.id
    if not is_admin(admin_id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        state = _get_admin_broadcast_state(admin_id)
        state["include_sender_name"] = not state["include_sender_name"]
        val = state["include_sender_name"]

    await callback_query.answer(f"Include Sender Name: {val}")
    await _show_broadcast_settings(client, callback_query, admin_id)


# The Mongo driver is synchronous, so every query below is run through
# asyncio.to_thread by its caller to keep the event loop responsive.

def _fetch_stored_user_ids() -> list[int]:
    return [
        u["user_id"]
        for u in collection.find({}, {"user_id": 1})
        if isinstance(u.get("user_id"), int)
    ]


def _count_stored_users() -> int:
    return collection.count_documents({"user_id": {"$exists": True}})


def _fetch_user_stat_docs() -> list[dict]:
    return list(collection.find({}, {"stats": 1, "user_id": 1}))


@Client.on_callback_query(filters.regex(r"^bcast_start$"))
async def bcast_start(client: Client, callback_query: CallbackQuery):
    admin_id = callback_query.from_user.id
    if not is_admin(admin_id):
        return await callback_query.answer("Admin only.", show_alert=True)

    async with broadcast_state_lock():
        state = _get_admin_broadcast_state(admin_id)
        payload = state["payload"]
        include_sender = state["include_sender_name"]

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

        target_users = await asyncio.to_thread(_fetch_stored_user_ids)
        if not target_users:
            return await callback_query.answer("No users in database.", show_alert=True)

        total = len(target_users)
        await rich_edit(
            callback_query,
            f"{rich_heading(f'{EmojiTag.ROCKET} Dispatching Broadcast', level=2)}\n\n"
            f"Target Audience: <code>{total} user(s)</code>\n"
            f"Include Sender Name: <code>{include_sender}</code>",
            client=client,
        )

        sent = 0
        failed = 0
        last_edit = time.time()

        for uid in target_users:
            await wait_broadcast_slot(max_wait=1.0)

            try:
                if include_sender:
                    await payload.forward(uid)
                else:
                    await payload.copy(uid)
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(int(getattr(e, "value", 5)) + 1)
                try:
                    if include_sender:
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
                pct = (sent + failed) * 100 / total if total else 0
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
                        f"{rich_heading(f'{EmojiTag.BROADCAST} Broadcasting in Progress', level=2)}\n"
                        f"{progress_table}",
                        client=client,
                    )
                except Exception:
                    pass

        summary_table = rich_kv_table([
            ("Total Delivered", f"<code>{sent}</code>"),
            ("Delivery Failures", f"<code>{failed}</code>"),
            ("Total Targets", f"<code>{total}</code>"),
            ("Include Sender Name", f"<code>{include_sender}</code>"),
        ])
        await rich_edit(
            callback_query,
            f"{rich_heading(f'{EmojiTag.SUCCESS} Broadcast Completed', level=1)}\n"
            f"{summary_table}",
            reply_markup=home_buttons,
            client=client,
        )
    finally:
        sem.release()


@Client.on_callback_query(filters.regex(r"^bcast_close$"))
async def bcast_close(client: Client, callback_query: CallbackQuery):
    admin_id = callback_query.from_user.id
    if not is_admin(admin_id):
        return await callback_query.answer("Admin only.", show_alert=True)
    await _reset_broadcast_state(admin_id)
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("Closed.")


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

    total_users = await asyncio.to_thread(_count_stored_users)
    if total_users == 0:
        return await rich_reply(message, f"{EmojiTag.INFO} <b>No users found in database.</b>", client=client)

    summary_pairs = [
        ("Total Registered Users", f"<code>{total_users}</code>"),
        ("Admin Count", f"<code>{len(get_admin_ids())}</code>"),
    ]
    summary_table = rich_kv_table(summary_pairs, headers=["Metric", "Value"])
    msg_text = (
        f"{rich_heading(f'{EmojiTag.MEMBERS} User Management Overview', level=1)}\n"
        f"{summary_table}\n\n"
        f"<i>For privacy and performance protection, individual user IDs are not dumped. Use <code>/stats</code> to view platform engagement.</i>"
    )
    await rich_reply(message, msg_text, client=client)


@Client.on_message(filters.private & filters.command("stats"))
async def stats_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    today = datetime.now().date()
    day_start_ts = int(time.mktime(today.timetuple()))

    all_users = await asyncio.to_thread(_fetch_user_stat_docs)
    total_users = await asyncio.to_thread(_count_stored_users)

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
    from batch_manager import pending_queue_counts
    queue_size, _ = pending_queue_counts()
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
        f"{rich_heading(f'{EmojiTag.STATS} Global Bot Usage Statistics', level=1)}\n"
        f"{today_table}\n\n"
        f"{overall_table}"
    )

    await rich_reply(message, text, client=client)
