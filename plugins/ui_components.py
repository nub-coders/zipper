from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle

# Shared button
help_button = InlineKeyboardButton("❓ Help", callback_data="help", style=ButtonStyle.PRIMARY)

# Button layouts with colors
common_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files", style=ButtonStyle.SUCCESS),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear", style=ButtonStyle.DANGER)],
    [InlineKeyboardButton("🏠 Home", callback_data="home", style=ButtonStyle.PRIMARY),
     InlineKeyboardButton("🗜️📑 Compress files", callback_data="fzip", style=ButtonStyle.SUCCESS)],
    [help_button, InlineKeyboardButton("🌐 Language / زبان", callback_data="lang_menu", style=ButtonStyle.PRIMARY)],
])

home_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🗂️ List My Files", callback_data="my_files", style=ButtonStyle.SUCCESS),
     InlineKeyboardButton("❌ Clear My Files", callback_data="clear", style=ButtonStyle.DANGER)],
    [help_button, InlineKeyboardButton("🌐 Language / زبان", callback_data="lang_menu", style=ButtonStyle.PRIMARY)],
])

back_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 Home", callback_data="home", style=ButtonStyle.PRIMARY), help_button],
])

pass_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔒 Create Protected ZIP", callback_data="set_password", style=ButtonStyle.SUCCESS)],
    [InlineKeyboardButton("📦 Create Regular ZIP", callback_data="no_password", style=ButtonStyle.PRIMARY)],
    [InlineKeyboardButton("🏠 Back to Menu", callback_data="home", style=ButtonStyle.DANGER)],
])

file_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear", style=ButtonStyle.DANGER),
     InlineKeyboardButton("🏠 Home", callback_data="home", style=ButtonStyle.PRIMARY)],
    [InlineKeyboardButton("📑 Compress files", callback_data="fzip", style=ButtonStyle.SUCCESS), help_button],
])

nofile_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Clear My Files", callback_data="clear", style=ButtonStyle.DANGER),
     InlineKeyboardButton("🏠 Home", callback_data="home", style=ButtonStyle.PRIMARY)],
    [help_button],
])
