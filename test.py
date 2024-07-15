import uvloop
import urllib3
urllib3.disable_warnings()
from fp.fp import FreeProxy
import random
import os
import certifi
from pyrogram import Client as dint
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import subprocess
import shutil
import requests
import hashlib
import aiohttp
ggg=os.getcwd()
import datetime
import pymongo
import time
from config import *
from telethon.errors.rpcerrorlist import UserIsBlockedError
from tools import is_user_on_chat
client = pymongo.MongoClient("mongodb+srv://ankitkr23835:air8858@cluster0.cxh2ryf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",tlsCAFile=certifi.where())
db = client["telegram_bot"]
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

def store_code(user_id,verifycode):
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

# Get the current date and time
current_time = datetime.datetime.now()
print(f"Current Date and Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Iterate over all sub-directories
'''for dirpath, dirnames, filenames in os.walk(current_dir):
    # Get the creation time of the latest file in each sub-directory
    latest_file_creation_time = 0
    for filename in filenames:
        file_path = os.path.join(dirpath, filename)
        file_creation_time = os.path.getctime(file_path)
        if file_creation_time > latest_file_creation_time:
            latest_file_creation_time = file_creation_time

    # Calculate the time difference
    if latest_file_creation_time > 0:
        time_difference = current_time - datetime.datetime.fromtimestamp(latest_file_creation_time)
        # Print the time difference in a human-readable format
        print(f"Directory: {dirpath}, Updated {time_difference} ago")

        # Delete files that are 3 days old or older (except in current_dir)
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            file_creation_time = os.path.getctime(file_path)
            
            # Skip deletion for files in current_dir
            if (current_time - datetime.datetime.fromtimestamp(file_creation_time)).days >= 3 and dirpath != current_dir:
                os.remove(file_path)
                print(f"Deleted file: {file_path}")'''


import cryptg
import requests
import asyncio
import subprocess
import shutil

from telethon import events, Button, utils
from telethon.sync import TelegramClient
from telethon.tl import types, functions
from FastTelethon import download_file, upload_file
import sys  # Import the sys module at the beginning of your code

# Directory path
api_id = API_ID
api_hash = API_HASH
token = BOT_TOKEN
admin = 6476862483 # Replace with the actual admin user ID
time.sleep(2)
dex="zipper/duo"
app=dint('name',api_id=API_ID,api_hash=API_HASH,bot_token=BOT_TOKEN,in_memory=True)
client = TelegramClient(None, api_id, api_hash)
@client.on(events.NewMessage(pattern='^!skip$'))
async def skip_handler(event):
    global dd
    user_id = event.sender_id
    global link_downloading
    global download_in_progress
    global zipping_in_progress

    # Check if the user is an admin by comparing their user ID with the ones in /home/u219967/Work/Work/Work/zipper//home/u219967/Work/zipper/admin.txt
    admin_file =f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await event.respond("Admin command received. Skipping the task...")
                await timeout(event)



async def timeout(event):
    global dd
    global max_retry
    max_retry=0
    user_id = event.sender_id
    global zipping_in_progress
    global link_downloading
    global download_in_progress
    zipping_in_progress=False
    link_downloading = False
    download_in_progress = False
    if not download_queue.empty():

                 next_file = download_queue.get()
                 dd=dd-1
                 user_ids.clear()
                 await download(next_file)
    elif not link_download_queue.empty():
                 next_link = link_download_queue.get()
                 dd=dd-1
                 user_ids.clear()
                 await link_download(next_link)
def read_chat_ids_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            chat_ids = file.readlines()
            chat_ids = [chat_id.strip() for chat_id in chat_ids]
            return chat_ids
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

# Path to your /home/u219967/Work/Work/Work/zipper//home/u219967/Work/Work/zipper/user.txt file
file_path = f'{ggg}/zipper/user.txt'

# Define event handler for /loud command
@client.on(events.NewMessage(pattern='/loud'))
async def loud_message(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Get all stored user IDs from MongoDB
    stored_user_ids = [user["user_id"] for user in collection.find()]
    xx=0
    if event.is_reply:
        try:
            reply_message = await event.get_reply_message()
            if reply_message:
                for user_id in stored_user_ids:
                    try:
                        await client.forward_messages(user_id, reply_message)
                        xx+=1
                    except Exception as e:
                        print(f"Failed to forward message: {e}")
                    await event.respond(f"Broadcasted to {xx} users")
        except Exception as e:
            print(f"Failed to forward message: {e}")




@app.on_message(filters.command("reboot", prefixes="!"))
async def reboot_handler(client, message):
    user_id = message.from_user.id

    # Check if the user is an admin by comparing their user ID with the ones in /home/u219967/Work/Work/Work/zipper//home/u219967/Work/zipper/admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await message.reply_text("Admin command received. Stopping the bot...")
                sys.exit(0)  # Raise a system exit exception to stop the entire code
            else:
                await message.reply_text("You are not authorized to use this command.")
    else:
        await message.reply_text("Admin file not found. Please contact the bot admin.")

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
uuser_ids={}
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
# Define the common button layout
help_button = Button.inline("❓ Help", b"help")  # Define the "Help" button
mesaage=None
clear_buttons = [Button.inline("🏠 Home", b"home")]
cancel_download_button = Button.inline("❌ Cancel Download", b"cancel_download")
common_buttons = [
    [   Button.inline("🗂️ List My Files", b"my_files"),
        Button.inline("❌ Clear My Files", b"clear"),
    ],
    [
        Button.inline("🏠 Home", b"home"),
        Button.inline("🗜️📑 Compress files", b"fzip"),
    ],
    [help_button],  # Add the "Help" button
]

home_buttons = [
    [
        Button.inline("🗂️ List My Files", b"my_files"),
        Button.inline("❌ Clear My Files", b"clear"),
    ],
    [help_button],  # Add the "Help" button
]

back_buttons = [Button.inline("🏠 Home", b"home"), help_button]  # Add the "Help" button

file_buttons = [
    [
        Button.inline("❌ Clear My Files", b"clear"),
        Button.inline("🏠 Home", b"home"),
    ],
    [
        Button.inline("📑 Compress files", b"fzip"),
        help_button,  # Add the "Help" button
    ],
]
nofile_buttons = [
    [
        Button.inline("❌ Clear My Files", b"clear"),
        Button.inline("🏠 Home", b"home"),                                                                                ],
[        help_button,  # Add the "Help" button
    ],

]

@client.on(events.CallbackQuery(data=b'cancel_download'))
async def cancel_download(event):
    user_id = event.sender_id

    # Check if the user has an ongoing download                                                                           
    if user_id in user_ids:
        # Remove the user from the queue                                                                                      
        if not download_queue.empty():
            download_queue.queue.remove(event)                                                                                
# Reset the user's download status
        del user_ids[user_id]
        # Respond with a cancellation message
        await event.edit("Download canceled.")
    else:
        await event.edit("No ongoing download to cancel.")


import random
import string

def generate_random_code(length=10):
  """Generates a random 10-digit code combining letters and numbers."""
  characters = string.ascii_letters + string.digits
  code = ''.join(random.choice(characters) for i in range(length))
  return code

async def liink_send(event):
    global dd
    headers = {'User-Agent': 'Mozilla/5.0'}

# Get the current date and time Define the phases for each day Calculate the current phase based on the time of day
    import requests
    code = generate_random_code()
    print(code)
    store_code(event.sender_id,code)
    long=f'http://t.me/FILEs_COMPRESSOR_BOT?start=verifycodeis{code}'
    url = f'https://api.cuty.io/quick?token=b09763cdea0deb0cc373ca5eb&url={long}'
# Send an HTTP GET request and get the JSON response
    response = requests.get(url,proxies={'https': FreeProxy().get()},verify=False)
    data = response.json()

# Print the result
    print(data)
    print(data["shortenedUrl"])
    await event.respond("you need to verify first in order to use the bot to avoid spam\n\nThis is only file to zip bot which gives 4.5 GB storage support to the user \n\nYou can also use /premium to get many benifits including no ads",buttons=[Button.url("Click to verify",data["shortenedUrl"]),Button.url("how to verify","https://t.me/nub_coder_s_updates/3")])
    if not premium_queue.empty():

                next_file = premium_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
    elif not download_queue.empty():

                next_file = download_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
async def link_send(event):
    global dd
# Get the current date and time
# Define the phases for each day
    phases = ['phase1', 'phase2', 'phase3', 'phase4']
# Get the current day and time
    current_datetime = datetime.datetime.now()

# Calculate the current phase based on the time of day
    current_hour = current_datetime.hour
    phase_index = (current_hour // 6) % 4  # 6 hours per phase, modulo 4 to cycle through phases

# Get the name of the current day
    day_name = current_datetime.strftime('%A')

# Combine the day name and phase
    output = f'{day_name}_{phases[phase_index]}'
# Print the result
    await event.respond("**Storage is limited to 200 MB for non verified users**\nyou need to verify first in order to incrrase storage capacity\n\nThis is only file to zip bot which gives 4.5 GB storage support to the user \n\nYou can also use /premium to get many benifits including no ads",buttons=[Button.url("Click to verify",links[output]),Button.url("how to verify","https://t.me/nub_coder_s_updates/3")])
    if not premium_queue.empty():

                next_file = premium_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
    elif not download_queue.empty():

                next_file = download_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)


@client.on(events.NewMessage(pattern='/start'))
async def lstart(event):
    if event.raw_text=="/start":
        return
    print(event.raw_text)
    user_id = event.sender_id
    current_time = time.time()
# Get the current day of the week
    phases = ['phase1', 'phase2', 'phase3', 'phase4']

# Get the current day and time
    current_datetime = datetime.datetime.now()

# Calculate the current phase based on the time of day
    current_hour = current_datetime.hour
    phase_index = (current_hour // 6) % 4  # 6 hours per phase, modulo 4 to cycle through phases

# Get the name of the current day
    day_name = current_datetime.strftime('%A')

# Combine the day name and phase
    output = f'{day_name}_{phases[phase_index]}'
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time
        if time_difference < 21600:  # 6 hours in seconds
         return await event.respond("You are already verified")
    # Check if the user's message contains the special start link
    if days_of_week[output] == event.raw_text:
            # Add the new user ID with an expiration time of 1 day (86400 seconds)
        store_user(user_id)

            # Send a welcome message to the new user
        await event.respond("Welcome back to the bot! You are verified for 6 hours",buttons=home_buttons)

            # User already exists, check if their expiration time has passed

    if  days_of_week[output] != event.raw_text:
        await event.respond("Wrong link, please try again")
        await link_send(event)
                # User exists and their access is still valid
# ...
active_user_id =None
#@client.on(events.NewMessage(incoming=True, pattern='/start',func=lambda e: e.is_private))
async def lhhstart(event):
    if event.raw_text=="/start":
        return
    print(event.raw_text)
    user_id = event.sender_id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time
        if time_difference < 21600:  # 6 hours in seconds
         return await event.respond("You are already verified")
    # Check if the user's message contains the special start link
    print(user_data["verifycode"])
    if f'verifycodeis{user_data["verifycode"]}'  == event.raw_text.split(' ')[1]:
            # Add the new user ID with an expiration time of 1 day (86400 seconds)
        store_user(user_id)

            # Send a welcome message to the new user
        await event.respond("Welcome back to the bot! You are verified for 6 hours",buttons=home_buttons)

            # User already exists, check if their expiration time has passed

    else:
        await event.respond("Wrong link, please try again")
        await link_send(event)
                # User exists and their access is still valid
# ...
active_user_id =None
# ...
@client.on(events.CallbackQuery(data=b'bhad'))
async def callback_queue(event):
    global dd
    global active_user_id
    global download_in_progress
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.t$
    admin_file = f"{ggg}/zipper/admin.txt"
    if 2==2:
                user_task_counts = {}

    # Iterate through the events in the download queue and count tasks per user
                for download_event in download_queue.queue:
                    user_id = download_event.sender_id

                    if user_id in user_task_counts:
                        user_task_counts[user_id] += 1
                    else:
                        user_task_counts[user_id] = 1

    # Iterate through the events in the link download queue and update counts
                for premium_event in premium_queue.queue:
                    user_id = premium_event.sender_id
                    if user_id in user_task_counts:
                        user_task_counts[user_id] += 1
                    else:
                        user_task_counts[user_id] = 1
                if active_user_id:
                    response_text = f"ACTIVE USER ⚡: {active_user_id}\n\n\n"
                else:
                    response_text = "No active downloads or uploads\n\n\n"

                response_text += "DOWNLOAD IN QUEUE:\n"
                for user_id, task_count in user_task_counts.items():
                    response_text += f"{user_id}:({task_count} tasks)\n\n\n"
                response_text += f"\nNEXT QUEUE IN: {time_left} seconds"
                try:
                    await event.answer(response_text, alert=True)
                except Exception as e:
                    await event.answer(f"your current queue {dd}", alert=True)
                start_time = time.time()
                last_time_left = time_left 
                while time.time() - start_time < 600:  # Check for 1 minute
                 if time_left == last_time_left:
                    if time.time() - start_time >= 180:  # 30 seconds without change
                       global download_in_progress
                       download_in_progress = False
                       print("time_left unchanged for 30 seconds. Setting downloading to False.")
                       break  # Exit the loop
                    else:
                       last_time_left = time_left  # Update last known time_left

                await asyncio.sleep(1)  # Check every second

@client.on(events.CallbackQuery(data=b'help'))
async def callback_help(event):
    await event.delete()
    await help_handler(event)

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/start'))
async def start(event):
    user_id = event.sender_id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
     timestamp = int(time.time())
     timestamp=timestamp-21600
     user_data = {"user_id": user_id, "timestamp": timestamp}
     collection.update_one({"user_id": user_id},{'$set': user_data}, upsert=True)
    # Check
    await event.respond(
            "Hello! this is file to zip bot.\nSend me any files or direct download link  and I will compress them to a zip\n/help to get more details",
            buttons=home_buttons)

@client.on(events.CallbackQuery(data=b'my_files'))
async def callback_my_files(event):
    await list_files(event)

@client.on(events.CallbackQuery(data=b'clear'))
async def callback_clear(event):
    await clear(event)

@client.on(events.CallbackQuery(data=b'home'))
async def callback_home(event):
    await event.delete()
    await start(event)

# Define a dictionary to store user states
user_states = {}

# ...

@client.on(events.CallbackQuery(data=b'fzip'))
async def callback_fzip(event):
    user_id = event.sender_id
    current_time = int(time.time())
       #await event.respond("you need to verify first in order to use the bot to avoid spam",buttons=[Button.url("Click to verify",links[Today]),Button.url("how to verify","https://t.me/nub_coder_s_updates/3")])
    user_states[user_id] = "waiting_for_rename"  # Set the user's state to "waiting_for_rename"
    try:
        await event.edit("Please give me a suitable name for the compressed file.\n\nNote: name should contain extension also")
    except:
        await event.respond("Please give me a suitable name for the compressed file.\n\nNote: name should contain extension also")
# ...

@client.on(events.NewMessage(func=lambda e: e.text and e.is_private))
async def handle_message(event):
    user_id = event.sender_id
    user_state = user_states.get(user_id)

    if user_state == "waiting_for_rename":
        user_states[user_id] = "ready"  # Reset the user's state
        global file_name
        file_name = event.text
        await create_zip(event)  # Call the create_zip function to proceed with compression
    else:
        # Handle other messages or commands here
        pass







@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/my_files'))
async def list_files(event):
    user = await event.get_sender()
    user_id = user.id
    check_if = await is_user_on_chat(client, "@treaserthings", user_id)
    
    '''if not check_if:
        button = Button.url("Join", "https://t.me/treaserthings")
        return await event.respond(
            "You need to join @treaserthings in order to use this bot.\n\nClick below to Join!", 
            buttons=button)'''

    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size  # 4.5GB in bytes
    stored_time = user_data.get("timestamp", current_time)
    time_difference = current_time - stored_time

    if time_difference < 0:
        remaining_storage = 10 * 1024 * 1024 * 1024 - total_size  # 10GB in bytes

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
            f"<b>List of files in your directory:</b>\n\n")


        messages = []
        current_message = header
        for entry in file_entries:
            if len(current_message) + len(entry) + 1 > 4096:  # +1 for newline
                messages.append(current_message)
                current_message = f"<blockquote>{entry}</blockquote>" + "\n"
            else:
                current_message += f"<blockquote>{entry}</blockquote>" + "\n"

        messages.append(current_message)  # Add the last accumulated message

        for i, msg in enumerate(messages):
            try:
                if i == len(messages) - 1:
                    await event.respond(msg, parse_mode="html", buttons=file_buttons)
                else:
                    await event.respond(msg, parse_mode="html")
            except:
                await event.respond(msg, parse_mode="html")
    else:
        message = "Your directory is empty, send me any file"
        try:
            await event.edit(message, buttons=nofile_buttons)
        except:
            await event.respond(message, buttons=nofile_buttons)


#@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/my_files'))
async def lillst_files(event):
    user = await event.get_sender()
    user_id = user.id
    check_if = await is_user_on_chat(client, "@treaserthings", event.sender_id)
    '''if not check_if:
        button = Button.url("Join", "https://t.me/treaserthings")
        return await event.respond("You need to join @treaserthings in order to use this bot.\n\nClick below to Join!", buttons=button)'''

    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    user_dir = f"{ggg}/zipper/{user_id}"
    #user_path = os.path.join(user_directory, user_id)
    os.makedirs(user_dir, exist_ok=True)
    # Calculate the remaining storage space
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size  # 3GB in bytes
    stored_time = user_data["timestamp"]
    time_difference = current_time - stored_time

    user_id = str(event.sender_id)
    user_dir = f"zipper/{user_id}"
    user_dir = f"{ggg}/zipper/{user_id}"

    if os.path.exists(user_dir):
        files = os.listdir(user_dir)
        if files:
            total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in files)
            total_size2 = round((total_size / (1024 * 1024)), 3)
            remaining_storage = (4.5 * 1024 * 1024 * 1024) - total_size  # 4GB in bytes
            if time_difference < 0:
              remaining_storage = (10 * 1024 * 1024 * 1024) - total_size  # 4GB in b

            file_list = "\n".join([f"{i+1}. {file} - {os.path.getsize(os.path.join(user_dir, file)) / (1024 * 1024):.2f} MB" for i, file in enumerate(files)])
            response_message = f"List of files in your directory:\n\n{file_list}\n\nTotal storage used: {total_size2} MB\nRemaining Storage: {remaining_storage / (1024 * 1024 * 1024):.2f} GB"
            try:
                await event.edit(response_message, buttons=file_buttons)
            except:
                await event.respond(response_message, buttons=file_buttons)
        else:
            try:
                await event.edit("Your directory is empty, send me any file", buttons=nofile_buttons)
            except:
                await event.respond("Your directory is empty, send me any file", buttons=nofile_buttons)
    else:
        try:
            await event.edit("Your directory doesn't exist, send me any file to create your directory", buttons=nofile_buttons)

        except:
            await event.respond("Your directory doesn't exist, send me any file to create your directory", buttons=nofile_buttons)


@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text.startswith('/del ')))
async def delete_file(event):
    user_id = str(event.sender_id)
    user_dir = f"{ggg}/zipper/{user_id}"

    # Extract the file number from the message
    try:
        file_number = int(event.raw_text.split('/del ')[1]) - 1  # Adjust for 0-based indexing
    except (IndexError, ValueError):
        return await event.respond("Invalid file number. Use /del <file_number> to delete a file.")

    if os.path.exists(user_dir):
        files = os.listdir(user_dir)
        if 0 <= file_number < len(files):
            file_to_delete = os.path.join(user_dir, files[file_number])
            os.remove(file_to_delete)
            # Notify the user that the file has been deleted
            return await event.respond(f"File '{files[file_number]}' has been deleted.")
        else:
            return await event.respond("Invalid file number. Use /del <file_number> to delete a file.")
    else:
        return await event.respond("Your directory doesn't exist. Send me any file to create your directory.")

# ... (other handlers and code)

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/clear'))
async def clear(event):
    user_directory ="zipper"
    user_id = str(event.sender_id)
    user_path = os.path.join(user_directory, user_id)

    if os.path.exists(user_path):
        shutil.rmtree(user_path,ignore_errors=True)  # Recursively remove the entire directory
        os.makedirs(user_path, exist_ok=True)  # Recreate the directory
        try:
            await event.edit(f"All files and directories in your directory have been removed.", buttons=back_buttons)
        except:
             await event.respond(f"All files and directories in your directory have been removed.", buttons=back_buttons)
    else:
        try:
            await event.edit(f"Your directory does not exist.", buttons=back_buttons)
        except:
            await event.respond(f"Your directory does not exist.", buttons=back_buttons)
uvloop.install()
client.flood_sleep_threshold = 24*60*60
client.start(bot_token=token)

config = client(functions.help.GetConfigRequest())
for option in config.dc_options:
    if option.ip_address == client.session.server_address:
        if client.session.dc_id != option.id:
            log.warning(f"Fixed DC ID in session from {client.session.dc_id} to {option.id}")
        client.session.set_dc(option.id, option.ip_address, option.port)
        client.session.save()
        break

class Timer:
    def __init__(self, time_between=2):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        if time.time() > (self.start_time + self.time_between):
            self.start_time = time.time()
            return True
        return False
time_left=0
stopper=0
# Store user state to track when to downlo
import queue  # Import the queue module
dd=0
# Create a queue to manage the download queue
download_queue = queue.Queue()
premium_queue = queue.Queue()
user1=None
user2=None
user3=None
user4=None
user5=None
max_retry=0
zipping_in_progress = False
# Define a flag to indicate if a download process is ongoing
download_in_progress = False
user_ids = {}
link_download_queue = queue.Queue()
link_downloading = False  # Flag to track if a link download is in progress





@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def main(event):
    if event.raw_text.startswith("http"):
        await link_download(event)
    elif event.media or event.document:
        if not download_queue.empty() or not premium_queue.empty():
           await asyncio.sleep(5)
        await download(event)
pinky=1
async def download(event):
    global active_user_id
    global download_in_progress  # Use a global flag to track download process
    global dd
    global user1
    global stopper
    global user2
    global user3
    global message
    global edit
    global max_retry
    global pinky
    fi_encoded=None
    size=0

    user_id = event.sender_id
    time_difference = 637474
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
        store_userr(user_id)
    user_dir = f"{ggg}/zipper/{user_id}"
    #user_path = os.path.join(user_directory, user_id)
    os.makedirs(user_dir, exist_ok=True)
    # Calculate the remaining storage space
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size  # 3GB in bytes
    remaining_free_storage = 200 * 1024 * 1024 - total_size
    stored_time = user_data["timestamp"]
    time_difference = current_time - stored_time
    if time_difference < 0:
        remaining_storage = 10 * 1024 * 1024 * 1024 - total_size  # 10GB in bytes
    if event.document:
        if event.document.size > 2500000000 and not time_difference < 0:
            return await event.reply("Please send a file smaller than 2GB.\n/my_files to show your files",buttons=common_buttons)
        elif event.document.size > 3500000000:
            return await event.reply("Please send a file smaller than 3GB.\n/my_files to show your files",buttons=common_buttons)
        docs=event.document
        size=event.document.size
    if event.photo:
        docs=event.media

        size=100
    if size<=remaining_storage:
        if not size<=remaining_free_storage and not time_difference < 21600:
           return await link_send(event)
        type_of = "downloading\nProgress:"
        msg = None

        timer = Timer()
        async def progress_bar(current, total,start_time=time.time()):
         if timer.can_send() and total != 0:  # Add a check to ensure total is not zero
          global download_in_progress
          global time_left
          download_in_progress = True
          progress_percent = current * 100 / total
          filename=fi_encoded
          progress_message = f"Downloading {filename}: {progress_percent:.2f}%\n"

          # Calculate progress bar length
          progress_bar_length = 30
          num_ticks = int(progress_percent / (100 / progress_bar_length))
          progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

          # Calculate speed in MB/s
          elapsed_time = time.time() - start_time
          speed = current / (elapsed_time * 1024 * 1024)
          progress_message += f"Speed: {speed:.2f} MB/s\n"

          # Calculate estimated time left to complete
          time_left = (total - current) / (speed * 1024 * 1024) if speed != 0 else 0  # C>
          progress_message += f"Time left: {time_left:.2f} seconds\n"

          # Display current size and total size
          progress_message += f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

          # Combine progress bar and message
          progress_message += f"\n[{progress_bar_text}]"
          if not time_difference < 0:
            progress_message += f"\n\n**Slow download?**, use /premium to boost download speed"
          message_text = f"{progress_message}"
          try:
            await msg.edit(message_text, parse_mode='html')
          except Exception as e:
            print(e)
        os.makedirs(user_dir, exist_ok=True)
        stopper +=1
        #os.chdir(user_dir)
        if not download_in_progress:
            user_ids[user_id] = True
            download_in_progress = True  #
            active_user_id=user_id
            await asyncio.sleep(5)
            fi = event.file.name
            try:
             if fi is None or not time_difference < 0 or size <= 35000000:
                msg = await event.reply("Downloading started")
                await client.download_media(event.media,file=user_dir,progress_callback=progress_bar)
                await msg.edit("Finished downloading\n/my_files to see your files")
             elif fi is not None and time_difference < 0:
                if stopper % 10 == 0:
                  await asyncio.sleep(180)
                msg = await event.reply("Downloading started")
                extension = os.path.splitext(fi)[1]
                fi_encoded = fi.encode('utf-8').decode('utf-8')
                with open(f"{user_dir}/{fi_encoded}", "wb") as out:
                    try:
                     await download_file(event.client, docs, out, progress_callback=progress_bar)
                     await msg.edit("Finished downloading\n/my_files to see your files")
                    except Exception as e:
                      await msg.edit(f"Download failed: {e}\nPlease resend this file")
                      download_in_progress = False
            except UserIsBlockedError:
                 return await timeout(event)
            download_in_progress = False
            if not premium_queue.empty():

                next_file = premium_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
            elif not download_queue.empty():

                next_file = download_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
            elif not link_download_queue.empty():
                next_link = link_download_queue.get()
                dd=dd-1
                user_ids.clear()
                await link_download(next_link)
        else:
            dd+=1
            que=f'I have added your file in queue to download'
            if not time_difference < 0:
                 que=f'I have added your file in queue to download\nYou can buy /premium to prioritise your download'
            if user_id not in user_ids:
               user_ids[user_id] = True
               user2=await event.reply(que,buttons=Button.inline("check your queue",b"bhad"))
            if time_difference < 0:
                premium_queue.put(event)
            else:
                download_queue.put(event)
    else:
        await event.reply("Not enough storage space to download this file.",buttons=common_buttons)
        if not premium_queue.empty():

                next_file = premium_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
        elif not download_queue.empty():

                next_file = download_queue.get()
                dd=dd-1
                user_ids.clear()
                await download(next_file)
        elif not link_download_queue.empty():
                next_link = link_download_queue.get()
                dd=dd-1
                user_ids.clear()
                await link_download(next_link)


zipping_in_progress=False

import zipfile
import re

# Updated API credentials and bot

video_sent=False
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/fzip'))
async def fzip(event):
    user_id = event.sender_id
    await callback_fzip(event)
async def create_zip(event):
    global zipping_in_progress
    user = await event.get_sender()
    user_iid = user.id
    global group_user_ids
    global zipping_in_progress
    global file_name
    global edit
    global message
    if file_name.startswith("/") or file_name.startswith("http") or event.document or event.media:
        return
    # Fetch all user IDs in the group and store them in the dictionary
    check_if = await is_user_on_chat(client, "@treaserthings", event.sender_id)
    '''if not check_if:
        button = Button.url("Join", "https://t.me/treaserthings")
        return await event.respond("You need to join @treaserthings in order to use this bot.\n\nClick below to Join!", buttons=button)'''
    group_user_ids.clear()
    user_id = str(event.sender_id)
    user_dir =f"{ggg}/zipper/{user_id}"
    if not os.path.exists(user_dir):
        return await event.reply("Your directory doesn't exist.", buttons=back_buttons)

    # List all files in the user's directory and add them to the zip archive
    files = os.listdir(user_dir)

    if not files:
        try:
            await event.edit("No files to compress.", buttons=back_buttons)
        except:
            return await event.respond("No files to compress.", buttons=back_buttons)
    #zip_dir = os.path.join(user_dir, 'zip')
    #os.makedirs(zip_dir, exist_ok=True)

    if not file_name.endswith('.zip'):
        file_name=f'{file_name}.zip'

# Create a unique zip file name (you can use timestamp or any other method)
    zip_filename= file_name
    video_extensions = ['.mp4', '.avi', '.wmv', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp']
    video_files = [file for file in files if os.path.splitext(file)[1].lower() in video_extensions]
    global video_sent
    if video_files:
        video_sent=True
    # Compress files into a zip archive
    try:
        message=await event.edit("Compressing files to zip please wait")
    except:
        message=await event.respond("Compressing files to zip please wait")
    try:
        # Use the 'zip' command via subprocess to create the zip file
        count = 0
        zipping_in_progress=True
        for filename in os.listdir(user_dir):
            command=['zip', zip_filename, os.path.join(user_dir, filename)]
            output= subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,  universal_newlines=True, )
            for line in output.stdout:
                line = line.strip()
                if line:
                    line=line.replace(f"zipper/{user_id}/","")
                    try:
                        await message.edit(line)
                    except Exception as e:
                        print(e)
                edit+=1
            count += 1

        # Check if the zip file was created successfully
        if os.path.exists(zip_filename):

            # Check the size of the zip file
            file_size = os.path.getsize(zip_filename)
            await event.respond('compression completed now uploading file')
            if file_size <=2000000000:  # 1000 MB in bytes
                type_of = "Uploading\nProgress:"
                msg = None
                timer = Timer()
        # File size is less than or equal to 1000 MB, upload as is
                async def progress_bar(current, total,start_time=time.time()):
                    global time_left
                    if timer.can_send():
                        progress_percent = current * 100 / total
                        progress_message = f"Uploading {zip_filename}: {progress_percent:.2f}%\n"

        # Calculate speed in MB/s
                        elapsed_time = time.time() - start_time
                        speed = current / (elapsed_time * 1024 * 1024)
                        progress_message += f"Speed: {speed:.2f} MB/s\n"

        # Calculate estimated time left to complete
                        time_left = (total - current) / (speed * 1024 * 1024)
                        progress_message += f"Time left: {time_left:.2f} seconds"
                        progress_message += f"\nSize: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

                        progress_bar_length = int(progress_percent / 5)
                        progress_bar_text = "█" * progress_bar_length + "░" * (20 - progress_bar_length)

                        progress_message += f"\n[{progress_bar_text}]"

        # Create a message with HTML formatting for better appearance
                        message_text = f"{progress_message}"

                        try:
                            await asyncio.sleep(1)
                            await msg.edit(message_text, parse_mode='html')
                        except Exception as e:
                            print(e)
                type_of = f"Uploading Compressed file\nProgress:"
                msg = await event.respond("uploading started")

         
                #await app.send_video(
             #int(event.sender_id),zip_filename,caption="zip by @FILEs_COMPRESSOR_BOT", progress=progress_bar)
                with open(zip_filename, "rb") as out:
                   res = await upload_file(client, out, progress_callback=progress_bar)
            # result is InputFile()
            # you can add more data to it
                   attributes, mime_type = utils.get_attributes(
                zip_filename,
            )
                   media = types.InputMediaUploadedDocument(
                file=res,
                mime_type=mime_type,
                attributes=attributes,
                # not needed for most files, thumb=thumb,
                force_file=False
            )
                   await event.reply(file=media)

                await msg.edit('Uploaded successfully\n\nPlease join @nub_coder_s', buttons=home_buttons)
                user_data = collection.find_one({})
                if user_data:
                                   is_ad = user_data.get('is_ad',"false")
                                   ad = user_data.get('ad')
                                   if ad and is_ad=='true':
                                      await event.respond(ad)
                if os.path.exists(user_dir):
                        shutil.rmtree(user_dir, ignore_errors=True)  # Recursivel$
                        os.makedirs(user_dir, exist_ok=True)
            elif file_size <= 5000000000:
                global time_left
                import requests

                url = "https://api.gofile.io/servers"

# Send an HTTP GET request and get the JSON response
                response = requests.get(url)
                data = response.json()

# Extract the server from the JSON response
                servers = data["data"]["servers"][0]
                server= servers['name']
                if not server:
        # Handle the scenario where the server variable is not available
        # Move the zip file to a specific directory based on an environmental value
                 #
                   return await event.reply("No storage available in gofile.io please try again later:", buttons=Button.url("Download File", download_url))

    # Your existing code...


# Print the server
                zipping_in_progress=False
                video_sent = False
                file_size = os.path.getsize(zip_filename)
                print(server)

                if file_size > 5000000000:  # 5000 MB
                    await event.reply("File size is too large to upload here. Please use an alternative method.", buttons=back_buttons)
                    return

                message=await event.respond('Compression completed. Uploading file...')

                transfer_url =f"https://{server}.gofile.io/uploadFile"
                try:
                 command=["curl","-F", f"file=@{zip_filename}", transfer_url]
                 start_time=time.time()
                 print(command)
                 output= subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True, bufsize=1,   universal_newlines=True, )
                 for line in output.stdout:
                        type_of = "Uploading\nProgress:"
                        line = line.strip()
                        if line:
                            output_text = line
                            print(line)

                            if edit % 5 == 0:
                                parts = line.split()

                                if len(parts) > 10:
                                     print(parts[1])
                                     total_size = parts[1]
                                     total =re.sub("[^0-9]", "", total_size)
                                     current_size = parts[5]
                                     current=re.sub("[^0-9]", "",current_size)

                                # Check if the parts contain valid numerical values
                                     if total.isdigit() and current.isdigit():
                                            total = int(total)
                                            current = int(current)

                                            if current != 0 and total != 0:
                                                progress_percent = current * 100 / total
                                                progress_message = f"Uploading {zip_filename}: {progress_percent:.2f}%\n\n"

                                                elapsed_time = time.time() - start_time
                                                speed = current / (elapsed_time*10)
                                                progress_message += f"Speed: {speed:.2f} MB/s\n"

                                                time_left = (total - current) / (speed*10)
                                                progress_message += f"Time left: {time_left:.2f} seconds"
                                                progress_message += f"Size: {current :.2f} MB / {total :.2f} MB"

                                                progress_bar_length = int(progress_percent / 5)
                                                progress_bar_text = "█" * progress_bar_length + "░" * (20 - progress_bar_length)
                                                progress_message += f"\n[{progress_bar_text}]"

                                                message_text = f"{progress_message}"

                                                try:
                                                        await message.edit(message_text, parse_mode='html')
                                                except Exception as e:
                                                        print(e)


                                                        zipping_in_progress=False
                        edit+=1
                 text=line
                 start_index = text.find("https://gofile.io")
                 end_index = text.find('"', start_index)

# Extract the link
                 link = text[start_index:end_index]
                            #sanitized_link = re.sub(r'[^a-zA-Z0-9:/._-]', '', link)

#print(sanitized_link)
                 try:
                                await message.edit(f"Not able to upload files more than 500MB here\n So I provided this download link:", buttons=Button.url("Download File",link))
                                user_data = collection.find_one({})
                                if user_data:
                                   is_ad = user_data.get('is_ad',"false")
                                   ad = user_data.get('ad')
                                   if ad and is_ad=='true':
                                      await event.respond(ad)
                                zipping_in_progress=False
                 except Exception as e:
                                print(f"Error sending link: {link}, Error: {e}")
    # Clean up the user directory
                except subprocess.CalledProcessError as e:
                    print(e)
                    await start(event)
    # Clean up the user directory

                try:
                 os.remove(zip_filename)
                except OSError as e:
                 print(e)
                if os.path.exists(user_dir):
                    shutil.rmtree(user_dir, ignore_errors=True)
        os.makedirs(user_dir, exist_ok=True)
        zipping_in_progress=False
    except Exception as e:
        await event.respond(f"An error occurred: {str(e)}", buttons=back_buttons)
        print(e)

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.raw_text == '/help'))
async def help_handler(event):
    user_id = str(event.sender_id)
    user_dir = user_id

    # Provide information about the bot
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

    # Send the help message with the common buttons
    await event.respond(help_message, parse_mode="html", buttons=common_buttons)


edit=0
# ... (previous code remains the same)
async def update_progress(event, message, link):
    while True:
        await asyncio.sleep(3)  # Update progress every 5 seconds

async def link_download(event):
    link = event.raw_text
    user_id = event.sender_id
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
    
    max_file_size_bytes = 4 * 1024 * 1024 * 1024  # 4 GB in bytes
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = 4.5 * 1024 * 1024 * 1024 - total_size  # 3GB in bytes
    remaining_free_storage = 200 * 1024 * 1024 - total_size
    timer = Timer()
    async def progress_bar(current, total, start_time, msg, filename):
     if timer.can_send() and total != 0:  # Add a check to ensure total is not zero
        progress_percent = current * 100 / total
        progress_message = f"Downloading {filename}: {progress_percent:.2f}%\n"

        # Calculate progress bar length
        progress_bar_length = 30
        num_ticks = int(progress_percent / (100 / progress_bar_length))
        progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

        # Calculate speed in MB/s
        elapsed_time = time.time() - start_time
        speed = current / (elapsed_time * 1024 * 1024)
        progress_message += f"Speed: {speed:.2f} MB/s\n"

        # Calculate estimated time left to complete
        time_left = (total - current) / (speed * 1024 * 1024) if speed != 0 else 0  # Check for zero speed
        progress_message += f"Time left: {time_left:.2f} seconds\n"

        # Display current size and total size
        progress_message += f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB"

        # Combine progress bar and message
        progress_message += f"\n[{progress_bar_text}]"

        # Create a message with HTML formatting for better appearance
        message_text = f"{progress_message}"
        try:
            await asyncio.sleep(1)
            await msg.edit(message_text, parse_mode='html')
        except Exception as e:
            print(e)
    try:
        # Send a HEAD request to fetch only headers and check file size
        response = requests.head(link)
        if "content-length" in response.headers:
            content_length = int(response.headers["content-length"])
            if content_length <= remaining_storage:
                if not content_length <= remaining_free_storage and not time_difference < 21600:
                    return await link_send(event)
                filename = link.split('/')[-1]  # Extract filename from URL
                message = await event.reply(f"Downloading {filename}\nFile size: {content_length} bytes\nStarting download")
                progress_task = asyncio.create_task(update_progress(event, message, link))
                
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
                                    await progress_bar(current_size, content_length, start_time, message, filename)
                                await message.edit(f"File {filename} downloaded successfully\n/my_files to check all your files")
                        else:
                            await event.reply("Download failed. Please check the URL.")
        else:
            await event.reply("Content length not found in headers. Cannot determine file size.")
    except Exception as e:
        await event.reply(str(e))

# ... (previous code remains the same)
from telethon import Button

@client.on(events.NewMessage(pattern='/premium'))
async def premium_info(event):
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
    contact_button = Button.url("Contact Admin", "https://t.me/nub_coder_s")
    await event.respond(premium_benefits, parse_mode="html", buttons=[[contact_button]])


from telethon import TelegramClient, events
import time

# ... your client and collection setup ...

@client.on(events.NewMessage(pattern='/status'))
async def user_status(event):
    user_id = event.sender_id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference =  stored_time - current_time

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

    await event.respond(status_message)

@client.on(events.NewMessage(pattern='/rst'))
async def unauthorize_user(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg.sender_id is not None:
            user_id = replied_msg.sender_id
        else:
            return await event.reply("Cannot authorize user: Unknown user ID.")
    command_args = event.raw_text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                user_id = (await client.get_entity(arg)).id
            except ValueError:
                return await event.reply("Cannot find user with the provided username.")

    # Store the user with a timestamp 30 days from now
    timestamp = int(time.time()) - 12600
    storre_user(user_id, timestamp)
    user_data = collection.find_one({"user_id": user_id})
    await event.reply(f"User resetted successfully.\nUserdata:{user_data}")

@client.on(events.NewMessage(pattern='/authorize'))
async def authorize_user(event):
    user_id = event.sender_id
    
    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    
    # Check if the command is replying to a message
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg.sender_id is not None:
            user_id = replied_msg.sender_id
        else:
            return await event.reply("Cannot authorize user: Unknown user ID.")
    
    # Extract user_id from the command argument
    command_args = event.raw_text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                # Resolve username to user_id
                user_id = (await client.get_entity(arg)).id
            except ValueError:
                return await event.reply("Cannot find user with the provided username.")
    
    # Store the user with a timestamp 30 days from now
    timestamp = int(time.time()) + (30 * 24 * 60 * 60)
    storre_user(user_id, timestamp)
    user_data = collection.find_one({"user_id": user_id})
    await event.reply(f"User authorized successfully.\nUserdata:{user_data}")

def storre_user(user_id, timestamp):
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)



@client.on(events.NewMessage(pattern='/users'))
async def list_users(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
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
            await event.respond(chunk)
    else:
        await event.respond("No users found.")

@client.on(events.NewMessage(pattern='/set'))
async def set_handler(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    input_text = event.raw_text.split('/set ')[1]
    value = input_text.strip()
    collection.update_one({}, {"$set": {'ad': value}}, upsert=True)
    await event.respond('Value saved successfully!')

@client.on(events.NewMessage(pattern='/ad'))
async def ad_handler(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/zipper/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    is_ad_value = event.raw_text.split()[1]
    # Update "is_ad" field in Advertisement collection with the new value
    collection.update_one({}, {"$set": {'is_ad': is_ad_value}}, upsert=True)
    await event.respond(f'Updated "is_ad" field with: {is_ad_value}')

@client.on(events.NewMessage(pattern='/get'))
async def get_handler(event):
    result = collection.find_one({})
    if result:
        value = result['ad']
        await event.respond(f'The value is: {value}')
    else:
        await event.respond('No value found')

app.start()
client.run_until_disconnected()
