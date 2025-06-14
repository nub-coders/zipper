from config import *
import urllib3
urllib3.disable_warnings()
import random
import os
import time
from pyrogram import Client
from convopyro import Conversation
import queue
import asyncio
from plugins.file_handlers import process_queues

# Import all configuration and globals from config
from config import *

# Import all configuration and globals from config (collection already initialized there)
import config
config.ggg = os.getcwd()

# Bot configuration with Smart Plugins enabled
time.sleep(2)
plugins = dict(root="plugins")
app = Client('file_compressor_bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True, plugins=plugins)
Conversation(app)

async def timeout():
    global dd, zipping_in_progress, download_in_progress
    config.zipping_in_progress = False
    config.download_in_progress = False
    zipping_in_progress = False
    download_in_progress = False

    if not config.premium_queue.empty():
        next_file = config.premium_queue.get()
        config.dd -= 1
        dd -= 1
        config.user_ids.clear()
        from plugins.file_handlers import download
        await download(next_file)
    elif not config.download_queue.empty():
        next_file = config.download_queue.get()
        config.dd -= 1
        dd -= 1
        config.user_ids.clear()
        from plugins.file_handlers import download
        await download(next_file)

# Update config timeout function
config.timeout = timeout

async def start_background_tasks():
    """Start background tasks after bot initialization"""
    print("Bot components initialized...")
    print("Starting queue processing...")
    
    # Start queue processing in background
    asyncio.create_task(process_queues())
    print("Queue processing started...")
    print("Bot started successfully!")

if __name__ == "__main__":
    print("Bot starting with Smart Plugins...")
    
    # Schedule background tasks to start after bot initialization
    asyncio.get_event_loop().call_later(3, lambda: asyncio.create_task(start_background_tasks()))
    
    # Use Pyrogram's built-in event loop management
    app.run()
