from config import *
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from tools import store_userr, get_user_status, store_user, send_verification_link
from plugins.ui_components import home_buttons, common_buttons
import time
import os
import requests
import asyncio

async def download_qr_image(url: str, user_id: int) -> str:
    """Download QR code image and return local path"""
    if not url or url == "qr_url" or not url.startswith("http"):
        # Create a simple text file instead of QR if URL is invalid
        user_dir = f"./user_{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        file_path = f"{user_dir}/payment_info.txt"
        with open(file_path, "w") as file:
            file.write("Payment QR code not available. Please use the payment link.")
        return file_path

    user_dir = f"./user_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    file_path = f"{user_dir}/razorpay_qr.png"

    try:
        qr_image_response = requests.get(url)
        if qr_image_response.status_code == 200:
            with open(file_path, "wb") as file:
                file.write(qr_image_response.content)
            return file_path
    except Exception as e:
        print(f"Error downloading QR image: {e}")

    # Fallback to text file
    file_path = f"{user_dir}/payment_info.txt"
    with open(file_path, "w") as file:
        file.write("Payment QR code not available. Please use the payment link.")
    return file_path

@Client.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
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
            return await message.reply_text("You are already verified", quote=True, reply_parameters={"message_id": message.id})

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

@Client.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
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

    await message.reply_text(help_message, reply_markup=common_buttons, quote=True, reply_parameters={"message_id": message.id})

@Client.on_message(filters.command("premium"))
async def premium_info(client: Client, message: Message):
    premium_benefits = """
🌟 **Premium Benefits:**
<blockquote>- Per file size limit increased to 3GB
- Storage limit increased to 10GB
- No ads for 30 days
- Priority downloads
- Fast downloads and uploads</blockquote>

💰 **Choose Your Plan:**
    """

    plans_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Weekly Plan - ₹15 ($0.18)", callback_data="plan_weekly")],
        [InlineKeyboardButton("📆 Monthly Plan - ₹50 ($0.60)", callback_data="plan_monthly")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/nub_coder_s")]
    ])

    await message.reply_text(premium_benefits, reply_markup=plans_keyboard, quote=True, reply_parameters={"message_id": message.id})

# Payment system imports
import razorpay
import qrcode
import io
import asyncio
from PIL import Image
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

# Razorpay configuration
razor_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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
        # Create payment link
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
            }
        }
        
        payment_link = razor_client.payment_link.create(data=payment_link_data)
        payment_link_id = payment_link["id"]
        
        # Store payment link details
        payment_orders[payment_link_id] = {
            "user_id": user_id,
            "amount": amount,
            "plan_type": plan_type,
            "created_at": int(time.time()),
            "days": 7 if plan_type == "weekly" else 30
        }
        
        # Get payment link URL - updated format
        payment_url = payment_link.get("short_url", f"https://rzp.io/rzp/{payment_link_id}")
        qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={payment_url}"
        
        return payment_link_id, payment_url, qr_image_url
        
    except Exception as e:
        print(f"Error creating payment link: {e}")
        # Fallback to simple payment URL
        simple_url = f"https://razorpay.me/@nubcoder/{amount}"
        qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={simple_url}"
        return f"fallback_{user_id}_{int(time.time())}", simple_url, qr_image_url

async def download_qr_image(qr_image_url, user_id):
    """Download QR image from Razorpay"""
    try:
        import aiohttp
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

async def check_payment_status(payment_link_id):
    """Check payment status from Razorpay"""
    try:
        # Check if it's a fallback payment
        if payment_link_id.startswith("fallback_"):
            return "pending"
            
        # Get payment link details
        payment_link = razor_client.payment_link.fetch(payment_link_id)
        status = payment_link.get("status", "created")
        
        # Check if any payments were made to this link
        if status == "paid":
            return "paid"
        elif status == "partially_paid":
            return "paid"  # Accept partial payments as well
        else:
            return "pending"
        
    except Exception as e:
        print(f"Error checking payment status: {e}")
        return "error"

async def get_plan_from_order(order_id):
    """Get plan details from order"""
    return payment_orders.get(order_id, {"days": 30, "amount": 50})

async def start_payment_monitor(client, message, payment_link_id, user_id, plan_details):
    """Monitor payment status and update message"""
    start_time = time.time()
    timeout_minutes = 30  # Increased timeout
    check_interval = 15  # Check every 15 seconds for better responsiveness
    
    print(f"Starting payment monitor for user {user_id}, payment_link_id: {payment_link_id}")
    
    while time.time() - start_time < timeout_minutes * 60:
        try:
            status = await check_payment_status(payment_link_id)
            print(f"Payment status for {payment_link_id}: {status}")
            
            if status == "paid":
                # Authorize user as premium
                days = plan_details.get("days", 30)
                authorize_premium_user(collection, user_id, days)
                
                success_message = f"""
✅ **Payment Successful!**

🎉 **Congratulations!** You are now a Premium user for {days} days!

🌟 **Your Premium Benefits:**
- Per file size limit: 3.2GB
- Storage limit: 10GB
- No ads for {days} days
- Priority downloads
- Fast processing

Thank you for your purchase! 🚀
                """
                
                try:
                    await message.edit_text(
                        success_message,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
                    )
                except:
                    await message.edit_caption(
                        success_message,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
                    )
                
                # Clean up payment order
                if payment_link_id in payment_orders:
                    del payment_orders[payment_link_id]
                    
                print(f"Payment successful for user {user_id}")
                break
                
        except Exception as e:
            print(f"Error in payment monitor: {e}")
            
        await asyncio.sleep(check_interval)
    
    else:
        # Payment timeout
        timeout_message = f"""
⏰ **Payment Timeout**

Your payment session has expired after {timeout_minutes} minutes.

The payment link is no longer being monitored. If you completed the payment, please contact support with your payment details.

You can try again with /premium command.
        """
        
        try:
            await message.edit_text(
                timeout_message,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Home", callback_data="home")],
                    [InlineKeyboardButton("💬 Contact Support", url="https://t.me/nub_coder_s")]
                ])
            )
        except:
            try:
                await message.edit_caption(
                    timeout_message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Home", callback_data="home")],
                        [InlineKeyboardButton("💬 Contact Support", url="https://t.me/nub_coder_s")]
                    ])
                )
            except:
                pass
        
        # Clean up payment order
        if payment_link_id in payment_orders:
            del payment_orders[payment_link_id]
            
        print(f"Payment timeout for user {user_id}, payment_link_id: {payment_link_id}")

# Payment callback handlers moved from callback_handlers.py
@Client.on_callback_query(filters.regex("plan_"))
async def handle_plan_selection(client: Client, callback_query: CallbackQuery):
    plan_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    plans = {
        "weekly": {"amount": 15, "days": 7, "usd": 0.18},
        "monthly": {"amount": 50, "days": 30, "usd": 0.60}
    }

    if plan_type not in plans:
        return await callback_query.answer("Invalid plan selected!", show_alert=True)

    plan = plans[plan_type]
    order_id, payment_link, qr_image_url = await create_payment_order(plan["amount"], user_id, plan_type)
    qr_path = await download_qr_image(qr_image_url, user_id)

    payment_message = f"""
💳 **Payment for {plan_type.title()} Premium Plan**

💰 **Amount:** ₹{plan['amount']} (${plan['usd']})
⏰ **Validity:** {plan['days']} days
🕒 **Payment expires in:** 15 minutes

🔗 **Payment Link:** {payment_link}

⚡ **Scan QR or click link to pay**
    """

    verify_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_{order_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
    ])

    await callback_query.message.delete()

    # Check if QR path is an image or text file
    if qr_path.endswith('.png'):
        payment_msg = await client.send_photo(
            callback_query.message.chat.id,
            qr_path,
            caption=payment_message,
            reply_markup=verify_button
        )
    else:
        # Send as text message if QR not available
        payment_msg = await client.send_message(
            callback_query.message.chat.id,
            payment_message,
            reply_markup=verify_button
        )

    asyncio.create_task(start_payment_monitor(client, payment_msg, order_id, user_id, plan))

@Client.on_callback_query(filters.regex("verify_"))
async def verify_payment(client: Client, callback_query: CallbackQuery):
    order_id = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id

    payment_status = await check_payment_status(order_id)
    if payment_status == "paid":
        plan_info = await get_plan_from_order(order_id)
        authorize_premium_user(collection, user_id, plan_info["days"])

        success_message = f"""
✅ **Payment Successful!**

🎉 **Congratulations!** You are now a Premium user for {plan_info["days"]} days!

🌟 **Your Premium Benefits:**
- Per file size limit: 3GB
- Storage limit: 10GB
- No ads
- Priority downloads
- Fast processing

Thank you for your purchase! 🚀
        """
        await callback_query.edit_message_caption(
            success_message,
            reply_markup=home_buttons
        )
    else:
        await callback_query.answer("Payment not found or still pending. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex("cancel_payment"))
async def cancel_payment(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_caption(
        "❌ Payment cancelled. You can try again anytime with /premium command.",
        reply_markup=home_buttons
    )

@Client.on_message(filters.command("status"))
async def user_status(client: Client, message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference = current_time - stored_time

        if time_difference < 0:
            status = "💎 Premium 💎"
            total_storage = "10 GB"
            file_size = "3.2 GB"
            ads = "✨ No ads! ✨"
            time_difference *=-1
        elif time_difference < 21600:
            status = "🌟 Elite 🌟"
            total_storage = "4.5 GB"
            file_size = "2 GB"
            ads = "Some ads"
            time_difference *=-1
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

    await message.reply_text(status_message, quote=True, reply_parameters={"message_id": message.id})