import config
import os
import asyncio
from pyrogram import Client
from convopyro import Conversation
from plugins.file_handlers import process_queues

from config import API_ID, API_HASH, BOT_TOKEN, FORCE_SUBSCRIBE

config.ggg = os.getcwd()

# Bot configuration with Smart Plugins enabled
plugins = dict(root="plugins")
app = Client(
    'file_compressor_bot',
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    in_memory=True,
    plugins=plugins,
)
Conversation(app)

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram import StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tools import is_user_on_chat, is_admin

async def check_membership_middleware(client, update):
    if not config.FORCE_SUBSCRIBE:
        return

    user = update.from_user
    if not user:
        return

    # Only enforce membership check in private chats — never reply in groups
    chat = getattr(update, "chat", None) or getattr(getattr(update, "message", None), "chat", None)
    if chat and chat.type.value != "private":
        return

    user_id = user.id
    if is_admin(user_id):
        return

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders")],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s")]
        ])
        text = "You need to join both @nub_coders and @nub_coder_s channels to use this bot.\n\nClick below to Join!"
        
        try:
            if hasattr(update, "reply_text"):
                await update.reply_text(text, reply_markup=button)
            elif hasattr(update, "message"):
                await update.message.reply_text(text, reply_markup=button)
        except Exception:
            pass
        raise StopPropagation()

app.add_handler(MessageHandler(check_membership_middleware), group=-1)
app.add_handler(CallbackQueryHandler(check_membership_middleware), group=-1)

async def start_background_tasks():
    """Start background tasks after bot initialization."""
    print("Bot components initialized…")

    # ── Start queue processing (fallback for direct processing) ────────
    print("Starting queue processing…")
    asyncio.create_task(process_queues())
    print("Queue processing started…")
    print("Bot started successfully!")


from pyrogram import idle
import asyncio

async def main():
    print("Bot starting with Smart Plugins…")
    await app.start()
    await start_background_tasks()
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
