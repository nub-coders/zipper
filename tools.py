import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import requests
from telethon import TelegramClient

async def is_user_on_chat(bot: TelegramClient, chat_id: int, user_id: int) -> bool:
    """
    Check if a user is present in a specific chat.

    Parameters:
        bot (TelegramClient): The Telegram client instance.
        chat_id (int): The ID of the chat.
        user_id (int): The ID of the user.

    Returns:
        bool: True if the user is present in the chat, False otherwise.
    """
    try:
        botting = bot_permissions = await bot.get_permissions(chat_id, bot._self_id)
        check = await bot.get_permissions(chat_id, user_id)
        return check
    except:
        return False
