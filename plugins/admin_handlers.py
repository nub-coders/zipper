import config
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyParameters
from tools import is_admin, get_admin_ids
from config import collection
import os
import asyncio
import time
from datetime import datetime


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


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_message(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        return await message.reply_text("Please reply to a message you want to broadcast.")

    from config import collection
    stored_user_ids = [u["user_id"] for u in collection.find({}, {"user_id": 1})]
    
    if not stored_user_ids:
        return await message.reply_text("No users found in the database.")

    msg = await message.reply_text(f"Starting broadcast to {len(stored_user_ids)} users...")
    
    sent = 0
    failed = 0
    
    for uid in stored_user_ids:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
        except Exception as e:
            failed += 1
            print(f"Failed to copy message to {uid}: {e}")
        
        # Avoid hitting rate limits
        await asyncio.sleep(0.05)
        
        # Update progress every 20 messages
        if (sent + failed) % 20 == 0:
            try:
                await msg.edit_text(f"Broadcast in progress...\n\n✅ Sent: {sent}\n❌ Failed: {failed}\n\nTotal Users: {len(stored_user_ids)}")
            except Exception:
                pass

    await msg.edit_text(
        f"**Broadcast Completed!**\n\n✅ Successfully sent to: {sent}\n❌ Failed: {failed}\n\nTotal Users Processed: {sent + failed}"
    )


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
