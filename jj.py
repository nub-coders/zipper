from telethon import TelegramClient, events
from telethon.tl.custom import Button
from urllib.parse import quote
from config import *

bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/lstart'))
async def start_handler(event):
    copy_text = "I'm trying to test newly launched telegram text copy buttons"
    # Create URL to trigger copy action
    copy_url = f"tg://copy?text={quote(copy_text)}"
    # Create an inline button with the copy URL
    copy_button = Button.url("📋 Copy Text", copy_url)
    await event.respond(
        "Welcome! Click the button below to copy the text:",
        buttons=[[copy_button]]
    )

bot.run_until_disconnected()
