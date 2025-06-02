from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.user_management import store_userr, get_user_status
from plugins.ui_components import home_buttons, common_buttons, file_buttons, nofile_buttons, back_buttons
from plugins.file_handlers import list_files, clear_files
from plugins.installer import get_database_collection
from tools import is_user_on_chat
import os
import shutil
import subprocess
import time
import random
import queue

collection = get_database_collection()
ggg = os.getcwd()

# Global variables
dd = 0
download_queue = queue.Queue()
premium_queue = queue.Queue()
user_ids = {}
active_user_id = None
time_left = 0

@Client.on_callback_query(filters.regex("no_password"))
async def without_pass(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text("starting without password")
    await create_zip(callback_query, None)

@Client.on_callback_query(filters.regex("set_password"))
async def with_pass(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text("starting with password")
    await create_zip(callback_query, True)

@Client.on_callback_query(filters.regex("cancel_download"))
async def cancel_download(client: Client, callback_query: CallbackQuery):
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

@Client.on_callback_query(filters.regex("bhad"))
async def callback_queue(client: Client, callback_query: CallbackQuery):
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

@Client.on_callback_query(filters.regex("help"))
async def callback_help(client: Client, callback_query: CallbackQuery):
    from plugins.basic_commands import help_command
    await help_command(client, callback_query)

@Client.on_callback_query(filters.regex("my_files"))
async def callback_my_files(client: Client, callback_query: CallbackQuery):
    await list_files(callback_query)

@Client.on_callback_query(filters.regex("clear"))
async def callback_clear(client: Client, callback_query: CallbackQuery):
    await clear_files(client, callback_query)

@Client.on_callback_query(filters.regex("home"))
async def callback_home(client: Client, callback_query: CallbackQuery):
    await start_handler(callback_query)

@Client.on_callback_query(filters.regex("fzip"))
async def callback_fzip(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text(
        "Would you like to protect your zip file with a secure password ?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 Set a Password", callback_data="set_password")],
            [InlineKeyboardButton("🔓Continue without Password", callback_data="no_password")]
        ])
    )

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

async def create_zip(callback_query, pass_protect=None):
    user_id = callback_query.from_user.id

    try:
        await callback_query.message.reply_text("Provide me a suitable filename for the zip file")
        response = await Client.get_current().listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        password = ''
        com = ''
        if pass_protect:
            await callback_query.message.reply_text("please type your password below.")
            get_pass = await Client.get_current().listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
            com = '--password'

    except Exception as e:
        await callback_query.message.reply_text(str(e))
        return

    file_name = response.text
    if file_name.startswith("/") or file_name.startswith("http"):
        return

    check_if = await is_user_on_chat(Client.get_current(), "@nub_coder_updates", user_id)
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
            from plugins.file_operations import Timer

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

            await Client.get_current().send_document(
                callback_query.message.chat.id,
                zip_filename,
                caption="zip by @FILEs_COMPRESSOR_BOT",
                progress=progress_bar
            )

            await msg.edit_text('Uploaded successfully\n\nPlease join @nub_coder_s', reply_markup=home_buttons)

        else:  # Upload to gofile.io for large files
            from plugins.file_operations import upload_to_gofile
            await upload_to_gofile(callback_query, zip_filename, message)

        # Show ad if enabled
        user_data = collection.find_one({})
        if user_data and user_data.get('is_ad') == 'true' and user_data.get('ad'):
            await callback_query.message.reply_text(user_data['ad'])

        # Clean up
        from plugins.file_operations import cleanup_user_directory
        cleanup_user_directory(user_dir)
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from plugins.ui_components import home_buttons, back_buttons, pass_button
from plugins.user_management import store_userr, get_user_status
from plugins.file_operations import Timer, upload_to_gofile
from plugins.installer import get_database_collection
from tools import is_user_on_chat
import subprocess
import shutil
import os
import time
import random

# These will be updated by main.py
dd = 0
download_queue = None
premium_queue = None
user_ids = {}
active_user_id = None
time_left = 0
collection = None
ggg = None
timeout = None

@Client.on_callback_query(filters.regex("no_password"))
async def without_pass(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text("starting without password")
    await create_zip(client, callback_query, None)

@Client.on_callback_query(filters.regex("set_password"))
async def with_pass(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text("starting with password")
    await create_zip(client, callback_query, True)

@Client.on_callback_query(filters.regex("cancel_download"))
async def cancel_download(client: Client, callback_query: CallbackQuery):
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

@Client.on_callback_query(filters.regex("bhad"))
async def callback_queue(client: Client, callback_query: CallbackQuery):
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

@Client.on_callback_query(filters.regex("help"))
async def callback_help(client: Client, callback_query: CallbackQuery):
    from plugins.basic_commands import help_command
    # Convert callback query to message-like object for help_command
    class MessageLike:
        def __init__(self, callback_query):
            self.from_user = callback_query.from_user
            self.edit_message_text = callback_query.edit_message_text

        async def reply_text(self, text, reply_markup=None):
            await self.edit_message_text(text, reply_markup=reply_markup)

    message_like = MessageLike(callback_query)
    await help_command(client, message_like)

@Client.on_callback_query(filters.regex("my_files"))
async def callback_my_files(client: Client, callback_query: CallbackQuery):
    from plugins.file_handlers import list_files
    await list_files(callback_query)

@Client.on_callback_query(filters.regex("clear"))
async def callback_clear(client: Client, callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    user_path = os.path.join("zipper", user_id)

    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
        os.makedirs(user_path, exist_ok=True)
        message_text = "All files and directories in your directory have been removed."
    else:
        message_text = "Your directory does not exist."

    await callback_query.edit_message_text(message_text, reply_markup=back_buttons)

@Client.on_callback_query(filters.regex("home"))
async def callback_home(client: Client, callback_query: CallbackQuery):
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

@Client.on_callback_query(filters.regex("fzip"))
async def callback_fzip(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_text(
        "Would you like to protect your zip file with a secure password ?",
        reply_markup=pass_button
    )

async def create_zip(client, callback_query, pass_protect=None):
    user_id = callback_query.from_user.id

    try:
        await client.send_message(user_id, "Provide me a suitable filename for the zip file")
        response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)

        password = ''
        com = ''
        if pass_protect:
            await client.send_message(user_id, "please type your password below.")
            get_pass = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=120)
            password = get_pass.text
            com = '--password'

    except Exception as e:
        await callback_query.message.reply_text(str(e))
        return

    file_name = response.text
    if file_name.startswith("/") or file_name.startswith("http"):
        return

    check_if = await is_user_on_chat(client, "@nub_coder_updates", user_id)
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
            global time_left

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

            await client.send_document(
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