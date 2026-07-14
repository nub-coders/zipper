from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Shared button
help_button = InlineKeyboardButton("❓ Help", callback_data="help")

# Button layouts
common_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [InlineKeyboardButton("🏠 Home", callback_data="home"),
     InlineKeyboardButton("🗜️📑 Compress files", callback_data="fzip")],
    [help_button, InlineKeyboardButton("🌐 Language / زبان", callback_data="lang_menu")],
])

home_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files"),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear")],
    [help_button, InlineKeyboardButton("🌐 Language / زبان", callback_data="lang_menu")],
])

back_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 Home", callback_data="home"), help_button],
])

pass_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔒 Create Protected ZIP", callback_data="set_password")],
    [InlineKeyboardButton("📦 Create Regular ZIP", callback_data="no_password")],
    [InlineKeyboardButton("🏠 Back to Menu", callback_data="home")],
])

file_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [InlineKeyboardButton("📑 Compress files", callback_data="fzip"), help_button],
])

nofile_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear"),
     InlineKeyboardButton("🏠 Home", callback_data="home")],
    [help_button],
])
