import urllib3
urllib3.disable_warnings()
import random
import os
import certifi
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked
from convopyro import Conversation
import subprocess
import shutil
import requests
import hashlib
import aiohttp
import datetime
import pymongo
import time
from config import *
from tools import is_user_on_chat
import asyncio
import queue
import math


ggg = os.getcwd()

client = pymongo.MongoClient("mongodb+srv://ankitkr23835:air8858@cluster0.cxh2ryf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", tlsCAFile=certifi.where())
db = client["telegram_bot"]
conversations = {}
collection = db["users"]

# Function to store user ID and timestamp
def store_user(user_id):
    timestamp = int(time.time())
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_userr(user_id):
    timestamp = int(time.time()) - 21600
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_code(user_id, verifycode):
    user_data = {"user_id": user_id, "verifycode": verifycode}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

# Function to check user status
def check_status(user_id):
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time
        if time_difference < 21600:  # 6 hours in seconds
            return f"Time remaining: {21600 - time_difference} seconds."
        else:
            return "Your session has expired. Please reverify the bot again."
    else:
        return "User not found or session expired. Please start the bot."

# Get the current directory
current_dir = f"{ggg}/zipper"
current_time = datetime.datetime.now()
print(f"Current Date and Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Specify the zipper directory name
zipper_dir_name = "zipper"

for dirpath, dirnames, filenames in os.walk(current_dir):
    latest_file_creation_time = 0
    for filename in filenames:
        file_path = os.path.join(dirpath, filename)
        file_creation_time = os.path.getctime(file_path)
        if file_creation_time > latest_file_creation_time:
            latest_file_creation_time = file_creation_time

    if latest_file_creation_time > 0:
        time_difference = current_time - datetime.datetime.fromtimestamp(latest_file_creation_time)
        print(f"Directory: {dirpath}, Updated {time_difference} ago")

        if zipper_dir_name in dirpath:
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                file_creation_time = os.path.getctime(file_path)

                if (current_time - datetime.datetime.fromtimestamp(file_creation_time)).days >= 3:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")

import cryptg
import requests
import asyncio
import subprocess
import shutil

# Directory path
api_id = API_ID
api_hash = API_HASH
token = BOT_TOKEN
admin = 6476862483

time.sleep(2)
dex = "zipper/duo"

app = Client('file_compressor_bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
Conversation(app)  # Initialize conversation plugin

links = {
    'Monday_phase1': 'https://link-center.net/756279/verify',
    'Monday_phase2': 'https://link-center.net/756279/verify1',
    'Monday_phase3': 'https://link-center.net/756279/verify2',
    'Monday_phase4': 'https://link-center.net/756279/verify3',
    'Tuesday_phase1': 'https://link-center.net/756279/verify4',
    'Tuesday_phase2': 'https://link-center.net/756279/verify5',
    'Tuesday_phase3': 'https://link-center.net/756279/verify6',
    'Tuesday_phase4': 'https://link-center.net/756279/verify7',
    'Wednesday_phase1': 'https://link-center.net/756279/verify8',
    'Wednesday_phase2': 'https://link-center.net/756279/verify9',
    'Wednesday_phase3': 'https://link-center.net/756279/verify10',
    'Wednesday_phase4': 'https://link-center.net/756279/verify11',
    'Thursday_phase1': 'https://link-center.net/756279/verify12',
    'Thursday_phase2': 'https://link-center.net/756279/verify13',
    'Thursday_phase3': 'https://link-center.net/756279/verify14',
    'Thursday_phase4': 'https://link-center.net/756279/verify15',
    'Friday_phase1': 'https://link-center.net/756279/verify16',
    'Friday_phase2': 'https://link-center.net/756279/verify17',
    'Friday_phase3': 'https://link-center.net/756279/verify18',
    'Friday_phase4': 'https://link-center.net/756279/verify19',
    'Saturday_phase1': 'https://link-center.net/756279/verify20',
    'Saturday_phase2': 'https://link-center.net/756279/verify21',
    'Saturday_phase3': 'https://link-center.net/756279/verify22',
    'Saturday_phase4': 'https://link-center.net/756279/verify23',
    'Sunday_phase1': 'https://link-center.net/756279/verify24',
    'Sunday_phase2': 'https://link-center.net/756279/verify25',
    'Sunday_phase3': 'https://link-center.net/756279/verify26',
    'Sunday_phase4': 'https://link-center.net/756279/verify27',
}

days_of_week = {
    'Monday_phase1': '/start verifycodeis27373636384747',
    'Monday_phase2': '/start verifycodeis273733764778',
    'Monday_phase3': '/start verifycodeis273736327364637',
    'Monday_phase4': '/start verifycodeis27373636737473',
    'Tuesday_phase1': '/start verifycodeis2737363373748484',
    'Tuesday_phase2': '/start verifycodeis27373636e626353747',
    'Tuesday_phase3': '/start verifycodeis27373636365449',
    'Tuesday_phase4': '/start verifycodeis27373755635449',
    'Wednesday_phase1': '/start verifycodeis2737363636758',
    'Wednesday_phase2': '/start verifycodeis27373666365449',
    'Wednesday_phase3': '/start verifycodeis27373636365744',
    'Wednesday_phase4': '/start verifycodeis27373636364487',
    'Thursday_phase1': '/start verifycodeis27373636365644',
    'Thursday_phase2': '/start verifycodeis27373636366744',
    'Thursday_phase3': '/start verifycodeis273736363534799',
    'Thursday_phase4': '/start verifycodeis2737363664897876',
    'Friday_phase1': '/start verifycodeis27373636364377',
    'Friday_phase2': '/start verifycodeis27373636354478',
    'Friday_phase3': '/start verifycodeis27373636329383',
    'Friday_phase4': '/start verifycodeis27373636365437373',
    'Saturday_phase1': '/start verifycodeis27373636362737363',
    'Saturday_phase2': '/start verifycodeis27373636286364',
    'Saturday_phase3': '/start verifycodeis27373636363874',
    'Saturday_phase4': '/start verifycodeis2737363373664',
    'Sunday_phase1': '/start verifycodeis273736327263648',
    'Sunday_phase2': '/start verifycodeis2737363639127644',
    'Sunday_phase3': '/start verifycodeis2737363827374',
    'Sunday_phase4': '/start verifycodeis2737363443648',
}

group_user_ids = {}
mesaage = None

# Define common button layouts
help_button = InlineKeyboardButton("❓ Help", callback_data="help")
clear_buttons = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
cancel_download_button = InlineKeyboardButton("❌ Cancel Download", callback_data="cancel_download")

common_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [InlineKeyboardButton("🏠 Home", callback_data="home"),
     InlineKeyboardButton("🗜️📑 Compress files", callback_data="fzip")],
    [help_button]
])

home_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [help_button]
])

back_buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home"), help_button]])

pass_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔒 Set a Password", callback_data="set_password")],
    [InlineKeyboardButton("🔓Continue without Password", callback_data="no_password")]
])

file_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [InlineKeyboardButton("📑 Compress files", callback_data="fzip"), help_button]
])

nofile_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [help_button]
])

# Global variables
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
max_retry = 0
zipping_in_progress = False
download_in_progress = False
user_ids = {}
link_download_queue = queue.Queue()
link_downloading = False
time_left = 0
stopper = 0
active_user_id = None
pinky = 1
edit = 0
video_sent = False

class Timer:
    def __init__(self, time_between=2):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        if time.time() > (self.start_time + self.time_between):
            self.start_time = time.time()
            return True
        return False

import random
import string

def generate_random_code(length=10):
    characters = string.ascii_letters + string.digits
    code = ''.join(random.choice(characters) for i in range(length))
    return code

async def liink_send(message):
    global dd
    headers = {'User-Agent': 'Mozilla/5.0'}
    import requests
    code = generate_random_code()
    print(code)
    store_code(message.from_user.id, code)
    long = f'http://t.me/FILEs_COMPRESSOR_BOT?start=verifycodeis{code}'
    url = f'https://api.cuty.io/quick?token=b09763cdea0deb0cc373ca5eb&url={long}'

    try:
        response = requests.get(url, verify=False)
        data = response.json()
        print(data)
        print(data["shortenedUrl"])

        verify_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Click to verify", url=data["shortenedUrl"])],
            [InlineKeyboardButton("how to verify", url="https://t.me/nub_coder_s_updates/3")]
        ])

        await message.reply_text(
            "you need to verify first in order to use the bot to avoid spam\n\n"
            "This is only file to zip bot which gives 4.5 GB storage support to the user \n\n"
            "You can also use /premium to get many benifits including no ads",
            reply_markup=verify_button
        )
    except Exception as e:
        print(f"Error in liink_send: {e}")

    if not premium_queue.empty():
        next_file = premium_queue.get()
        dd = dd - 1
        user_ids.clear()
        await download(next_file)
    elif not download_queue.empty():
        next_file = download_queue.get()
        dd = dd - 1
        user_ids.clear()
        await download(next_file)

async def link_send(message):
    global dd
    phases = ['phase1', 'phase2', 'phase3', 'phase4']
    current_datetime = datetime.datetime.now()
    current_hour = current_datetime.hour
    phase_index = (current_hour // 6) % 4
    day_name = current_datetime.strftime('%A')
    output = f'{day_name}_{phases[phase_index]}'

    verify_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Click to verify", url=links[output])],
        [InlineKeyboardButton("how to verify", url="https://t.me/nub_coder_updates/211")]
    ])

    await message.reply_text(
        "**Storage is limited to 200 MB for non verified users**\n"
        "you need to verify first in order to incrrase storage capacity\n\n"
        "This is only file to zip bot which gives 4.5 GB storage support to the user \n\n"
        "You can also use /premium to get many benifits including no ads",
        reply_markup=verify_button
    )

    if not premium_queue.empty():
        next_file = premium_queue.get()
        dd = dd - 1
        user_ids.clear()
        await download(next_file)
    elif not download_queue.empty():
        next_file = download_queue.get()
        dd = dd - 1
        user_ids.clear()
        await download(next_file)

@app.on_callback_query(filters.regex("no_password"))
async def without_pass(client, callback_query):
    pass_protect = None
    await callback_query.edit_message_text("starting without password")
    await create_zip(callback_query, pass_protect)

@app.on_callback_query(filters.regex("set_password"))
async def with_pass(client, callback_query):
    pass_protect = True
    await callback_query.edit_message_text("starting with password")
    await create_zip(callback_query, pass_protect)

@app.on_callback_query(filters.regex("cancel_download"))
async def cancel_download(client, callback_query):
    user_id = callback_query.from_user.id

    if user_id in user_ids:
        if not download_queue.empty():
            try:
                download_queue.queue.remove(callback_query)
            except:
                pass
        del user_ids[user_id]
        await callback_query.edit_message_text("Download canceled.")
    else:
        await callback_query.edit_message_text("No ongoing download to cancel.")

@app.on_message(filters.command("skip") & filters.regex("^!skip$"))
async def skip_handler(client, message):
    global dd, max_retry, zipping_in_progress, link_downloading, download_in_progress
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await message.reply_text("Admin command received. Skipping the task...")
                await timeout(message)

async def timeout(message):
    global dd, max_retry, zipping_in_progress, link_downloading, download_in_progress
    max_retry = 0
    zipping_in_progress = False
    link_downloading = False
    download_in_progress = False

    if not download_queue.empty():
        next_file = download_queue.get()
        dd = dd - 1
        user_ids.clear()
        await download(next_file)
    elif not link_download_queue.empty():
        next_link = link_download_queue.get()
        dd = dd - 1
        user_ids.clear()
        await link_download(next_link)

@app.on_message(filters.command("loud"))
async def loud_message(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    stored_user_ids = [user["user_id"] for user in collection.find()]
    xx = 0

    if message.reply_to_message:
        try:
            for user_id in stored_user_ids:
                try:
                    await message.reply_to_message.forward(user_id)
                    xx += 1
                except Exception as e:
                    print(f"Failed to forward message: {e}")
            await message.reply_text(f"Broadcasted to {xx} users")
        except Exception as e:
            print(f"Failed to forward message: {e}")

@app.on_message(filters.command("reboot"))
async def reboot_handler(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await message.reply_text("Admin command received. Stopping the bot...")
                os.system(f"kill -9 {os.getpid()}")
            else:
                await message.reply_text("You are not authorized to use this command.")
    else:
        await message.reply_text("Admin file not found. Please contact the bot admin.")

@app.on_message(filters.command("start"))
async def lstart(client, message):
    if message.text == "/start":
        user_id = message.from_user.id
        current_time = int(time.time())
        user_data = collection.find_one({"user_id": user_id})
        if not user_data:
            timestamp = int(time.time()) - 21600
            user_data = {"user_id": user_id, "timestamp": timestamp}
            collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

        await message.reply_text(
            "Hello! this is file to zip bot.\n"
            "Send me any files or direct download link and I will compress them to a zip\n"
            "/help to get more details",
            reply_markup=home_buttons
        )
        return

    print(message.text)
    user_id = message.from_user.id
    phases = ['phase1', 'phase2', 'phase3', 'phase4']
    current_datetime = datetime.datetime.now()
    current_hour = current_datetime.hour
    phase_index = (current_hour // 6) % 4
    day_name = current_datetime.strftime('%A')
    output = f'{day_name}_{phases[phase_index]}'

    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time
        if time_difference < 21600:
            return await message.reply_text("You are already verified")

    # Check verification codes
    if days_of_week[output] == message.text:
        store_user(user_id)
        await message.reply_text(
            "Welcome back to the bot! You are verified for 6 hours",
            reply_markup=home_buttons
        )
    elif user_data and "verifycode" in user_data:
        if f'verifycodeis{user_data["verifycode"]}' == message.text.split(' ')[1]:
            store_user(user_id)
            await message.reply_text(
                "Welcome back to the bot! You are verified for 6 hours",
                reply_markup=home_buttons
            )
        else:
            await message.reply_text("Wrong link, please try again")
            await link_send(message)
    else:
        await message.reply_text("Wrong link, please try again")
        await link_send(message)

@app.on_callback_query(filters.regex("bhad"))
async def callback_queue(client, callback_query):
    global dd, active_user_id, download_in_progress, time_left
    user_id = callback_query.from_user.id

    user_task_counts = {}

    for download_event in download_queue.queue:
        event_user_id = download_event.from_user.id
        if event_user_id in user_task_counts:
            user_task_counts[event_user_id] += 1
        else:
            user_task_counts[event_user_id] = 1

    for premium_event in premium_queue.queue:
        event_user_id = premium_event.from_user.id
        if event_user_id in user_task_counts:
            user_task_counts[event_user_id] += 1
        else:
            user_task_counts[event_user_id] = 1

    if active_user_id:
        response_text = f"ACTIVE USER ⚡: {active_user_id}\n\n\n"
    else:
        response_text = "No active downloads or uploads\n\n\n"

    response_text += "DOWNLOAD IN QUEUE:\n"
    for user_id, task_count in user_task_counts.items():
        response_text += f"{user_id}:({task_count} tasks)\n\n\n"
    response_text += f"\nNEXT QUEUE IN: {time_left} seconds"

    try:
        await callback_query.answer(response_text, show_alert=True)
    except Exception as e:
        await callback_query.answer(f"your current queue {dd}", show_alert=True)

@app.on_callback_query(filters.regex("help"))
async def callback_help(client, callback_query):
    await help_handler(callback_query)

@app.on_callback_query(filters.regex("my_files"))
async def callback_my_files(client, callback_query):
    await list_files(callback_query)

@app.on_callback_query(filters.regex("clear"))
async def callback_clear(client, callback_query):
    await clear(callback_query)

@app.on_callback_query(filters.regex("home"))
async def callback_home(client, callback_query):
    await start_handler(callback_query)

@app.on_callback_query(filters.regex("fzip"))
async def callback_fzip(client, callback_query):
    await check_pass(callback_query)

async def start_handler(callback_query):
    user_id = callback_query.from_user.id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
        timestamp = int(time.time()) - 21600
        user_data = {"user_id": user_id, "timestamp": timestamp}
        collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

    await callback_query.edit_message_text(
        "Hello! this is file to zip bot.\n"
        "Send me any files or direct download link and I will compress them to a zip\n"
        "/help to get more details",
        reply_markup=home_buttons
    )

async def list_files(event):
    user_id = event.from_user.id
    check_if = await is_user_on_chat(app, "@nub_coder_updates", user_id)

    if not check_if:
        button = InlineKeyboardMarkup([[InlineKeyboardButton("Join", url="https://t.me/nub_coder_updates")]])
        if hasattr(event, 'edit_message_text'):
            return await event.edit_message_text(
                "You need to join @nub_coder_updates in order to use this bot.\n\nClick below to Join!",
                reply_markup=button
            )
        else:
            return await event.reply_text(
                "You need to join @nub_coder_updates in order to use this bot.\n\nClick below to Join!",
                reply_markup=button
            )

    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size
    stored_time = user_data.get("timestamp", current_time)
    time_difference = current_time - stored_time

    if time_difference < 0:
        remaining_storage = 10 * 1024 * 1024 * 1024 - total_size

    files = os.listdir(user_dir)
    if files:
        file_entries = [
            f"{i+1}. {file} - {os.path.getsize(os.path.join(user_dir, file)) / (1024 * 1024):.2f} MB"
            for i, file in enumerate(files)
        ]
        total_size_mb = total_size / (1024 * 1024)
        remaining_storage_gb = remaining_storage / (1024 * 1024 * 1024)

        header = (
            f"Total storage used: {total_size_mb:.2f} MB\n"
            f"Remaining Storage: {remaining_storage_gb:.2f} GB\n\n"
            f"List of files in your directory:\n\n"
        )

        if not time_difference <= 21600:
            remaining_storage = 200 * 1024 * 1024 - total_size
            remaining_storage_mb = remaining_storage / 1024 / 1024
            header = (
                f"<b>Total storage used: {total_size_mb:.2f} MB</b>\n"
                f"<b>Remaining free Storage: {remaining_storage_mb:.2f} MB</b>\n\n"
                f"<b>List of files in your directory:</b>\n\n"
                f"<b>Use /del <number> to delete the file using file number in list:</b>\n\n"
            )

        messages = []
        current_message = header
        for entry in file_entries:
            if len(current_message) + len(entry) + 1 > 4096:
                messages.append(current_message)
                current_message = f"<blockquote>{entry}</blockquote>" + "\n"
            else:
                current_message += f"<blockquote>{entry}</blockquote>" + "\n"

        messages.append(current_message)

        for i, msg in enumerate(messages):
            try:
                if i == len(messages) - 1:
                    if hasattr(event, 'edit_message_text'):
                        await event.edit_message_text(msg, parse_mode="html", reply_markup=file_buttons)
                    else:
                        await event.reply_text(msg, parse_mode="html", reply_markup=file_buttons)
                else:
                    if hasattr(event, 'edit_message_text'):
                        await event.edit_message_text(msg, parse_mode="html")
                    else:
                        await event.reply_text(msg, parse_mode="html")
            except:
                if hasattr(event, 'edit_message_text'):
                    await event.edit_message_text(msg, parse_mode="html")
                else:
                    await event.reply_text(msg, parse_mode="html")
    else:
        message = "Your directory is empty, send me any file"
        try:
            if hasattr(event, 'edit_message_text'):
                await event.edit_message_text(message, reply_markup=nofile_buttons)
            else:
                await event.reply_text(message, reply_markup=nofile_buttons)
        except:
            if hasattr(event, 'edit_message_text'):
                await event.edit_message_text(message, reply_markup=nofile_buttons)
            else:
                await event.reply_text(message, reply_markup=nofile_buttons)

@app.on_message(filters.command("del"))
async def delete_file(client, message):
    user_id = str(message.from_user.id)
    user_dir = f"{ggg}/zipper/{user_id}"

    try:
        file_number = int(message.text.split('/del ')[1]) - 1
    except (IndexError, ValueError):
        return await message.reply_text("Invalid file number. Use /del <file_number> to delete a file.")

    if os.path.exists(user_dir):
        files = os.listdir(user_dir)
        if 0 <= file_number < len(files):
            file_to_delete = os.path.join(user_dir, files[file_number])
            os.remove(file_to_delete)
            return await message.reply_text(f"File '{files[file_number]}' has been deleted.")
        else:
            return await message.reply_text("Invalid file number. Use /del <file_number> to delete a file.")
    else:
        return await message.reply_text("Your directory doesn't exist. Send me any file to create your directory.")

@app.on_message(filters.command("clear"))
async def clear(client, message):
    user_directory = "zipper"
    user_id = str(message.from_user.id)
    user_path = os.path.join(user_directory, user_id)

    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
        os.makedirs(user_path, exist_ok=True)
        try:
            if hasattr(message, 'edit_message_text'):
                await message.edit_message_text(
                    f"All files and directories in your directory have been removed.",
                    reply_markup=back_buttons
                )
            else:
                await message.reply_text(
                    f"All files and directories in your directory have been removed.",
                    reply_markup=back_buttons
                )
        except:
            await message.reply_text(
                f"All files and directories in your directory have been removed.",
                reply_markup=back_buttons
            )
    else:
        try:
            if hasattr(message, 'edit_message_text'):
                await message.edit_message_text(f"Your directory does not exist.", reply_markup=back_buttons)
            else:
                await message.reply_text(f"Your directory does not exist.", reply_markup=back_buttons)
        except:
            await message.reply_text(f"Your directory does not exist.", reply_markup=back_buttons)

async def download(message):
    global active_user_id, download_in_progress, dd, stopper, max_retry, pinky
    fi_encoded = None
    size = 0

    user_id = message.from_user.id
    time_difference = 637474
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if not user_data:
        store_userr(user_id)

    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size
    remaining_free_storage = 200 * 1024 * 1024 - total_size
    stored_time = user_data["timestamp"]
    time_difference = current_time - stored_time

    if time_difference < 0:
        remaining_storage = 10 * 1024 * 1024 * 1024 - total_size

    if message.document:
        if message.document.file_size > 2500000000 and not time_difference < 0:
            return await message.reply_text(
                "Please send a file smaller than 2GB.\n/my_files to show your files",
                reply_markup=common_buttons
            )
        elif message.document.file_size > 3500000000:
            return await message.reply_text(
                "Please send a file smaller than 3GB.\n/my_files to show your files",
                reply_markup=common_buttons
            )
        size = message.document.file_size

    if message.photo:
        size = 100

    if size <= remaining_storage:
        if not size <= remaining_free_storage and not time_difference < 21600:
            return await link_send(message)

        timer = Timer()

        async def progress_bar(current, total, start_time=time.time()):
            if timer.can_send() and total != 0:
                global download_in_progress, time_left
                download_in_progress = True
                progress_percent = current * 100 / total
                filename = fi_encoded if fi_encoded else "file"
                progress_message = f"Downloading {filename}: {progress_percent:.2f}%\n"

                progress_bar_length = 30
                num_ticks = int(progress_percent / (100 / progress_bar_length))
                progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

                elapsed_time = time.time() - start_time
                speed = current / (elapsed_time * 1024 * 1024)
                progress_message += f"Speed: {speed:.2f} MB/s\n"

                time_left = (total - current) / (speed * 1024 * 1024) if speed != 0 else 0
                progress_message += f"Time left: {time_left:.2f} seconds\n"

                progress_message += f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

                progress_message += f"\n[{progress_bar_text}]"
                if not time_difference < 0:
                    progress_message += f"\n\n**Slow download?**, use /premium to boost download speed"

                message_text = f"{progress_message}"

                try:
                    if random.choices([True, False], weights=[1, 999])[0]:
                        await msg.edit_text(message_text, parse_mode='html')
                except Exception as e:
                    print(e)

        os.makedirs(user_dir, exist_ok=True)
        stopper += 1

        if not download_in_progress:
            user_ids[user_id] = True
            download_in_progress = True
            active_user_id = user_id
            await asyncio.sleep(5)

            try:
                msg = await message.reply_text("Downloading started")

                if message.document and message.document.file_name:
                    fi_encoded = message.document.file_name
                    file_path = os.path.join(user_dir, fi_encoded)
                else:
                    fi_encoded = f"file_{user_id}_{int(time.time())}"
                    file_path = os.path.join(user_dir, fi_encoded)

                await message.download(file_path, progress=progress_bar)
                await msg.edit_text("Finished downloading\n/my_files to see your files")

            except UserIsBlocked:
                return await timeout(message)
            except Exception as e:
                await msg.edit_text(f"Download failed: {e}\nPlease resend this file")
                download_in_progress = False

            download_in_progress = False

            if not premium_queue.empty():
                next_file = premium_queue.get()
                dd = dd - 1
                user_ids.clear()
                await download(next_file)
            elif not download_queue.empty():
                next_file = download_queue.get()
                dd = dd - 1
                user_ids.clear()
                await download(next_file)
            elif not link_download_queue.empty():
                next_link = link_download_queue.get()
                dd = dd - 1
                user_ids.clear()
                await link_download(next_link)
        else:
            dd += 1
            que = f'I have added your file in queue to download'
            if not time_difference < 0:
                que = f'I have added your file in queue to download\nYou can buy /premium to prioritise your download'

            if user_id not in user_ids:
                user_ids[user_id] = True
                queue_button = InlineKeyboardMarkup([[InlineKeyboardButton("check your queue", callback_data="bhad")]])
                await message.reply_text(que, reply_markup=queue_button)

            if time_difference < 0:
                premium_queue.put(message)
            else:
                download_queue.put(message)
    else:
        await message.reply_text("Not enough storage space to download this file.", reply_markup=common_buttons)

        if not premium_queue.empty():
            next_file = premium_queue.get()
            dd = dd - 1
            user_ids.clear()
            await download(next_file)
        elif not download_queue.empty():
            next_file = download_queue.get()
            dd = dd - 1
            user_ids.clear()
            await download(next_file)
        elif not link_download_queue.empty():
            next_link = link_download_queue.get()
            dd = dd - 1
            user_ids.clear()
            await link_download(next_link)

@app.on_message(filters.command("fzip"))
async def check_pass(client, message):
    return await message.reply_text(
        "Would you like to protect your zip file with a secure password ?",
        reply_markup=pass_button
    )

async def create_zip(callback_query, pass_protect=None):
    get_pass = None
    user_id = callback_query.from_user.id
    response = None

    try:
        await app.send_message(user_id, "Provide me a suitable filename for the zip file")
        response = await app.listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        if pass_protect:
            await app.send_message(user_id, "please type your password below.")
            get_pass = await app.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
            com = '--password'
        else:
            password = ''
            com = ''
        
    except Exception as e:
        await callback_query.message.reply_text(str(e))
        return

    global zipping_in_progress
    file_name = response.text

    if file_name.startswith("/") or file_name.startswith("http"):
        return

    check_if = await is_user_on_chat(app, "@nub_coder_updates", user_id)
    if not check_if:
        button = InlineKeyboardMarkup([[InlineKeyboardButton("Join", url="https://t.me/nub_coder_updates")]])
        return await callback_query.message.reply_text(
            "You need to join @nub_coder_updates in order to use this bot.\n\nClick below to Join!",
            reply_markup=button
        )

    user_dir = f"{ggg}/zipper/{user_id}"
    files = os.listdir(user_dir) if os.path.exists(user_dir) else []

    if not os.path.exists(user_dir) or not files:
        return await callback_query.message.reply_text(
            "you don't have files to zip\nSend your files first",
            reply_markup=back_buttons
        )

    if not file_name.endswith('.zip'):
        file_name = f'{file_name}.zip'

    zip_filename = os.path.join(user_dir, file_name)
    video_extensions = ['.mp4', '.avi', '.wmv', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp']
    video_files = [file for file in files if os.path.splitext(file)[1].lower() in video_extensions]

    global video_sent
    if video_files:
        video_sent = True

    try:
        message = await callback_query.message.edit_text("Compressing files to zip please wait")
    except:
        message = await callback_query.message.reply_text("Compressing files to zip please wait")

    zipping_in_progress = True

    for filename in os.listdir(user_dir):
        command = ['zip', com, password, zip_filename, os.path.join(user_dir, filename)] if pass_protect else ['zip', zip_filename, os.path.join(user_dir, filename)]
        output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for line in output.stdout:
            line = line.strip()
            if line:
                line = line.replace(f"zipper/{user_id}/", "")
                try:
                    await message.edit_text(line)
                except Exception as e:
                    print(e)

    if os.path.exists(zip_filename):
        file_size = os.path.getsize(zip_filename)
        await callback_query.message.reply_text('compression completed now uploading file')

        if file_size <= 2000000000:  # 2GB
            timer = Timer()

            async def progress_bar(current, total, start_time=time.time()):
                global time_left
                if timer.can_send():
                    progress_percent = current * 100 / total
                    progress_message = f"Uploading {zip_filename}: {progress_percent:.2f}%\n"

                    elapsed_time = time.time() - start_time
                    speed = current / (elapsed_time * 1024 * 1024)
                    progress_message += f"Speed: {speed:.2f} MB/s\n"

                    time_left = (total - current) / (speed * 1024 * 1024)
                    progress_message += f"Time left: {time_left:.2f} seconds"
                    progress_message += f"\nSize: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

                    progress_bar_length = int(progress_percent / 5)
                    progress_bar_text = "█" * progress_bar_length + "░" * (20 - progress_bar_length)

                    progress_message += f"\n[{progress_bar_text}]"

                    message_text = f"{progress_message}"

                    try:
                        if random.choices([True, False], weights=[1, 999])[0]:
                            await asyncio.sleep(1)
                            await msg.edit_text(message_text, parse_mode='html')
                    except Exception as e:
                        print(e)

            msg = await callback_query.message.reply_text("uploading started")

            await app.send_document(
                callback_query.message.chat.id,
                zip_filename,
                caption="zip by @FILEs_COMPRESSOR_BOT",
                progress=progress_bar
            )

            await msg.edit_text('Uploaded successfully\n\nPlease join @nub_coder_s', reply_markup=home_buttons)

            user_data = collection.find_one({})
            if user_data:
                is_ad = user_data.get('is_ad', "false")
                ad = user_data.get('ad')
                if ad and is_ad == 'true':
                    await callback_query.message.reply_text(ad)

            if os.path.exists(user_dir):
                shutil.rmtree(user_dir, ignore_errors=True)
                os.makedirs(user_dir, exist_ok=True)

        elif file_size <= 5000000000:  # 5GB - upload to gofile.io
            import requests

            url = "https://api.gofile.io/servers"
            response = requests.get(url)
            data = response.json()
            servers = data["data"]["servers"][0]
            server = servers['name']

            if not server:
                return await callback_query.message.reply_text(
                    "No storage available in gofile.io please try again later:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Download File", url="download_url")]])
                )

            zipping_in_progress = False
            video_sent = False

            if file_size > 5000000000:
                await callback_query.message.reply_text(
                    "File size is too large to upload here. Please use an alternative method.",
                    reply_markup=back_buttons
                )
                return

            message = await callback_query.message.reply_text('Compression completed. Uploading file...')
            transfer_url = f"https://{server}.gofile.io/uploadFile"

            try:
                command = ["curl", "-F", f"file=@{zip_filename}", transfer_url]
                start_time = time.time()
                output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

                for line in output.stdout:
                    line = line.strip()
                    if line:
                        print(line)

                text = line
                start_index = text.find("https://gofile.io")
                end_index = text.find('"', start_index)
                link = text[start_index:end_index]

                try:
                    download_button = InlineKeyboardMarkup([[InlineKeyboardButton("Download File", url=link)]])
                    await message.edit_text(
                        f"Not able to upload files more than 2GB here\nSo I provided this download link:",
                        reply_markup=download_button
                    )

                    user_data = collection.find_one({})
                    if user_data:
                        is_ad = user_data.get('is_ad', "false")
                        ad = user_data.get('ad')
                        if ad and is_ad == 'true':
                            await callback_query.message.reply_text(ad)

                    zipping_in_progress = False

                except Exception as e:
                    print(f"Error sending link: {link}, Error: {e}")

            except subprocess.CalledProcessError as e:
                print(e)
                await start_handler(callback_query)

            try:
                os.remove(zip_filename)
            except OSError as e:
                print(e)

            if os.path.exists(user_dir):
                shutil.rmtree(user_dir, ignore_errors=True)
            os.makedirs(user_dir, exist_ok=True)
            zipping_in_progress = False

@app.on_message(filters.command("help"))
async def help_handler(client, message):
    help_message = (
        "🤖 File Compression Bot Help 🤖\n\n"
        "This bot allows you to compress files into zip archives and manage your files.\n\n"
        "📋 Available Commands:\n"
        "<blockquote>/start - Start the bot</blockquote>\n"
        "<blockquote>/my_files - List your files</blockquote>\n"
        "<blockquote>/clear - Clear your files</blockquote>\n"
        "<blockquote>/fzip - Compress files into a zip archive</blockquote>\n"
        "<blockquote>/help - Show this help message</blockquote>\n"
        "<blockquote>/premium - Show premium features</blockquote>\n\n"
        "🚧 Limitations for non-premium users:\n"
        "<blockquote>- Maximum file size for compression: 2GB</blockquote>\n"
        "<blockquote>- Maximum storage per user: 4GB</blockquote>\n\n"
        "📞 Support:\n"
        "<blockquote>If you need assistance or have any questions, please contact the bot admin.</blockquote>\n"
        f"Admin : @nub_coder_s\n\n"
        "Enjoy using the bot! 🚀"
    )

    if hasattr(message, 'edit_message_text'):
        await message.edit_message_text(help_message, parse_mode="html", reply_markup=common_buttons)
    else:
        await message.reply_text(help_message, parse_mode="html", reply_markup=common_buttons)

async def link_download(message):
    link = message.text
    user_id = message.from_user.id
    current_time = int(time.time())
    time_difference = 7373737
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time

    user_dir = f"zipper/{user_id}"
    user_dir = f"{ggg}/zipper/{user_id}"
    download_directory = user_dir
    os.makedirs(user_dir, exist_ok=True)

    max_file_size_bytes = 4 * 1024 * 1024 * 1024
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size
    remaining_free_storage = 200 * 1024 * 1024 - total_size
    timer = Timer()

    async def progress_bar(current, total, start_time, msg, filename):
        if timer.can_send() and total != 0:
            progress_percent = current * 100 / total
            progress_message = f"Downloading {filename}: {progress_percent:.2f}%\n"

            progress_bar_length = 30
            num_ticks = int(progress_percent / (100 / progress_bar_length))
            progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

            elapsed_time = time.time() - start_time
            speed = current / (elapsed_time * 1024 * 1024)
            progress_message += f"Speed: {speed:.2f} MB/s\n"

            time_left = (total - current) / (speed * 1024 * 1024) if speed != 0 else 0
            progress_message += f"Time left: {time_left:.2f} seconds\n"

            progress_message += f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

            progress_message += f"\n[{progress_bar_text}]"

            message_text = f"{progress_message}"
            try:
                if random.choices([True, False], weights=[1, 999])[0]:
                    await asyncio.sleep(1)
                    await msg.edit_text(message_text, parse_mode='html')
            except Exception as e:
                print(e)

    try:
        response = requests.head(link)
        if "content-length" in response.headers:
            content_length = int(response.headers["content-length"])
            if content_length <= remaining_storage:
                if not content_length <= remaining_free_storage and not time_difference < 21600:
                    return await link_send(message)

                filename = link.split('/')[-1]
                message_obj = await message.reply_text(f"Downloading {filename}\nFile size: {content_length} bytes\nStarting download")

                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:
                            with open(os.path.join(download_directory, filename), "wb") as f:
                                while True:
                                    chunk = await resp.content.read(1024)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    current_size = os.path.getsize(os.path.join(download_directory, filename))
                                    await progress_bar(current_size, content_length, start_time, message_obj, filename)
                                await message_obj.edit_text(f"File {filename} downloaded successfully\n/my_files to check all your files")
                        else:
                            await message.reply_text("Download failed. Please check the URL.")
        else:
            await message.reply_text("Content length not found in headers. Cannot determine file size.")
    except Exception as e:
        await message.reply_text(str(e))

@app.on_message(filters.command("premium"))
async def premium_info(client, message):
    premium_benefits = """
    Premium Benefits:
<blockquote>- Per file size limit increased to 3GB.
- Storage limit increased to 10GB.
- No ads for 30 days.
- Priority downloads.
- fast downloads and uploads.</blockquote>

    Get Premium for just ₹50 (approximately $0.6).

    Contact any admin to get premium.
    """
    contact_button = InlineKeyboardMarkup([[InlineKeyboardButton("Contact Admin", url="https://t.me/nub_coder_s")]])
    await message.reply_text(premium_benefits, parse_mode="html", reply_markup=contact_button)

@app.on_message(filters.command("status"))
async def user_status(client, message):
    user_id = message.from_user.id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference = stored_time - current_time

        if time_difference > 0:
            status = "💎 Premium 💎"
            total_storage = "10 GB"
            file_size = "3.2 GB"
            ads = "✨ No ads! ✨"
        elif time_difference >= -21600:
            status = "🌟 Elite 🌟"
            total_storage = "4.5 GB"
            file_size = "2 GB"
            ads = "Some ads"
            time_difference *= -1
        else:
            status = "Not Verified"
            total_storage = "200MB"
            file_size = "200MB"
            ads = "No ads upto 200MB"

        if status in ("💎 Premium 💎", "🌟 Elite 🌟"):
            days = time_difference // (24 * 3600)
            time_difference %= (24 * 3600)
            hours = time_difference // 3600
            time_difference %= 3600
            minutes = time_difference // 60
            status_message = f"""
            *✨ Your Status ✨*

            ⏳ Time left: {days} days, {hours} hours, {minutes} minutes
            👑 Status: {status}
            📦 Total Storage: {total_storage}
            📄 File Size Limit: {file_size}
            🚫 Ads: {ads}
            """
        else:
            status_message = f"""
            * 😔 Your Status 😔*

            👑 Status: {status}
            📦 Total Storage: {total_storage}
            📄 File Size Limit: {file_size}
            🚫 Ads: {ads}
            """
    else:
        status_message = "You are Not Verified"

    await message.reply_text(status_message)

@app.on_message(filters.command("rst"))
async def unauthorize_user(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    if message.reply_to_message:
        if message.reply_to_message.from_user.id is not None:
            user_id = message.reply_to_message.from_user.id
        else:
            return await message.reply_text("Cannot authorize user: Unknown user ID.")

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                user_entity = await app.get_users(arg)
                user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    timestamp = int(time.time()) - 12600
    storre_user(user_id, timestamp)
    user_data = collection.find_one({"user_id": user_id})
    await message.reply_text(f"User resetted successfully.\nUserdata:{user_data}")

@app.on_message(filters.command("authorize"))
async def authorize_user(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    if message.reply_to_message:
        if message.reply_to_message.from_user.id is not None:
            user_id = message.reply_to_message.from_user.id
        else:
            return await message.reply_text("Cannot authorize user: Unknown user ID.")

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                user_entity = await app.get_users(arg)
                user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    timestamp = int(time.time()) + (30 * 24 * 60 * 60)
    storre_user(user_id, timestamp)
    user_data = collection.find_one({"user_id": user_id})
    await message.reply_text(f"User authorized successfully.\nUserdata:{user_data}")

def storre_user(user_id, timestamp):
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)

@app.on_message(filters.command("users"))
async def list_users(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    user_ids = [str(user["user_id"]) for user in collection.find()]
    if user_ids:
        user_list = "\n".join(user_ids)
        user_list += f"\nTotal users: {str(len(user_ids))}"
        chunk_size = 4000
        chunks = [user_list[i:i+chunk_size] for i in range(0, len(user_list), chunk_size)]
        for chunk in chunks:
            await message.reply_text(chunk)
    else:
        await message.reply_text("No users found.")

@app.on_message(filters.command("set"))
async def set_handler(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    input_text = message.text.split('/set ')[1]
    value = input_text.strip()
    collection.update_one({}, {"$set": {'ad': value}}, upsert=True)
    await message.reply_text('Value saved successfully!')

@app.on_message(filters.command("ad"))
async def ad_handler(client, message):
    user_id = message.from_user.id

    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    is_ad_value = message.text.split()[1]
    collection.update_one({}, {"$set": {'is_ad': is_ad_value}}, upsert=True)
    await message.reply_text(f'Updated "is_ad" field with: {is_ad_value}')

@app.on_message(filters.command("get"))
async def get_handler(client, message):
    result = collection.find_one({})
    if result:
        value = result['ad']
        await message.reply_text(f'The value is: {value}')
    else:
        await message.reply_text('No value found')

@app.on_message(filters.private & (filters.document | filters.photo))
async def handle_media(client, message):
    if not download_queue.empty() or not premium_queue.empty():
        await asyncio.sleep(5)
    await download(message)

@app.on_message(filters.private & filters.text & ~filters.command(["start", "help", "my_files", "clear", "del", "fzip", "premium", "status", "rst", "authorize", "users", "set", "ad", "get", "loud", "reboot", "skip"]))
async def handle_links(client, message):
    if message.text.startswith("http"):
        await link_download(message)

if __name__ == "__main__":
    print("Bot starting...")
    app.run()