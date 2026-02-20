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


async def timeout():
    """Process next file in queue after a download completes."""
    config.zipping_in_progress = False
    config.download_in_progress = False
    config.uploading_in_progress = False

    next_file = None
    if not config.premium_queue.empty():
        next_file = config.premium_queue.get()
    elif not config.download_queue.empty():
        next_file = config.download_queue.get()

    if next_file:
        config.dd -= 1
        config.user_ids.clear()
        from plugins.file_handlers import download
        await download(next_file)


# Update config timeout function
config.timeout = timeout


async def start_background_tasks():
    """Start background tasks after bot initialization."""
    print("Bot components initialized…")
    print("Starting queue processing…")
    asyncio.create_task(process_queues())
    print("Queue processing started…")
    print("Bot started successfully!")


if __name__ == "__main__":
    print("Bot starting with Smart Plugins…")
    asyncio.get_event_loop().call_later(
        3, lambda: asyncio.create_task(start_background_tasks())
    )
    app.run()
