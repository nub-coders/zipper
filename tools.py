from config import *
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse
import os
import time
from pyrogram import Client, filters
import string
import random
import shutil
import subprocess
import requests
import aiohttp
from telethon import TelegramClient
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram import Client

async def is_user_on_chat(bot: TelegramClient, chat_id: int, user_id: int) -> bool:
    """
    Check if a user is present in a specific chat.

    Parameters:
        bot (TelegramClient): The Telegram client instance.
        chat_id (int): The ID of the chat.
        user_id (int): The ID of the user.

    Returns:
        bool: True if the user is present in the chat, False otherwise.
    """
    try:
        botting = bot_permissions = await bot.get_permissions(chat_id, bot._self_id)
    except:
        return True
    try:
        check = await bot.get_permissions(chat_id, user_id)
        return check
    except:
       return False

# Admin utility functions
def is_admin(user_id):
    """Check if user is admin"""
    ggg = os.getcwd()
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            return user_id in admin_ids
    return False

def get_admin_ids():
    """Get list of admin IDs"""
    ggg = os.getcwd()
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            return [int(line.strip()) for line in file.readlines()]
    return []

def store_userr(collection, user_id):
    """Store user in database"""
    current_time = int(time.time())
    user_data = {
        "user_id": user_id,
        "timestamp": current_time,
        "is_verified": False
    }
    collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

def store_user(collection, user_id):
    """Store verified user in database"""
    current_time = int(time.time())
    user_data = {
        "user_id": user_id,
        "timestamp": current_time,
        "is_verified": True
    }
    collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

def storre_user(user_id, timestamp):
    """Store user with specific timestamp"""
    user_data = {
        "user_id": user_id,
        "timestamp": timestamp,
        "is_verified": True
    }
    collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

def get_user_status(collection, user_id):
    """Get user verification status and limits"""
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    
    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference = current_time - stored_time
        
        if time_difference < 0:  # Premium user
            return True, 10 * 1024 * 1024 * 1024, 3.2 * 1024 * 1024 * 1024  # 10GB, 3.2GB
        elif time_difference < 21600:  # Elite user (6 hours)
            return True, 4.5 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024  # 4.5GB, 2GB
    
    return False, 200 * 1024 * 1024, 200 * 1024 * 1024  # 200MB, 200MB

def get_file_size_info(user_dir, max_storage):
    """Get file size information for user directory"""
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
        return 0, max_storage, []
    
    files = os.listdir(user_dir)
    total_size = sum(os.path.getsize(os.path.join(user_dir, file)) for file in files)
    remaining_storage = max_storage - total_size
    
    return total_size, remaining_storage, files

def cleanup_user_directory(user_dir):
    """Clean up user directory"""
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
        os.makedirs(user_dir, exist_ok=True)

async def send_verification_link(message, collection):
    """Send verification link to user"""
    user_id = message.from_user.id
    verifycode = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    user_data = {
        "user_id": user_id,
        "verifycode": verifycode,
        "timestamp": int(time.time())
    }
    collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)
    
    verify_url = f"https://t.me/{BOT_USERNAME}?start=verifycodeis{verifycode}"
    button = InlineKeyboardMarkup([[InlineKeyboardButton("Verify", url=verify_url)]])
    
    await message.reply_text(
        "You need to verify yourself to upload files larger than 200MB.\n"
        "Click the button below to verify:",
        reply_markup=button,
        quote=True,
        reply_to_message_id=message.id
    )

def get_queue_status(user_id):
    """Get queue status for user"""
    from config import active_user_id, time_left, dd, user_ids, download_queue, premium_queue
    
    user_task_counts = {}
    for download_event in list(download_queue.queue) + list(premium_queue.queue):
        event_user_id = download_event.from_user.id
        user_task_counts[event_user_id] = user_task_counts.get(event_user_id, 0) + 1

    response_text = f"ACTIVE USER ⚡: {active_user_id}\n\n" if active_user_id else "No active downloads or uploads\n\n"
    response_text += "DOWNLOAD IN QUEUE:\n"

    for uid, task_count in user_task_counts.items():
        response_text += f"{uid}:({task_count} tasks)\n\n"
    response_text += f"\nNEXT QUEUE IN: {time_left} seconds"
    
    return response_text

async def broadcast_message(client, message, collection):
    """Broadcast message to all users"""
    stored_user_ids = [user["user_id"] for user in collection.find()]
    success_count = 0

    if message.reply_to_message:
        for user_id in stored_user_ids:
            try:
                await message.reply_to_message.forward(user_id)
                success_count += 1
            except Exception as e:
                print(f"Failed to forward message: {e}")
    
    return success_count

import razorpay
import qrcode
import io
import os
import asyncio
from PIL import Image

# Razorpay configuration
KEY_ID = "rzp_live_whGnMZeGzeGe2l"
KEY_SECRET = "QBzrGMNofkapxcHZfd7nt160"
razor_client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Store payment orders
payment_orders = {}

def storre_user(collection, user_id, timestamp=None):
    """Store user with timestamp"""
    if timestamp is None:
        timestamp = int(time.time())
    
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)
    return collection.find_one({"user_id": user_id})

def authorize_premium_user(collection, user_id, days=30):
    """Authorize user as premium for specified days (additive)"""
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    
    if user_data and user_data.get("timestamp", 0) > current_time:
        # User has existing premium time, add to it
        existing_timestamp = user_data["timestamp"]
        new_timestamp = existing_timestamp + (days * 24 * 60 * 60)
    else:
        # User has no premium time or it's expired, start from now
        new_timestamp = current_time + (days * 24 * 60 * 60)
    
    storre_user(collection, user_id, new_timestamp)
    return collection.find_one({"user_id": user_id})

async def create_payment_order(amount, user_id, plan_type):
        """Create Razorpay payment order with payment link"""
        try:
            # Create payment link instead of order
            payment_link_data = {
                "amount": amount * 100,  # Amount in paise
                "currency": "INR",
                "description": f"Premium subscription for {plan_type}",
                "customer": {
                    "name": f"User {user_id}",
                    "contact": "+919999999999",  # Placeholder
                    "email": f"user{user_id}@example.com"  # Placeholder
                },
                "notify": {
                    "sms": False,
                    "email": False
                },
                "reminder_enable": True,
                "notes": {
                    "user_id": str(user_id),
                    "plan_type": plan_type
                },
                "callback_url": "https://example.com/callback",
                "callback_method": "get"
            }
            
            payment_link = razor_client.payment_link.create(data=payment_link_data)
            payment_link_id = payment_link["id"]
            
            # Store payment link details
            payment_orders[payment_link_id] = {
                "user_id": user_id,
                "amount": amount,
                "plan_type": plan_type,
                "created_at": int(time.time())
            }
            
            # Get payment link URL and QR code
            payment_url = payment_link["short_url"]
            qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={payment_url}"
            
            return payment_link_id, payment_url, qr_image_url
            
        except Exception as e:
            print(f"Error creating payment link: {e}")
            # Fallback to simple payment URL
            simple_url = f"https://razorpay.me/@{user_id}{int(time.time())}"
            qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={simple_url}"
            return f"fallback_{user_id}", simple_url, qr_image_url
        
 #   except Exception as e:
  #      raise Exception(f"Failed to create payment order: {str(e)}")

async def download_qr_image(qr_image_url, user_id):
    """Download QR image from Razorpay"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(qr_image_url) as response:
                if response.status == 200:
                    qr_path = f"payment_qr_{user_id}.png"
                    with open(qr_path, 'wb') as f:
                        f.write(await response.read())
                    return qr_path
                else:
                    raise Exception(f"Failed to download QR image: {response.status}")
        
    except Exception as e:
        raise Exception(f"Failed to download QR code: {str(e)}")

async def check_payment_status(order_id):
    """Check payment status from Razorpay"""
    try:
        order = razor_client.order.fetch(order_id)
        return order.get("status", "created")
        
    except Exception as e:
        print(f"Error checking payment status: {e}")
        return "error"

async def get_plan_from_order(order_id):
    """Get plan details from order"""
    return payment_orders.get(order_id, {"days": 30, "amount": 50})

async def start_payment_monitor(client, message, order_id, user_id, plan):
    """Monitor payment status and update message"""
    start_time = time.time()
    timeout_minutes = 15
    
    while time.time() - start_time < timeout_minutes * 60:
        try:
            status = await check_payment_status(order_id)
            
            if status == "paid":
                # Authorize user as premium
                from config import collection
                authorize_premium_user(collection, user_id, plan["days"])
                
                success_message = f"""
✅ **Payment Successful!**

🎉 **Congratulations!** You are now a Premium user for {plan["days"]} days!

🌟 **Your Premium Benefits:**
- Per file size limit: 3GB
- Storage limit: 10GB
- No ads
- Priority downloads
- Fast processing

Thank you for your purchase! 🚀
                """
                
                await message.edit_caption(
                    success_message,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
                )
                break
                
        except Exception as e:
            print(f"Error in payment monitor: {e}")
            
        await asyncio.sleep(30)  # Check every 30 seconds
    
    else:
        # Payment timeout
        timeout_message = f"""
⏰ **Payment Timeout**

Your payment session has expired. The payment link is no longer valid.

You can try again with /premium command.
        """
        
        try:
            await message.edit_caption(
                timeout_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
            )
        except:
            pass

def reset_user(collection, user_id):
    """Reset user verification status"""
    timestamp = int(time.time()) - 12600
    storre_user(collection, user_id, timestamp)
    return collection.find_one({"user_id": user_id})

async def handle_clear_files(user_id, reply_markup=None):
    """Handle clearing user files"""
    user_path = os.path.join("zipper", str(user_id))
    
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
        os.makedirs(user_path, exist_ok=True)
        message_text = "All files and directories in your directory have been removed."
    else:
        message_text = "Your directory does not exist."
    
    return message_text

async def create_zip_file(client, callback_query, pass_protect=None):
    """Create ZIP file from user's files"""
    user_id = callback_query.from_user.id
    ggg = "."
    
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

    # Check channel membership
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
        from plugins.ui_components import back_buttons
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

    # Create zip file using Python zipfile module
    import zipfile
    import pyminizip
    
    try:
        if pass_protect and password:
            # Create password-protected zip
            file_paths = [os.path.join(user_dir, filename) for filename in files]
            prefixes = ["" for _ in files]  # No prefix for file names in zip
            pyminizip.compress_multiple(file_paths, prefixes, zip_filename, password, 5)
            await message.edit_text("Created password-protected ZIP file")
        else:
            # Create regular zip file
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    zipf.write(file_path, filename)
                    try:
                        await message.edit_text(f"Adding {filename} to ZIP...")
                    except Exception:
                        pass
            await message.edit_text("ZIP file created successfully")
    except Exception as e:
        await message.edit_text(f"Error creating ZIP: {str(e)}")
        return None, message

    return zip_filename, message

def get_admin_ids():
    """Get list of admin IDs"""
    ggg = os.getcwd()
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            return [int(line.strip()) for line in file.readlines()]
    return []

async def broadcast_message(app, collection, message):
    """Broadcast message to all users"""
    stored_user_ids = [user["user_id"] for user in collection.find()]
    success_count = 0

    if message.reply_to_message:
        for user_id in stored_user_ids:
            try:
                await message.reply_to_message.forward(user_id)
                success_count += 1
            except Exception as e:
                print(f"Failed to forward message: {e}")
        
        await message.reply_text(f"Broadcasted to {success_count} users")

def authorize_premium_user_legacy(collection, user_id, days=30):
    """Legacy function - use authorize_premium_user instead"""
    return authorize_premium_user(collection, user_id, days)

def reset_user(collection, user_id):
    """Reset user verification status"""
    timestamp = int(time.time()) - 12600
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)
    return collection.find_one({"user_id": user_id})

# User management functions
def store_user(collection, user_id):
    """Store user with current timestamp"""
    timestamp = int(time.time())
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_userr(collection, user_id):
    """Store user with timestamp 6 hours ago"""
    timestamp = int(time.time()) - 21600
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_code(collection, user_id, verifycode):
    """Store verification code for user"""
    user_data = {"user_id": user_id, "verifycode": verifycode}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)


def generate_random_code(length=10):
    """Generate random verification code"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_user_status(collection, user_id):
    """Get user verification status and limits"""
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
        return False, 200 * 1024 * 1024, 200 * 1024 * 1024

    stored_time = user_data["timestamp"]
    time_difference = current_time - stored_time

    if time_difference < 0:  # Premium user
        return True, 10 * 1024 * 1024 * 1024, 3.5 * 1024 * 1024 * 1024
    elif time_difference < 21600:  # Verified user
        return True, 4.5 * 1024 * 1024 * 1024, 2.5 * 1024 * 1024 * 1024
    else:  # Non-verified user
        return False, 200 * 1024 * 1024, 200 * 1024 * 1024

# File operations utilities
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

# Verification utilities
async def send_verification_link(message, collection):
    """Send verification link to user"""
    code = generate_random_code()
    store_code(collection, message.from_user.id, code)
    long = f'http://t.me/FILEs_COMPRESSOR_BOT?start=verifycodeis{code}'
    url = f'https://api.cuty.io/quick?token=b09763cdea0deb0cc373ca5eb&url={long}'

    try:
        response = requests.get(url, verify=False)
        data = response.json()
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
        print(f"Error in send_verification_link: {e}")

def get_queue_status(user_id):
    """Get current queue status for user"""
    from config import download_queue, premium_queue, download_in_progress, active_user_id, user_ids
    
    regular_queue_size = download_queue.qsize()
    premium_queue_size = premium_queue.qsize()

    status = f"**Queue Status:**\n\n"

    if download_in_progress:
        status += f"🔄 **Currently downloading for user:** {active_user_id}\n\n"
    else:
        status += "✅ **No active downloads**\n\n"

    status += f"📋 **DOWNLOAD IN QUEUE:**\n"
    status += f"Regular users: {regular_queue_size} tasks\n"
    status += f"Premium users: {premium_queue_size} tasks\n\n"

    if user_id in user_ids:
        if download_in_progress and active_user_id == user_id:
            status += "🎯 **Your download is currently active!**"
        else:
            # Calculate position in queue
            position = premium_queue_size + 1 if user_id not in user_ids else regular_queue_size
            status += f"⏳ **Your position in queue:** {position}"
    else:
        status += "ℹ️ **You have no files in queue**"

    return status

