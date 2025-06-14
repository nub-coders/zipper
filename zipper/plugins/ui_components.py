from config import *

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Button layouts
help_button = InlineKeyboardButton("❓ Help", callback_data="help")

common_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [InlineKeyboardButton("🏠 Home", callback_data="home"),
     InlineKeyboardButton("🗜️📑 Compress files", callback_data="fzip")],
    [help_button]
])

home_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [help_button]
])

back_buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home"), help_button]])

pass_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔒 Set a Password", callback_data="set_password")],
    [InlineKeyboardButton("🔓Continue without Password", callback_data="no_password")]
])

file_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [InlineKeyboardButton("📑 Compress files", callback_data="fzip"), help_button]
])

nofile_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [help_button]
])

def get_verification_buttons():
    """Get verification buttons"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Click to verify", url="")],  # URL will be set dynamically
        [InlineKeyboardButton("how to verify", url="https://t.me/nub_coder_s_updates/3")]
    ])
