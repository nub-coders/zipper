import config
from config import *
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from tools import get_user_status, get_file_size_info, authorize_premium_user
from plugins.ui_components import home_buttons, common_buttons
from stats_manager import stats_manager
import time
import os
import asyncio

# Razorpay setup
import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

razor_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
payment_orders = {}


# ─── Basic Commands ───────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **Welcome to File Zipper Bot!**\n\n"
        "I can help you:\n"
        "📁 Compress files into ZIP archives\n"
        "🔐 Create password-protected ZIPs\n"
        "📥 Download files from direct links\n"
        "📦 Manage your uploaded files\n\n"
        "🚀 Send me any files or direct download links to get started!\n"
        "❔ Use /help for detailed instructions",
        reply_markup=home_buttons,
    )


@Client.on_message(filters.private & filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = (
        "📚 **File Zipper Bot Help Guide**\n\n"
        "🤖 I can help you compress and manage files easily!\n\n"
        "📋 **Available Commands:**\n"
        "<blockquote>🏠 /start - Return to main menu</blockquote>\n"
        "<blockquote>📂 /my_files - View your uploaded files</blockquote>\n"
        "<blockquote>🗑️ /clear - Remove all your files</blockquote>\n"
        "<blockquote>🔐 /fzip - Create a ZIP archive</blockquote>\n"
        "<blockquote>📊 /status - View your usage statistics</blockquote>\n"
        "<blockquote>❔ /help - Show this help guide</blockquote>\n\n"
        "📤 **How to Use:**\n"
        "<blockquote>1. Send me any files or download links</blockquote>\n"
        "<blockquote>2. Use /fzip when ready to create ZIP</blockquote>\n"
        "<blockquote>3. Choose password protection if needed</blockquote>\n"
        "<blockquote>4. Download your compressed file</blockquote>\n\n"
        "💾 **Storage Limits:**\n"
        "<blockquote>• Maximum file size: 3.5 GB</blockquote>\n"
        "<blockquote>• Total storage: 10 GB</blockquote>\n\n"
        "📞 **Need Help?**\n"
        "<blockquote>Join our support channel @nub_coder_s</blockquote>\n"
        "<blockquote>Join main channel @nub_coders</blockquote>\n\n"
        "🚀 Happy compressing!"
    )
    await message.reply_text(
        help_text,
        reply_markup=common_buttons,
        quote=True,
        reply_parameters={"message_id": message.id},
    )


@Client.on_message(filters.private & filters.command("premium"))
async def premium_info(client: Client, message: Message):
    plans_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Weekly Plan - ₹15 ($0.18)", callback_data="plan_weekly")],
        [InlineKeyboardButton("📆 Monthly Plan - ₹50 ($0.60)", callback_data="plan_monthly")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/nub_coder_s")],
    ])
    await message.reply_text(
        "🌟 **Premium Benefits:**\n"
        "<blockquote>- Per file size limit increased to 3GB\n"
        "- Storage limit increased to 10GB\n"
        "- No ads for 30 days\n"
        "- Priority downloads\n"
        "- Fast downloads and uploads</blockquote>\n\n"
        "💰 **Choose Your Plan:**",
        reply_markup=plans_keyboard,
        reply_to_message_id=message.id,
    )


# ─── Status Commands ─────────────────────────────────────────────────────────

async def _build_status_message(user_id):
    """Build a status text string and appropriate buttons for the given user."""
    user_stats = await stats_manager.get_user_stats(user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    _, max_storage, max_file_size = get_user_status(collection, user_id)
    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

    text = (
        f"📊 **Your Statistics**\n\n"
        f"📥 Files Processed: {user_stats['files_sent']}\n"
        f"🔒 Password-Protected ZIPs: {user_stats['zip_with_pass']}\n"
        f"📦 Regular ZIPs: {user_stats['zip_without_pass']}\n"
        f"☁️ External Uploads: {user_stats['external_uploads']}\n\n"
        f"💾 **Storage Information**\n"
        f"📦 Used Storage: {total_size / (1024**3):.2f} GB\n"
        f"📊 Available Storage: {remaining_storage / (1024**3):.2f} GB\n"
        f"📁 Total Files: {len(files)}\n\n"
        f"⚡ **File Size Limit:** {max_file_size / (1024**3):.1f} GB"
    )

    # Show activity info and cancel button if user has an active task
    markup = home_buttons
    if config.active_user_id == user_id:
        if config.download_in_progress:
            text += "\n\n🔄 **Status:** Downloading a file…"
        elif config.zipping_in_progress:
            text += "\n\n🔄 **Status:** Compressing files…"
        elif config.uploading_in_progress:
            text += "\n\n🔄 **Status:** Uploading file…"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Cancel All Tasks", callback_data="cancel_all")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ])
    elif user_id in config.user_ids:
        # User has queued items
        text += "\n\n⏳ **Status:** Your files are in queue"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Cancel All Tasks", callback_data="cancel_all")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ])

    return text, markup


@Client.on_callback_query(filters.regex("status"))
async def status_handler(client: Client, callback_query):
    text, markup = await _build_status_message(callback_query.from_user.id)
    await callback_query.edit_message_text(text, reply_markup=markup)


@Client.on_message(filters.private & filters.command("status"))
async def user_status(client: Client, message: Message):
    text, markup = await _build_status_message(message.from_user.id)
    await message.reply_text(text, reply_markup=markup, quote=True, reply_to_message_id=message.id)


# ─── Payment System ──────────────────────────────────────────────────────────

def storre_user(collection, user_id, timestamp=None):
    """Store user with timestamp."""
    if timestamp is None:
        timestamp = int(time.time())
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)
    return collection.find_one({"user_id": user_id})


async def create_payment_order(amount, user_id, plan_type):
    """Create Razorpay payment order with payment link."""
    try:
        payment_link_data = {
            "amount": amount * 100,
            "currency": "INR",
            "description": f"Premium subscription for {plan_type}",
            "notes": {"user_id": str(user_id), "plan_type": plan_type},
        }
        try:
            payment_link = razor_client.payment_link.create(data=payment_link_data)
            pl_id = payment_link["id"]
            if "short_url" not in payment_link:
                payment_link["short_url"] = f"https://rzp.io/i/{pl_id}"
        except Exception as e:
            raise Exception(f"Payment link creation failed: {e}")

        payment_orders[pl_id] = {
            "user_id": user_id,
            "amount": amount,
            "plan_type": plan_type,
            "created_at": int(time.time()),
            "days": 7 if plan_type == "weekly" else 30,
        }

        payment_url = payment_link.get("short_url", f"https://rzp.io/rzp/{pl_id}")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={payment_url}"
        return pl_id, payment_url, qr_url

    except Exception as e:
        print(f"Error creating payment link: {e}")
        simple_url = f"https://razorpay.me/@nubcoder/{amount}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={simple_url}"
        return f"fallback_{user_id}_{int(time.time())}", simple_url, qr_url


async def download_qr_image(qr_image_url, user_id):
    """Download QR image and return local path."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(qr_image_url) as resp:
                if resp.status == 200:
                    qr_path = f"payment_qr_{user_id}.png"
                    with open(qr_path, "wb") as f:
                        f.write(await resp.read())
                    return qr_path
                raise Exception(f"Failed to download QR image: {resp.status}")
    except Exception as e:
        raise Exception(f"Failed to download QR code: {e}")


async def check_payment_status(payment_link_id):
    """Check payment status from Razorpay."""
    try:
        if payment_link_id.startswith("fallback_"):
            return "pending"
        link = razor_client.payment_link.fetch(payment_link_id)
        return "paid" if link.get("status") == "paid" else "pending"
    except Exception as e:
        print(f"Error checking payment status: {e}")
        return "error"


async def get_plan_from_order(order_id):
    """Get plan details from order."""
    return payment_orders.get(order_id, {"days": 30, "amount": 50})


async def start_payment_monitor(client, message, payment_link_id, user_id, plan_details):
    """Monitor payment status and update message upon success or timeout."""
    timeout_minutes = 30
    check_interval = 15
    start = time.time()

    print(f"Starting payment monitor for user {user_id}, link: {payment_link_id}")

    while time.time() - start < timeout_minutes * 60:
        try:
            status = await check_payment_status(payment_link_id)
            print(f"Payment status for {payment_link_id}: {status}")

            if status == "paid":
                days = plan_details.get("days", 30)
                authorize_premium_user(collection, user_id, days)
                success_msg = (
                    f"✅ **Payment Successful!**\n\n"
                    f"🎉 **Congratulations!** You are now a Premium user for {days} days!\n\n"
                    f"🌟 **Your Premium Benefits:**\n"
                    f"- Per file size limit: 3.2GB\n"
                    f"- Storage limit: 10GB\n"
                    f"- No ads for {days} days\n"
                    f"- Priority downloads\n"
                    f"- Fast processing\n\n"
                    f"Thank you for your purchase! 🚀"
                )
                home_btn = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
                )
                try:
                    await message.edit_text(success_msg, reply_markup=home_btn)
                except Exception:
                    await message.edit_caption(success_msg, reply_markup=home_btn)

                payment_orders.pop(payment_link_id, None)
                print(f"Payment successful for user {user_id}")
                return
        except Exception as e:
            print(f"Error in payment monitor: {e}")

        await asyncio.sleep(check_interval)

    # Timeout
    timeout_msg = (
        f"⏰ **Payment Timeout**\n\n"
        f"Your payment session has expired after {timeout_minutes} minutes.\n\n"
        f"If you completed the payment, please contact support.\n"
        f"Try again with /premium command."
    )
    timeout_btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
        [InlineKeyboardButton("💬 Contact Support", url="https://t.me/nub_coder_s")],
    ])
    try:
        await message.edit_text(timeout_msg, reply_markup=timeout_btns)
    except Exception:
        try:
            await message.edit_caption(timeout_msg, reply_markup=timeout_btns)
        except Exception:
            pass

    payment_orders.pop(payment_link_id, None)
    print(f"Payment timeout for user {user_id}, link: {payment_link_id}")
