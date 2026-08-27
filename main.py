import asyncio
import os
import config
from config import API_HASH, API_ID, BOT_TOKEN, FORCE_SUBSCRIBE
from convopyro import Conversation
from pyrogram import Client, StopPropagation, idle
from pyrogram.enums import ButtonStyle
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tools import is_admin, is_user_on_chat
from utils.emoji import Emoji, EmojiTag
from utils.premium_emoji import patch_pyrogram_for_custom_emojis
from utils.rich_ui import rich_reply, rich_send

# Apply Bot API 10.3 custom emoji and button styling patches
patch_pyrogram_for_custom_emojis()

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


async def check_membership_middleware(client, update):
    if not config.FORCE_SUBSCRIBE:
        return

    user = update.from_user
    if not user:
        return

    chat = getattr(update, "chat", None) or getattr(getattr(update, "message", None), "chat", None)
    if chat and getattr(chat.type, "value", str(chat.type)) != "private":
        return

    user_id = user.id
    if is_admin(user_id):
        return

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)]
        ])
        text = (
            f"{EmojiTag.LOCK} <b>Channel Membership Required</b>\n\n"
            f"You need to join both @nub_coders and @nub_coder_s channels to use this bot.\n\n"
            f"<i>Click the buttons below to join and then return here.</i>"
        )

        try:
            target = update.message if hasattr(update, "message") else update
            await rich_reply(target, text, reply_markup=button, client=client)
        except Exception:
            pass
        raise StopPropagation()


app.add_handler(MessageHandler(check_membership_middleware), group=-1)
app.add_handler(CallbackQueryHandler(check_membership_middleware), group=-1)


async def main():
    print("Bot starting with Smart Plugins and Bot API 10.3 UI…")
    await app.start()
    # Downloads are driven per user by batch_manager, which spawns its own worker
    # task on demand; there is no central queue poller to start here.
    print("Zipper Bot started successfully with Bot API 10.2 & 10.3 Rich UI!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
