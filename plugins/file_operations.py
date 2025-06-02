
import os
import shutil
import subprocess
import requests
import aiohttp
import time
import random
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class Timer:
    def __init__(self, time_between=2):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        if time.time() > (self.start_time + self.time_between):
            self.start_time = time.time()
            return True
        return False

async def upload_to_gofile(callback_query, zip_filename, message):
    """Upload large files to gofile.io"""
    try:
        response = requests.get("https://api.gofile.io/servers")
        data = response.json()
        server = data["data"]["servers"][0]['name']

        if not server:
            return await callback_query.message.reply_text("No storage available in gofile.io please try again later:")

        transfer_url = f"https://{server}.gofile.io/uploadFile"
        command = ["curl", "-F", f"file=@{zip_filename}", transfer_url]
        output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for line in output.stdout:
            line = line.strip()
            if line:
                print(line)

        start_index = line.find("https://gofile.io")
        end_index = line.find('"', start_index)
        link = line[start_index:end_index]

        download_button = InlineKeyboardMarkup([[InlineKeyboardButton("Download File", url=link)]])
        await message.edit_text(
            f"Not able to upload files more than 2GB here\nSo I provided this download link:",
            reply_markup=download_button
        )

    except Exception as e:
        print(f"Error uploading to gofile: {e}")

def get_file_size_info(user_dir, max_storage):
    """Get file size information for user directory"""
    if not os.path.exists(user_dir):
        return 0, max_storage, []
    
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = max_storage - total_size
    files = os.listdir(user_dir)
    
    return total_size, remaining_storage, files

def cleanup_user_directory(user_dir):
    """Clean up user directory"""
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
        os.makedirs(user_dir, exist_ok=True)
