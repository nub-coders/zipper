"""plugins/ui_components.py — Modern, Styled Inline Keyboards with Bot API 10.3 Button Styles and Custom Emoji Icons."""

from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils.emoji import Emoji

# ── Shared Standard Buttons ───────────────────────────────────────────────────
help_button = InlineKeyboardButton(
    "❓ Help & Guide",
    callback_data="help",
    style=ButtonStyle.PRIMARY,
    icon_custom_emoji_id=Emoji.HELP,
)

home_button = InlineKeyboardButton(
    "🏠 Main Menu",
    callback_data="home",
    style=ButtonStyle.DEFAULT,
    icon_custom_emoji_id=Emoji.HOME,
)

back_to_menu_button = InlineKeyboardButton(
    "◀️ Back to Menu",
    callback_data="home",
    style=ButtonStyle.DEFAULT,
    icon_custom_emoji_id=Emoji.BACK,
)


# ── Menu Keyboards ────────────────────────────────────────────────────────────

home_buttons = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🗂️ My Files", callback_data="my_files", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.FILE),
        InlineKeyboardButton("🗜️ Compress", callback_data="fzip", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.COMPRESS),
    ],
    [
        InlineKeyboardButton("📊 My Status", callback_data="status", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.STATS),
        InlineKeyboardButton("🌐 Language", callback_data="lang_menu", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.LANG),
    ],
    [
        help_button,
    ],
])

common_buttons = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🗂️ My Files", callback_data="my_files", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.FILE),
        InlineKeyboardButton("❌ Clear Files", callback_data="clear", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.TRASH),
    ],
    [
        home_button,
        InlineKeyboardButton("🗜️ Compress", callback_data="fzip", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.COMPRESS),
    ],
    [
        help_button,
        InlineKeyboardButton("🌐 Language", callback_data="lang_menu", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.LANG),
    ],
])

back_buttons = InlineKeyboardMarkup([
    [
        home_button,
        help_button,
    ],
])

pass_button = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔒 Create Protected ZIP", callback_data="set_password", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.LOCK),
    ],
    [
        InlineKeyboardButton("📦 Create Regular ZIP", callback_data="no_password", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ZIP),
    ],
    [
        back_to_menu_button,
    ],
])

file_buttons = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🗜️ Compress Files", callback_data="fzip", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.COMPRESS),
        InlineKeyboardButton("❌ Clear All", callback_data="clear", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.TRASH),
    ],
    [
        InlineKeyboardButton("🔄 Refresh List", callback_data="my_files", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.REFRESH),
        home_button,
    ],
])

nofile_buttons = InlineKeyboardMarkup([
    [
        home_button,
        help_button,
    ],
])

cancel_markup = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🛑 Cancel Task", callback_data="cancel_task", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL),
    ],
])

cancel_all_markup = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🛑 Cancel All Tasks", callback_data="cancel_all", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CANCEL),
        home_button,
    ],
])

lang_markup = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LANG),
        InlineKeyboardButton("🇮🇷 فارسی", callback_data="setlang_fa", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.LANG),
    ],
    [
        home_button,
    ],
])
