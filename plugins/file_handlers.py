
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.user_management import store_userr, get_user_status
from plugins.ui_components import home_buttons, common_buttons, file_buttons, nofile_buttons, back_buttons, pass_button
from plugins.file_operations import Timer, upload_to_gofile, get_file_size_info, cleanup_user_directory
from plugins.verification import send_verification_link
from plugins.installer import get_database_collection
from tools import is_user_on_chat
import os
import shutil
import subprocess
import requests
import aiohttp
import time
import random
import asyncio
import queue

collection = get_database_collection()
ggg = os.getcwd()

# Global variables (will be updated by main.py)
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
zipping_in_progress = False
download_in_progress = False
user_ids = {}
active_user_id = None
time_left = 0

@Client.on_message(filters.command("my_files"))
async def list_files_command(client: Client, message: Message):
    await list_files(message)

@Client.on_message(filters.command("del"))
async def delete_file(client: Client, message: Message):
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

@Client.on_message(filters.command("clear"))
async def clear_files(client: Client, message: Message):
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

@Client.on_message(filters.command("fzip"))
async def zip_files_command(client: Client, message: Message):
    return await message.reply_text(
        "Would you like to protect your zip file with a secure password ?",
        reply_markup=pass_button
    )

@Client.on_message(filters.private & (filters.document | filters.photo))
async def handle_media(client: Client, message: Message):
    if not download_queue.empty() or not premium_queue.empty():
        await asyncio.sleep(5)
    await download(message)

@Client.on_message(filters.private & filters.text & ~filters.command(["start", "help", "my_files", "clear", "del", "fzip", "premium", "status", "rst", "authorize", "users", "set", "ad", "get", "loud", "reboot", "skip"]))
async def handle_links(client: Client, message: Message):
    if message.text.startswith("http"):
        await link_download(message)

async def list_files(event):
    user_id = event.from_user.id
    check_if = await is_user_on_chat(Client.get_current(), "@nub_coder_updates", user_id)

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

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

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

async def download(message):
    global active_user_id, download_in_progress, dd
    user_id = message.from_user.id
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

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
            # Import timeout function from main
            import main
            await main.timeout()
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
        import main
        await main.timeout()

async def link_download(message):
    link = message.text
    user_id = message.from_user.id
    is_verified, max_storage, max_file_size = get_user_status(collection, user_id)

    user_dir = f"{ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)
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
