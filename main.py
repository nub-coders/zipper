import urllib3
urllib3.disable_warnings()
import random
import os
import time
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
import asyncio
import queue
import math
import cryptg

# Import plugins
from plugins.installer import initialize_bot
from plugins.user_management import *
from plugins.ui_components import *
from plugins.file_operations import *
from plugins.admin_commands import *
from plugins.verification import send_verification_link
from config import *
from tools import is_user_on_chat
import string

# Initialize bot and get database collection
collection = initialize_bot()
ggg = os.getcwd()

# Bot configuration
time.sleep(2)
app = Client('file_compressor_bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
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
        await download(next_file)
    elif not download_queue.empty():
        next_file = download_queue.get()
        dd -= 1
        user_ids.clear()
        await download(next_file)

# Command handlers
@app.on_message(filters.command("skip") & filters.regex("^!skip$"))
async def skip_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await message.reply_text("Admin command received. Skipping the task...")
                await timeout()

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
        for user_id in stored_user_ids:
            try:
                await message.reply_to_message.forward(user_id)
                xx += 1
            except Exception as e:
                print(f"Failed to forward message: {e}")
        await message.reply_text(f"Broadcasted to {xx} users")

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

@app.on_message(filters.command("start"))
async def lstart(client, message):
    user_id = message.from_user.id

    if message.text == "/start":
        user_data = collection.find_one({"user_id": user_id})
        if not user_data:
            store_userr(collection, user_id)
        await message.reply_text(
            "Hello! this is file to zip bot.\n"
            "Send me any files or direct download link and I will compress them to a zip\n"
            "/help to get more details",
            reply_markup=home_buttons
        )
        return

    # Handle verification codes
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data["timestamp"]
        time_difference = current_time - stored_time
        if time_difference < 21600:
            return await message.reply_text("You are already verified")

    # Check verification codes
    if user_data and "verifycode" in user_data:
        if f'verifycodeis{user_data["verifycode"]}' == message.text.split(' ')[1]:
            store_user(collection, user_id)
            await message.reply_text(
                "Welcome back to the bot! You are verified for 6 hours",
                reply_markup=home_buttons
            )
        else:
            await send_verification_link(message, collection)
    else:
        await send_verification_link(message, collection)

# Callback handlers
@app.on_callback_query(filters.regex("no_password"))
async def without_pass(client, callback_query):
    await callback_query.edit_message_text("starting without password")
    await create_zip(callback_query, None)

@app.on_callback_query(filters.regex("set_password"))
async def with_pass(client, callback_query):
    await callback_query.edit_message_text("starting with password")
    await create_zip(callback_query, True)

@app.on_callback_query(filters.regex("cancel_download"))
async def cancel_download(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in user_ids:
        try:
            download_queue.queue.remove(callback_query)
        except:
            pass
        del user_ids[user_id]
        await callback_query.edit_message_text("Download canceled.")
    else:
        await callback_query.edit_message_text("No ongoing download to cancel.")

@app.on_callback_query(filters.regex("bhad"))
async def callback_queue(client, callback_query):
    global dd, active_user_id, time_left
    user_task_counts = {}

    for download_event in list(download_queue.queue) + list(premium_queue.queue):
        event_user_id = download_event.from_user.id
        user_task_counts[event_user_id] = user_task_counts.get(event_user_id, 0) + 1

    response_text = f"ACTIVE USER ⚡: {active_user_id}\n\n" if active_user_id else "No active downloads or uploads\n\n"
    response_text += "DOWNLOAD IN QUEUE:\n"

    for user_id, task_count in user_task_counts.items():
        response_text += f"{user_id}:({task_count} tasks)\n\n"
    response_text += f"\nNEXT QUEUE IN: {time_left} seconds"

    try:
        await callback_query.answer(response_text, show_alert=True)
    except Exception:
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
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
        store_userr(collection, user_id)

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
        message_text = "You need to join @nub_coder_updates in order to use this bot.\n\nClick below to Join!"
        if hasattr(event, 'edit_message_text'):
            return await event.edit_message_text(message_text, reply_markup=button)
        else:
            return await event.reply_text(message_text, reply_markup=button)

    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)
    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = max_storage - total_size
    files = os.listdir(user_dir)

    if files:
        file_entries = [
            f"{i+1}. {file} - {os.path.getsize(os.path.join(user_dir, file)) / (1024 * 1024):.2f} MB"
            for i, file in enumerate(files)
        ]
        total_size_mb = total_size / (1024 * 1024)

        if is_verified:
            remaining_storage_gb = remaining_storage / (1024 * 1024 * 1024)
            header = (
                f"Total storage used: {total_size_mb:.2f} MB\n"
                f"Remaining Storage: {remaining_storage_gb:.2f} GB\n\n"
                f"List of files in your directory:\n\n"
            )
        else:
            remaining_storage_mb = remaining_storage / (1024 * 1024)
            header = (
                f"<b>Total storage used: {total_size_mb:.2f} MB</b>\n"
                f"<b>Remaining free Storage: {remaining_storage_mb:.2f} MB</b>\n\n"
                f"<b>List of files in your directory:</b>\n\n"
                f"<b>Use /del <number> to delete the file using file number in list:</b>\n\n"
            )

        # Split long messages
        messages = []
        current_message = header
        for entry in file_entries:
            if len(current_message) + len(entry) + 1 > 4096:
                messages.append(current_message)
                current_message = f"<blockquote>{entry}</blockquote>\n"
            else:
                current_message += f"<blockquote>{entry}</blockquote>\n"
        messages.append(current_message)

        for i, msg in enumerate(messages):
            reply_markup = file_buttons if i == len(messages) - 1 else None
            if hasattr(event, 'edit_message_text') and i == 0:
                await event.edit_message_text(msg, reply_markup=reply_markup)
            else:
                await event.reply_text(msg, reply_markup=reply_markup)
    else:
        message = "Your directory is empty, send me any file"
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
            return await message.reply_text("Invalid file number.")
    else:
        return await message.reply_text("Your directory doesn't exist. Send me any file to create your directory.")

@app.on_message(filters.command("clear"))
async def clear(client, message):
    user_id = str(message.from_user.id)
    user_path = os.path.join("zipper", user_id)

    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
        os.makedirs(user_path, exist_ok=True)
        message_text = "All files and directories in your directory have been removed."
    else:
        message_text = "Your directory does not exist."

    if hasattr(message, 'edit_message_text'):
        await message.edit_message_text(message_text, reply_markup=back_buttons)
    else:
        await message.reply_text(message_text, reply_markup=back_buttons)

async def download(message):
    global active_user_id, download_in_progress, dd
    user_id = message.from_user.id
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = max_storage - total_size

    # Get file size
    if message.document:
        size = message.document.file_size
        if size > max_file_size:
            size_gb = max_file_size / (1024 * 1024 * 1024)
            return await message.reply_text(
                f"Please send a file smaller than {size_gb:.1f}GB.\n/my_files to show your files",
                reply_markup=common_buttons
            )
    elif message.photo:
        size = 100
    else:
        size = 0

    if size <= remaining_storage:
        if not is_verified and size > 200 * 1024 * 1024:
            return await send_verification_link(message, collection)

        timer = Timer()

        async def progress_bar(current, total, start_time=time.time()):
            if timer.can_send() and total != 0:
                global download_in_progress, time_left
                download_in_progress = True
                progress_percent = current * 100 / total
                filename = fi_encoded if fi_encoded else "file"

                progress_bar_length = 30
                num_ticks = int(progress_percent / (100 / progress_bar_length))
                progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

                elapsed_time = time.time() - start_time
                speed = current / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0
                time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

                progress_message = (
                    f"Downloading {filename}: {progress_percent:.2f}%\n"
                    f"Speed: {speed:.2f} MB/s\n"
                    f"Time left: {time_left:.2f} seconds\n"
                    f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB\n"
                    f"[{progress_bar_text}]"
                )

                if not is_verified:
                    progress_message += f"\n\n**Slow download?**, use /premium to boost download speed"

                try:
                    if random.choices([True, False], weights=[1, 999])[0]:
                        await msg.edit_text(progress_message)
                except Exception as e:
                    print(e)

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

            except Exception as e:
                await msg.edit_text(f"Download failed: {e}\nPlease resend this file")

            download_in_progress = False
            await timeout()
        else:
            dd += 1
            queue_message = 'I have added your file in queue to download'
            if not is_verified:
                queue_message += '\nYou can buy /premium to prioritise your download'

            if user_id not in user_ids:
                user_ids[user_id] = True
                queue_button = InlineKeyboardMarkup([[InlineKeyboardButton("check your queue", callback_data="bhad")]])
                await message.reply_text(queue_message, reply_markup=queue_button)

            if is_verified:
                premium_queue.put(message)
            else:
                download_queue.put(message)
    else:
        await message.reply_text("Not enough storage space to download this file.", reply_markup=common_buttons)
        await timeout()

@app.on_message(filters.command("fzip"))
async def check_pass(client, message):
    return await message.reply_text(
        "Would you like to protect your zip file with a secure password ?",
        reply_markup=pass_button
    )

async def create_zip(callback_query, pass_protect=None):
    user_id = callback_query.from_user.id

    try:
        await app.send_message(user_id, "Provide me a suitable filename for the zip file")
        response = await app.listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        password = ''
        com = ''
        if pass_protect:
            await app.send_message(user_id, "please type your password below.")
            get_pass = await app.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
            com = '--password'

    except Exception as e:
        await callback_query.message.reply_text(str(e))
        return

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

    if not files:
        return await callback_query.message.reply_text(
            "you don't have files to zip\nSend your files first",
            reply_markup=back_buttons
        )

    if not file_name.endswith('.zip'):
        file_name = f'{file_name}.zip'

    zip_filename = os.path.join(user_dir, file_name)

    try:
        message = await callback_query.message.edit_text("Compressing files to zip please wait")
    except:
        message = await callback_query.message.reply_text("Compressing files to zip please wait")

    # Create zip file
    for filename in files:
        command = ['zip', com, password, zip_filename, os.path.join(user_dir, filename)] if pass_protect else ['zip', zip_filename, os.path.join(user_dir, filename)]
        output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for line in output.stdout:
            line = line.strip()
            if line:
                line = line.replace(f"zipper/{user_id}/", "")
                try:
                    await message.edit_text(line)
                except Exception:
                    pass

    if os.path.exists(zip_filename):
        file_size = os.path.getsize(zip_filename)
        await callback_query.message.reply_text('compression completed now uploading file')

        if file_size <= 2000000000:  # 2GB
            timer = Timer()

            async def progress_bar(current, total, start_time=time.time()):
                global time_left
                if timer.can_send():
                    progress_percent = current * 100 / total
                    elapsed_time = time.time() - start_time
                    speed = current / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0
                    time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

                    progress_bar_length = int(progress_percent / 5)
                    progress_bar_text = "█" * progress_bar_length + "░" * (20 - progress_bar_length)

                    progress_message = (
                        f"Uploading {zip_filename}: {progress_percent:.2f}%\n"
                        f"Speed: {speed:.2f} MB/s\n"
                        f"Time left: {time_left:.2f} seconds\n"
                        f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB\n"
                        f"[{progress_bar_text}]"
                    )

                    try:
                        if random.choices([True, False], weights=[1, 999])[0]:
                            await msg.edit_text(progress_message)
                    except Exception:
                        pass

            msg = await callback_query.message.reply_text("uploading started")

            await app.send_document(
                callback_query.message.chat.id,
                zip_filename,
                caption="zip by @FILEs_COMPRESSOR_BOT",
                progress=progress_bar
            )

            await msg.edit_text('Uploaded successfully\n\nPlease join @nub_coder_s', reply_markup=home_buttons)

        else:  # Upload to gofile.io for large files
            await upload_to_gofile(callback_query, zip_filename, message)

        # Show ad if enabled
        user_data = collection.find_one({})
        if user_data and user_data.get('is_ad') == 'true' and user_data.get('ad'):
            await callback_query.message.reply_text(user_data['ad'])

        # Clean up
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir, ignore_errors=True)
            os.makedirs(user_dir, exist_ok=True)

async def upload_to_gofile(callback_query, zip_filename, message):
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
        await message.edit_message_text(help_message, reply_markup=common_buttons)
    else:
        await message.reply_text(help_message, reply_markup=common_buttons)

async def link_download(message):
    link = message.text
    user_id = message.from_user.id
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in os.listdir(user_dir))
    remaining_storage = max_storage - total_size
    timer = Timer()

    async def progress_bar(current, total, start_time, msg, filename):
        if timer.can_send() and total != 0:
            progress_percent = current * 100 / total
            progress_bar_length = 30
            num_ticks = int(progress_percent / (100 / progress_bar_length))
            progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

            elapsed_time = time.time() - start_time
            speed = current / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0
            time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

            progress_message = (
                f"Downloading {filename}: {progress_percent:.2f}%\n"
                f"Speed: {speed:.2f} MB/s\n"
                f"Time left: {time_left:.2f} seconds\n"
                f"Size: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB\n"
                f"[{progress_bar_text}]"
            )

            try:
                if random.choices([True, False], weights=[1, 999])[0]:
                    await msg.edit_text(progress_message)
            except Exception:
                pass

    try:
        response = requests.head(link)
        if "content-length" in response.headers:
            content_length = int(response.headers["content-length"])
            if content_length <= remaining_storage:
                if not is_verified and content_length > 200 * 1024 * 1024:
                    return await send_verification_link(message, collection)

                filename = link.split('/')[-1]
                message_obj = await message.reply_text(f"Downloading {filename}\nFile size: {content_length} bytes\nStarting download")

                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:
                            file_path = os.path.join(user_dir, filename)
                            with open(file_path, "wb") as f:
                                while True:
                                    chunk = await resp.content.read(1024)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    current_size = os.path.getsize(file_path)
                                    await progress_bar(current_size, content_length, start_time, message_obj, filename)
                            await message_obj.edit_text(f"File {filename} downloaded successfully\n/my_files to check all your files")
                        else:
                            await message.reply_text("Download failed. Please check the URL.")
            else:
                await message.reply_text("Not enough storage space.")
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
    await message.reply_text(premium_benefits, reply_markup=contact_button)

@app<on_message(filters.command("status"))
async def user_status(client, message):
    user_id = message.from_user.id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference = current_time - stored_time

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

# Admin commands
@app.on_message(filters.command("rst"))
async def unauthorize_user(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user.id:
        target_user_id = message.reply_to_message.from_user.id

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            target_user_id = int(arg)
        else:
            try:
                user_entity = await app.get_users(arg)
                target_user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    if target_user_id:
        timestamp = int(time.time()) - 12600
        storre_user(collection, target_user_id, timestamp)
        user_data = collection.find_one({"user_id": target_user_id})
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

    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user.id:
        target_user_id = message.reply_to_message.from_user.id

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            target_user_id = int(arg)
        else:
            try:
                user_entity = await app.get_users(arg)
                target_user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    if target_user_id:
        timestamp = int(time.time()) + (30 * 24 * 60 * 60)
        storre_user(collection, target_user_id, timestamp)
        user_data = collection.find_one({"user_id": target_user_id})
        await message.reply_text(f"User authorized successfully.\nUserdata:{user_data}")

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
        user_list += f"\nTotal users: {len(user_ids)}"
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

    try:
        input_text = message.text.split('/set ')[1]
        value = input_text.strip()
        collection.update_one({}, {"$set": {'ad': value}}, upsert=True)
        await message.reply_text('Value saved successfully!')
    except IndexError:
        await message.reply_text('Please provide a value after /set')

@app.on_message(filters.command("ad"))
async def ad_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    try:
        is_ad_value = message.text.split()[1]
        collection.update_one({}, {"$set": {'is_ad': is_ad_value}}, upsert=True)
        await message.reply_text(f'Updated "is_ad" field with: {is_ad_value}')
    except IndexError:
        await message.reply_text('Please provide a value (true/false)')

@app.on_message(filters.command("get"))
async def get_handler(client, message):
    result = collection.find_one({})
    if result and 'ad' in result:
        await message.reply_text(f'The value is: {result["ad"]}')
    else:
        await message.reply_text('No value found')

# Message handlers
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