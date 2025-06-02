import os
import queue

# Bot configuration
API_ID = 21869707
API_HASH = '31ec80a4adad7aaad9262e894e3654e6'
BOT_TOKEN='6239906461:AAFrz8NvMpG5o9oXGIx_XDEl34ulTK18wtY'
BOT_TOKEN='7571416784:AAEJJK9bINObGk96VuC6JLR2CzwclVUOXbE'
# Global variables
collection = None
ggg = os.getcwd()
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
zipping_in_progress = False
download_in_progress = False
user_ids = {}
active_user_id = None
time_left = 0
timeout = None
