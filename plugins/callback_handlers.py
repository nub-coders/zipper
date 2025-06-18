from config import *
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from plugins.ui_components import home_buttons, back_buttons, pass_button
from tools import store_userr, get_user_status, Timer, upload_to_gofile, is_user_on_chat, get_queue_status
from plugins.installer import get_database_collection
import os
import subprocess
import shutil
import time
import random
import asyncio

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
    from tools import get_queue_status
    user_id = callback_query.from_user.id
    response_text = get_queue_status(user_id)

    try:
        await callback_query.answer(response_text, show_alert=True)
    except Exception:
        global dd
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
    await list_files(client, callback_query)

@Client.on_callback_query(filters.regex("clear"))
async def callback_clear(client: Client, callback_query: CallbackQuery):
    from tools import handle_clear_files
    user_id = callback_query.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
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
        from tools import create_zip_file
        zip_filename, message = await create_zip_file(client, callback_query, pass_protect)

        if not zip_filename or not os.path.exists(zip_filename):
            return

        user_id = callback_query.from_user.id
        file_size = os.path.getsize(zip_filename)
        await callback_query.message.reply_text('compression completed now uploading file', quote=True, reply_to_message_id=callback_query.message.id)

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

            msg = await callback_query.message.reply_text("uploading started", quote=True, reply_to_message_id=callback_query.message.id)

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



@Client.on_callback_query(filters.regex("plan_"))
async def handle_plan_selection(client: Client, callback_query: CallbackQuery):
    from tools import create_payment_order, start_payment_monitor, download_qr_image, get_plan_from_order

    plan_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    # Define plan details
    plans = {
        "weekly": {"amount": 15, "days": 7, "usd": 0.18},
        "monthly": {"amount": 50, "days": 30, "usd": 0.60}
    }

    if plan_type not in plans:
        return await callback_query.answer("Invalid plan selected!", show_alert=True)

    plan = plans[plan_type]

    try:
        # Create payment order and QR
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

        # Delete original message and send payment info
        await callback_query.message.delete()

        payment_msg = await client.send_photo(
            callback_query.message.chat.id,
            qr_path,
            caption=payment_message,
            reply_markup=verify_button
        )

        # Start payment monitoring task
        asyncio.create_task(start_payment_monitor(client, payment_msg, order_id, user_id, plan))

    except Exception as e:
        await callback_query.answer(f"Error creating payment: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex("verify_"))
async def verify_payment(client: Client, callback_query: CallbackQuery):
    from tools import check_payment_status, authorize_premium_user, get_plan_from_order

    order_id = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id

    try:
        payment_status = await check_payment_status(order_id)

        if payment_status == "paid":
            # Get plan details from order
            plan_info = await get_plan_from_order(order_id)

            # Authorize premium user
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

    except Exception as e:
        await callback_query.answer(f"Error verifying payment: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex("cancel_payment"))
async def cancel_payment(client: Client, callback_query: CallbackQuery):
    await callback_query.edit_message_caption(
        "❌ Payment cancelled. You can try again anytime with /premium command.",
        reply_markup=home_buttons
    )

@Client.on_callback_query()
async def callback_query_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "bhad":  # Check queue callback
        queue_status = get_queue_status(user_id)
        await callback_query.answer()
        await callback_query.edit_message_text(queue_status)