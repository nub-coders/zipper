import urllib3
urllib3.disable_warnings()
import random
import os
import time
from pyrogram import Client
from convopyro import Conversation
import queue

# Import plugins
from plugins.installer import initialize_bot
from config import *

# Initialize bot and get database collection
collection = initialize_bot()
ggg = os.getcwd()

# Bot configuration with Smart Plugins enabled
time.sleep(2)
plugins = dict(root="plugins")
app = Client('file_compressor_bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True, plugins=plugins)
Conversation(app)

# Global variables
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
zipping_in_progress = False
download_in_progress = False
user_ids = {}
active_user_id = None
time_left = 0

async def timeout():
    global dd, zipping_in_progress, download_in_progress
    zipping_in_progress = False
    download_in_progress = False

    if not premium_queue.empty():
        next_file = premium_queue.get()
        dd -= 1
        user_ids.clear()
        from plugins.file_handlers import download
        await download(next_file)
    elif not download_queue.empty():
        next_file = download_queue.get()
        dd -= 1
        user_ids.clear()
        from plugins.file_handlers import download
        await download(next_file)

# Make global variables accessible to plugins
def get_globals():
    return {
        'collection': collection,
        'ggg': ggg,
        'dd': dd,
        'download_queue': download_queue,
        'premium_queue': premium_queue,
        'zipping_in_progress': zipping_in_progress,
        'download_in_progress': download_in_progress,
        'user_ids': user_ids,
        'active_user_id': active_user_id,
        'time_left': time_left,
        'timeout': timeout
    }

if __name__ == "__main__":
    print("Bot starting with Smart Plugins...")
    update_globals()  # Update plugin globals before starting
    app.run()

# Make global variables accessible to plugins
def update_globals():
    """Update global variables in plugins"""
    import plugins.file_handlers as fh
    import plugins.basic_commands as bc
    import plugins.admin_handlers as ah
    import plugins.callback_handlers as ch
    
    # Update file_handlers globals
    fh.dd = dd
    fh.download_queue = download_queue
    fh.premium_queue = premium_queue
    fh.zipping_in_progress = zipping_in_progress
    fh.download_in_progress = download_in_progress
    fh.user_ids = user_ids
    fh.active_user_id = active_user_id
    fh.time_left = time_left
    fh.timeout = timeout
    fh.collection = collection
    fh.ggg = ggg
    
    # Update basic_commands globals
    bc.collection = collection
    bc.ggg = ggg
    bc.timeout = timeout
    
    # Update admin_handlers globals
    ah.collection = collection
    ah.ggg = ggg
    
    # Update callback_handlers globals
    ch.dd = dd
    ch.download_queue = download_queue
    ch.premium_queue = premium_queue
    ch.user_ids = user_ids
    ch.active_user_id = active_user_id
    ch.time_left = time_left
    ch.collection = collection
    ch.ggg = ggg
    ch.timeout = timeout