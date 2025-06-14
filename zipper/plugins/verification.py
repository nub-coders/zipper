from config import *

import requests
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .user_management import generate_random_code, store_code

async def send_verification_link(message, collection):
    """Send verification link to user"""
    code = generate_random_code()
    store_code(collection, message.from_user.id, code)
    long = f'http://t.me/FILEs_COMPRESSOR_BOT?start=verifycodeis{code}'
    url = f'https://api.cuty.io/quick?token=b09763cdea0deb0cc373ca5eb&url={long}'

    try:
        response = requests.get(url, verify=False)
        data = response.json()
        verify_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Click to verify", url=data["shortenedUrl"])],
            [InlineKeyboardButton("how to verify", url="https://t.me/nub_coder_s_updates/3")]
        ])

        await message.reply_text(
            "you need to verify first in order to use the bot to avoid spam\n\n"
            "This is only file to zip bot which gives 4.5 GB storage support to the user \n\n"
            "You can also use /premium to get many benifits including no ads",
            reply_markup=verify_button
        )
    except Exception as e:
        print(f"Error in send_verification_link: {e}")
