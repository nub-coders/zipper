from config import *
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from tools import store_userr, get_user_status, store_user, send_verification_link
from plugins.ui_components import home_buttons, common_buttons
from plugins.installer import get_database_collection
import time

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
            return await message.reply_text("You are already verified", quote=True, reply_to_message_id=message.id)

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

    await message.reply_text(help_message, reply_markup=common_buttons, quote=True, reply_to_message_id=message.id)

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
    
    await message.reply_text(premium_benefits, reply_markup=plans_keyboard, quote=True, reply_to_message_id=message.id)

# Payment functions moved from tools.py
import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
razor_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

async def create_payment_order(amount, user_id, plan_type):
    """Create Razorpay payment order with QR code"""
    order_data = {
        "amount": amount * 100,  # Amount in paise
        "currency": "INR",
        "receipt": f"premium_{user_id}_{int(time.time())}",
        "notes": {
            "user_id": str(user_id),
            "plan_type": plan_type
        }
    }
    
    order = razor_client.order.create(data=order_data)
    if not order or "id" not in order:
        raise Exception("Invalid response from Razorpay")
        
    # Create QR code
    qr_data = {
        "type": "upi_qr",
        "name": "Premium Subscription",
        "usage": "single_use",
        "fixed_amount": True,
        "payment_amount": amount * 100,
        "description": f"Premium {plan_type} plan",
        "customer_id": str(user_id)
    }
    qr_code = razor_client.qrcode.create(data=qr_data)
    
    return {
        "order_id": order["id"],
        "payment_link": f"https://razorpay.me/@{order['id']}",
        "qr_url": qr_code["image_url"]
    }

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
    payment_msg = await client.send_photo(
        callback_query.message.chat.id,
        qr_path,
        caption=payment_message,
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

    await message.reply_text(status_message, quote=True, reply_to_message_id=message.id)
