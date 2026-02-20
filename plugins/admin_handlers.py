from config import *
from pyrogram import Client, filters
from pyrogram.types import Message
from tools import is_admin, get_admin_ids
import os


@Client.on_message(filters.private & filters.command("skip") & filters.regex("^!skip$"))
async def skip_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await message.reply_text(
            "Admin command received. Skipping the task…",
            quote=True, reply_to_message_id=message.id,
        )
        if timeout:
            await timeout()


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_message(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    stored_user_ids = [u["user_id"] for u in collection.find({}, {"user_id": 1})]
    sent = 0

    if message.reply_to_message:
        for uid in stored_user_ids:
            try:
                await message.reply_to_message.forward(uid)
                sent += 1
            except Exception as e:
                print(f"Failed to forward message: {e}")
        await message.reply_text(
            f"Broadcasted to {sent} users",
            quote=True, reply_to_message_id=message.id,
        )


@Client.on_message(filters.private & filters.command("reboot"))
async def reboot_handler(client: Client, message: Message):
    if is_admin(message.from_user.id):
        await message.reply_text(
            "Admin command received. Stopping the bot…",
            quote=True, reply_to_message_id=message.id,
        )
        os.system(f"kill -9 {os.getpid()}")


@Client.on_message(filters.private & filters.command("users"))
async def list_users(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    user_ids_list = [str(u["user_id"]) for u in collection.find({}, {"user_id": 1})]
    if not user_ids_list:
        return await message.reply_text("No users found.", quote=True, reply_to_message_id=message.id)

    user_list = "\n".join(user_ids_list) + f"\nTotal users: {len(user_ids_list)}"
    for i in range(0, len(user_list), 4000):
        await message.reply_text(
            user_list[i:i + 4000],
            quote=True, reply_to_message_id=message.id,
        )


@Client.on_message(filters.private & filters.command("set"))
async def set_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        value = message.text.split("/set ", 1)[1].strip()
        collection.update_one({}, {"$set": {"ad": value}}, upsert=True)
        await message.reply_text("Value saved successfully!", quote=True, reply_to_message_id=message.id)
    except IndexError:
        await message.reply_text("Please provide a value after /set", quote=True, reply_to_message_id=message.id)


@Client.on_message(filters.private & filters.command("ad"))
async def ad_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        is_ad_value = message.text.split()[1]
        collection.update_one({}, {"$set": {"is_ad": is_ad_value}}, upsert=True)
        await message.reply_text(
            f'Updated "is_ad" field with: {is_ad_value}',
            quote=True, reply_to_message_id=message.id,
        )
    except IndexError:
        await message.reply_text(
            "Please provide a value (true/false)",
            quote=True, reply_to_message_id=message.id,
        )


@Client.on_message(filters.private & filters.command("get"))
async def get_handler(client: Client, message: Message):
    result = collection.find_one({})
    if result and "ad" in result:
        await message.reply_text(f'The value is: {result["ad"]}', quote=True, reply_to_message_id=message.id)
    else:
        await message.reply_text("No value found", quote=True, reply_to_message_id=message.id)
