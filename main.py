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

async def start_bot():
    """Start the bot and background tasks"""
    print("Bot starting with Smart Plugins...")
    
    # Start the bot
    await app.start()
    print("Bot components initialized...")
    
    # Start queue processing in background
    asyncio.create_task(process_queues())
    print("Queue processing started...")
    
    # Keep the bot running
    await app.idle()
    print("Bot started successfully!")

if __name__ == "__main__":
    # Run the bot with proper async handling
    asyncio.run(start_bot())
