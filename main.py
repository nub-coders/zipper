from config import *
import os
import asyncio
from pyrogram import Client
from convopyro import Conversation
from plugins.file_handlers import process_queues

import config
config.ggg = os.getcwd()

# Bot configuration with Smart Plugins enabled
plugins = dict(root="plugins")
app = Client(
    'file_compressor_bot',
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    plugins=plugins,
)
Conversation(app)

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram import StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tools import is_user_on_chat, is_admin

async def check_membership_middleware(client, update):
    if not config.FORCE_SUBSCRIBE:
        return

    user = update.from_user
    if not user:
        return

    # Only enforce membership check in private chats — never reply in groups
    chat = getattr(update, "chat", None) or getattr(getattr(update, "message", None), "chat", None)
    if chat and chat.type.value != "private":
        return

    user_id = user.id
    if is_admin(user_id):
        return

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders")],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s")]
        ])
        text = "You need to join both @nub_coders and @nub_coder_s channels to use this bot.\n\nClick below to Join!"
        
        try:
            if hasattr(update, "reply_text"):
                await update.reply_text(text, reply_markup=button)
            elif hasattr(update, "message"):
                await update.message.reply_text(text, reply_markup=button)
        except Exception:
            pass
        raise StopPropagation()

app.add_handler(MessageHandler(check_membership_middleware), group=-1)
app.add_handler(CallbackQueryHandler(check_membership_middleware), group=-1)

async def timeout():
    """No-op kept for backwards compatibility.

    Per-user flags are cleared by download() itself, and
    process_queues() handles picking up the next queued item.
    """
    pass


# Update config timeout function
config.timeout = timeout


# ─── Main Bot: Validate Channel Access ────────────────────────────────────────

async def validate_main_bot_channel(client: Client) -> list[int]:
    """Check which processing channels the main bot can access.

    Returns a list of accessible channel IDs.
    """
    accessible_channels = []
    for ch_id in config.PROCESS_CHANNEL_IDS:
        try:
            chat = await client.get_chat(ch_id)
            print(f"✅ Main bot can access channel {ch_id} ({chat.title})")
            accessible_channels.append(ch_id)
        except Exception as e:
            print(f"❌ Main bot cannot access channel {ch_id}: {e}")
    return accessible_channels

# ─── Channel Result Watcher ───────────────────────────────────────────────────

async def channel_result_watcher(client: Client, channel_id: int):
    """Poll MongoDB for completed/failed tasks and forward results from channel to users.

    Workers store their result message ID in the task document.
    This watcher uses `copy_message` to send that exact message to the user.
    """
    from task_manager import task_mgr

    print(f"  Channel watcher: started polling MongoDB for results")

    while True:
        try:
            # Find tasks that are completed or failed, but user hasn't been notified yet
            unnotified_tasks = task_mgr.tasks.find({
                "status": {"$in": ["completed", "failed"]},
                "notified": {"$ne": True}
            })

            for task in unnotified_tasks:
                user_id = task.get("user_id")
                msg_id = task.get("result_msg_id")
                result_text = task.get("result_text")
                error = task.get("error")
                status = task.get("status")
                reply_id = task.get("main_bot_reply_id")

                if not user_id:
                    continue

                if status == "completed":
                    if msg_id:
                        try:
                            await client.copy_message(user_id, channel_id, msg_id)
                            # Delete the ZIP file from the channel once delivered
                            await client.delete_messages(channel_id, msg_id)
                        except Exception as e:
                            print(f"  Channel watcher: failed to copy/delete msg to {user_id}: {e}")
                    
                    if result_text:
                        try:
                            if reply_id:
                                await client.edit_message_text(user_id, reply_id, result_text)
                            else:
                                await client.send_message(user_id, result_text)
                        except Exception as e:
                            print(f"  Channel watcher: failed to send text to {user_id}: {e}")

                elif status == "failed":
                    error_msg = f"❌ Error: {error}"
                    try:
                        if reply_id:
                            await client.edit_message_text(user_id, reply_id, error_msg)
                        else:
                            await client.send_message(user_id, error_msg)
                    except Exception:
                        pass
                
                # Try to delete the original input file from the channel if it exists
                channel_msg_id = task.get("channel_msg_id")
                if channel_msg_id:
                    try:
                        await client.delete_messages(channel_id, channel_msg_id)
                    except Exception:
                        pass

                # Mark as notified
                task_mgr.tasks.update_one({"_id": task["_id"]}, {"$set": {"notified": True}})

            await asyncio.sleep(2)
        except Exception as e:
            print(f"  Channel watcher error: {e}")
            await asyncio.sleep(2)

async def progress_watcher(client: Client):
    """Periodically check MongoDB for task progress and update user messages."""
    from task_manager import task_mgr
    from worker import _fmt_size
    
    print("  Progress watcher: started polling MongoDB for progress updates")
    while True:
        try:
            active_tasks = task_mgr.tasks.find({
                "status": {"$in": ["downloading", "uploading", "zipping"]},
                "main_bot_reply_id": {"$ne": None},
                "notified": {"$ne": True}
            })
            for task in active_tasks:
                user_id = task.get("user_id")
                reply_id = task.get("main_bot_reply_id")
                status = task.get("status")
                current = task.get("current", 0)
                total = task.get("total", 0)
                
                if not user_id or not reply_id:
                    continue
                
                action_text = "📥 Downloading..." if status == "downloading" else "📤 Uploading..." if status == "uploading" else "🗜️ Zipping..."
                
                if status == "zipping":
                    total_files = task.get("total_files", 0)
                    current_file = task.get("current_file", 0)
                    if total_files > 0:
                        percent = (current_file / total_files) * 100
                        prog = f"[{'█' * int(percent // 10)}{'░' * (10 - int(percent // 10))}] {percent:.1f}%"
                        text = f"{action_text}\n\n{prog}\n📦 {current_file} / {total_files} files compressed"
                    else:
                        text = f"{action_text}\n\nWorking..."
                else:
                    if total > 0:
                        percent = (current / total) * 100
                        prog = f"[{'█' * int(percent // 10)}{'░' * (10 - int(percent // 10))}] {percent:.1f}%"
                        text = f"{action_text}\n\n{prog}\n{_fmt_size(current)} / {_fmt_size(total)}"
                    else:
                        text = f"{action_text}\n\n{_fmt_size(current)} processed"
                
                # Check if we should edit (only if text changed)
                last_text = task.get("last_progress_text", "")
                if text != last_text:
                    try:
                        await client.edit_message_text(user_id, reply_id, text)
                        task_mgr.tasks.update_one(
                            {"_id": task["_id"]},
                            {"$set": {"last_progress_text": text}}
                        )
                    except Exception:
                        pass

        except Exception as e:
            print(f"  Progress watcher error: {e}")
        await asyncio.sleep(3)

async def channel_cleanup_task(client: Client):
    """Periodically clean up old messages using task records in MongoDB."""
    import time
    from task_manager import task_mgr
    
    print("  Channel cleanup task started (runs every hour)")
    while True:
        try:
            if config.active_channel:
                cutoff = time.time() - 86400  # 24 hours ago
                
                # Find old tasks
                old_tasks = task_mgr.tasks.find({
                    "created_at": {"$lt": cutoff}
                })
                
                deleted_msgs = 0
                deleted_tasks = 0
                for task in old_tasks:
                    msgs_to_delete = []
                    if task.get("channel_msg_id"):
                        msgs_to_delete.append(task["channel_msg_id"])
                    if task.get("result_msg_id"):
                        msgs_to_delete.append(task["result_msg_id"])
                    
                    if msgs_to_delete:
                        try:
                            await client.delete_messages(config.active_channel, msgs_to_delete)
                            deleted_msgs += len(msgs_to_delete)
                        except Exception:
                            pass
                            
                    # Delete the task from MongoDB to save space
                    task_mgr.tasks.delete_one({"_id": task["_id"]})
                    deleted_tasks += 1
                
                if deleted_tasks > 0:
                    print(f"  Cleanup: Deleted {deleted_msgs} old messages and {deleted_tasks} old tasks.")
        except Exception as e:
            print(f"  Channel cleanup error: {e}")
        
        await asyncio.sleep(3600)  # run once an hour


async def start_background_tasks():
    """Start background tasks after bot initialization."""
    print("Bot components initialized…")

    # ── Initialize Workers ─────────────────────────────────────────────
    from worker import worker_manager

    if config.WORKER_BOT_TOKENS and config.PROCESS_CHANNEL_IDS:
        # First, check if main bot can access any channel
        main_channels = await validate_main_bot_channel(app)
        if main_channels:
            config.active_channel = main_channels[0]  # Just a fallback
            # Initialize worker bots with the channels the main bot can see
            await worker_manager.initialize(API_ID, API_HASH, main_channels)
            if worker_manager.available:
                # Use the channel that workers validated
                config.active_channel = worker_manager.active_channel
                print(f"🔗 Active processing channel: {config.active_channel}")
            else:
                print("⚠️  Workers unavailable. Main bot will process files directly.")
                config.active_channel = None
        else:
            print("⚠️  Main bot has no channel access. Running in single-bot mode.")
            config.active_channel = None
    else:
        config.active_channel = None
        if not config.WORKER_BOT_TOKENS:
            print("ℹ️  No WORKER_BOT_TOKENS set. Running in single-bot mode.")
        if not config.PROCESS_CHANNEL_IDS:
            print("ℹ️  No PROCESS_CHANNEL_IDS set. Running in single-bot mode.")

    # ── Start channel watcher (forwards worker results to users) ─────
    if config.active_channel:
        asyncio.create_task(channel_result_watcher(app, config.active_channel))
        asyncio.create_task(progress_watcher(app))
        asyncio.create_task(channel_cleanup_task(app))
        print(f"👁️  Channel watcher & Progress watcher started on {config.active_channel}")

    # ── Start queue processing (fallback for direct processing) ────────
    print("Starting queue processing…")
    asyncio.create_task(process_queues())
    print("Queue processing started…")
    print("Bot started successfully!")


from pyrogram import idle
import asyncio

async def main():
    print("Bot starting with Smart Plugins…")
    await app.start()
    await start_background_tasks()
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
