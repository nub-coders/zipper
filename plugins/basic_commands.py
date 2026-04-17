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

# Binance setup for crypto payments
import hmac
import hashlib
import requests
from decimal import Decimal
from config import BINANCE_API_KEY, BINANCE_API_SECRET, CRYPTO_USDT_AMOUNTS, db


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
        [InlineKeyboardButton("🪙 Pay with Crypto (USDT)", callback_data="crypto_choose_plan")],
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


# ─── Binance Crypto Payment Functions ────────────────────────────────────────

def verify_binance_deposit(tx_hash: str, asset: str = "USDT", min_amount: float = 0.0) -> tuple:
    """Strictly verify a Binance deposit by tx hash.

    Accept only if:
      - Matching txId and coin
      - Status == 1 (credited)
      - Amount == expected (neither greater nor smaller)

    Returns (ok: bool, message: str)
    """
    import time
    endpoint = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    timestamp = int(time.time() * 1000)
    params = {
        "timestamp": timestamp,
        "recvWindow": 60000,
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    signature = hmac.new(BINANCE_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    url = f"{endpoint}?{query_string}&signature={signature}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        j = r.json()
    except Exception as e:
        return False, f"Network error: {e}"
    if not isinstance(j, list):
        return False, f"Binance API error: {j}"

    expected = Decimal(str(min_amount))
    for dep in j:
        if dep.get("txId") != tx_hash or dep.get("coin") != asset:
            continue
        status = dep.get("status")  # 1 = success
        amount_raw = dep.get("amount", 0)
        try:
            received = Decimal(str(amount_raw))
        except Exception:
            return False, f"Unable to parse deposit amount: {amount_raw}"

        if status != 1:
            return False, f"Deposit found but not credited yet (status {status}). Please wait for confirmation."

        if received != expected:
            cmp = "greater" if received > expected else "smaller"
            return False, (
                f"Amount mismatch: expected {expected} {asset}, received {received} ({cmp}). "
                f"Please deposit exactly {expected} {asset}."
            )

        # All conditions satisfied
        return True, f"Deposit confirmed: {received} {asset}"

    return False, "No matching deposit found yet. Make sure you entered the correct TX Hash and try again later."


def get_binance_deposit_address(coin: str = "USDT", network: str = "BSC") -> tuple[bool, dict[str, str]]:
    """Fetch your Binance deposit address for a given coin/network.
    Returns (ok, {address, tag, url, raw}) or (False, {error})
    """
    ts = int(time.time() * 1000)
    recv = 60000
    endpoint = "https://api.binance.com/sapi/v1/capital/deposit/address"
    params = f"coin={coin}&network={network}&timestamp={ts}&recvWindow={recv}"
    sig = hmac.new(BINANCE_API_SECRET.encode(), params.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    url = f"{endpoint}?{params}&signature={sig}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        j = r.json()
    except Exception as e:
        return False, {"error": f"Network error: {e}"}

    if isinstance(j, dict) and j.get("success") is False:
        return False, {"error": j.get("msg", "Binance error")}

    if isinstance(j, dict) and j.get("address"):
        return True, {
            "address": j.get("address"),
            "tag": j.get("tag") or "",
            "url": j.get("url") or "",
            "raw": j,
        }
    # Unexpected structure
    return False, {"error": f"Unexpected response: {j}"}


# ─── Crypto Payment Handlers ─────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^crypto_choose_plan$"))
async def crypto_choose_plan_handler(client: Client, callback_query):
    weekly_usdt = CRYPTO_USDT_AMOUNTS["weekly"]
    monthly_usdt = CRYPTO_USDT_AMOUNTS["monthly"]
    await callback_query.edit_message_text(
        "🪙 Choose a Crypto Plan (USDT via Binance Deposit)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Weekly (7 Days — {weekly_usdt} USDT ≈ ₹15)", callback_data="crypto_plan:weekly", style="primary")],
            [InlineKeyboardButton(f"Monthly (30 Days — {monthly_usdt} USDT ≈ ₹50)", callback_data="crypto_plan:monthly", style="primary")],
        ])
    )


@Client.on_callback_query(filters.regex(r"^crypto_plan:(weekly|monthly)$"))
async def crypto_plan_handler(client: Client, callback_query):
    plan_type = callback_query.matches[0].group(1)
    await callback_query.edit_message_text(
        "🌐 Select the network for your USDT deposit:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Network: BSC (BEP20)", callback_data=f"binance_plan:BSC:{plan_type}")],
            [InlineKeyboardButton("Network: TRC20 (TRON)", callback_data=f"binance_plan:TRX:{plan_type}")],
            [InlineKeyboardButton("Network: ERC20 (Ethereum)", callback_data=f"binance_plan:ETH:{plan_type}")],
        ])
    )


@Client.on_callback_query(filters.regex(r'binance_plan:(BSC|TRX|ETH):(weekly|monthly)'))
async def binance_plan_handler(client: Client, callback_query):
    user_id = callback_query.from_user.id
    network = callback_query.matches[0].group(1).decode()
    plan_type = callback_query.matches[0].group(2).decode()
    amount_usdt = float(CRYPTO_USDT_AMOUNTS[plan_type])
    duration_days = 7 if plan_type == "weekly" else 30
    inr_equiv = 15 if plan_type == "weekly" else 50
    ok_addr, addr_info = get_binance_deposit_address("USDT", network)
    if not ok_addr:
        return await callback_query.edit_message_text(f"❌ Could not fetch Binance deposit address: {addr_info.get('error')}\nPlease try again later or contact support.")

    address = addr_info.get("address", "")
    tag = addr_info.get("tag", "")
    qr_url = f"https://quickchart.io/qr?text={address}&margin=2&size=400"

    text = (
        f"<b>USDT Deposit (via Binance)</b>\n\n"
        f"Send <b>{amount_usdt} USDT</b> (~₹{inr_equiv}) on <b>{'BSC (BEP20)' if network=='BSC' else ('TRC20 (TRON)' if network=='TRX' else 'ERC20 (Ethereum)')}</b> to:\n"
        f"<code>{address}</code>\n"
        + (f"Memo/Tag: <code>{tag}</code>\n" if tag else "") +
        "\nAfter sending, reply with your <b>transaction hash</b> here.\n"
        "You have 15 minutes to complete this step.\n\n"
        f"Plan: <b>{plan_type.capitalize()}</b> — {duration_days} days"
    )
    try:
        await callback_query.edit_message_text(text, parse_mode='html')
        # Send QR code
        await client.send_photo(
            callback_query.message.chat.id,
            qr_url,
            caption="Scan this QR code to copy the address"
        )
    except Exception as e:
        await callback_query.edit_message_text(text, parse_mode='html')
        print(f"Error sending QR: {e}")

    # Start conversation for TX hash
    try:
        async with client.conversation(callback_query.message.chat.id, timeout=900) as conv:
            await conv.send_message("Please send your tx hash (0x… or 64-hex) or type CANCEL.")
            msg = await conv.wait_event(filters.text & filters.user(user_id))
            if msg.text.lower() == 'cancel':
                return await conv.send_message("Binance payment cancelled.")
            txh = msg.text.strip()
            # Accept BSC/ETH (0x + 64 hex) and TRX (64 hex, no 0x)
            if not ((txh.startswith('0x') and len(txh) == 66) or (len(txh) == 64)):
                return await conv.send_message("Invalid tx hash format. Please send the 64-hex tx id.")

            # Prevent reuse of tx hash
            if db.used_tx_hashes.find_one({"tx_hash": txh}):
                return await conv.send_message("❌ This transaction hash has already been used for a premium purchase.")

            ok, reason = verify_binance_deposit(txh, asset="USDT", min_amount=amount_usdt)
            if not ok:
                return await conv.send_message(f"❌ Verification failed: {reason}")

            # Success — grant premium
            user_data = collection.find_one({"user_id": user_id}) or {}
            ldays = 0
            stored_time = user_data.get("timestamp", 0)
            time_difference = stored_time - int(time.time())
            if time_difference > 0:
                ldays = time_difference // (24 * 3600)
            days = duration_days
            timestamp = int(time.time()) + ((days + ldays) * 24 * 60 * 60)

            collection.update_one(
                {"user_id": user_id},
                {"$set": {"timestamp": timestamp, "premium_by": "BINANCE"}},
                upsert=True,
            )
            # Store used tx hash to prevent reuse
            db.used_tx_hashes.update_one(
                {"tx_hash": txh},
                {"$set": {"user_id": user_id, "plan_type": plan_type, "timestamp": int(time.time())}},
                upsert=True,
            )
            try:
                await conv.send_message(
                    f"✅ Deposit confirmed!\n"
                    f"Premium activated for <b>{days}</b> days. Enjoy!",
                    parse_mode='html',
                )
            except Exception as e:
                print(f"Error sending success message: {e}")

    except Exception as e:
        print(f"Error in binance payment handler: {e}")
        await callback_query.message.reply_text("Payment session timed out. Try again with /premium")


# ─── Razorpay Payment Handlers ───────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^plan_(weekly|monthly)$"))
async def plan_handler(client: Client, callback_query):
    plan_type = callback_query.matches[0].group(1)
    amount = 15 if plan_type == "weekly" else 50
    days = 7 if plan_type == "weekly" else 30
    user_id = callback_query.from_user.id

    try:
        pl_id, payment_url, qr_url = await create_payment_order(amount, user_id, plan_type)
        plan_details = {"days": days, "amount": amount}

        text = (
            f"💎 **{plan_type.capitalize()} Premium Plan**\n\n"
            f"📅 Duration: {days} days\n"
            f"💰 Amount: ₹{amount}\n\n"
            f"🔗 Pay here: {payment_url}\n\n"
            f"⏰ You have 30 minutes to complete payment."
        )

        await callback_query.edit_message_text(text)
        await client.send_photo(
            callback_query.message.chat.id,
            qr_url,
            caption="Scan QR code to pay"
        )

        # Start payment monitoring
        asyncio.create_task(start_payment_monitor(client, callback_query.message, pl_id, user_id, plan_details))

    except Exception as e:
        print(f"Error creating payment: {e}")
        await callback_query.edit_message_text("❌ Payment gateway error. Please try later.")
