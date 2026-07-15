import config
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from tools import get_user_status, get_file_size_info, get_text, set_user_lang
from plugins.ui_components import home_buttons, common_buttons
from stats_manager import get_user_stats
from config import collection


# ─── Basic Commands ───────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("start"))
async def start_command(client: Client, message: Message):
    text = get_text(collection, message.from_user.id, "start_msg")
    await message.reply_text(
        text,
        reply_markup=home_buttons,
    )


@Client.on_message(filters.private & filters.command("lang"))
async def lang_command(client: Client, message: Message):
    user_id = message.from_user.id
    lang_text = get_text(collection, user_id, "choose_lang")
    btn_en = get_text(collection, user_id, "lang_btn_en")
    btn_fa = get_text(collection, user_id, "lang_btn_fa")
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_en, callback_data="setlang_en")],
        [InlineKeyboardButton(btn_fa, callback_data="setlang_fa")]
    ])
    await message.reply_text(lang_text, reply_markup=markup)


@Client.on_callback_query(filters.regex(r"^setlang_(en|fa)$"))
async def set_lang_handler(client: Client, callback_query):
    user_id = callback_query.from_user.id
    lang_code = callback_query.matches[0].group(1)
    set_user_lang(collection, user_id, lang_code)
    
    success_msg = get_text(collection, user_id, "lang_set")
    await callback_query.edit_message_text(success_msg, reply_markup=home_buttons)


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
        reply_parameters=ReplyParameters(message_id=message.id),
    )


# ─── Status Commands ─────────────────────────────────────────────────────────

async def _build_status_message(user_id):
    """Build a status text string and appropriate buttons for the given user."""
    user_stats = await get_user_stats(user_id)
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
    if user_id in config.downloading_users or user_id in config.zipping_users or user_id in config.uploading_users:
        if user_id in config.downloading_users:
            text += "\n\n🔄 **Status:** Downloading a file…"
        elif user_id in config.zipping_users:
            text += "\n\n🔄 **Status:** Compressing files…"
        elif user_id in config.uploading_users:
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
    await message.reply_text(text, reply_markup=markup, reply_parameters=ReplyParameters(message_id=message.id))

