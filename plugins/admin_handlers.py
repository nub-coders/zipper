
from pyrogram import Client, filters
from pyrogram.types import Message
from plugins.admin_commands import is_admin, broadcast_message, authorize_premium_user, reset_user
from plugins.installer import get_database_collection
import os
import time

collection = get_database_collection()
ggg = os.getcwd()

@Client.on_message(filters.command("skip") & filters.regex("^!skip$"))
async def skip_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.reply_text("Admin command received. Skipping the task...")
        # Import timeout function from main
        import main
        await main.timeout()

@Client.on_message(filters.command("loud"))
async def loud_message(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    await broadcast_message(client, collection, message)

@Client.on_message(filters.command("reboot"))
async def reboot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.reply_text("Admin command received. Stopping the bot...")
        os.system(f"kill -9 {os.getpid()}")

@Client.on_message(filters.command("rst"))
async def reset_user_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user.id:
        target_user_id = message.reply_to_message.from_user.id

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            target_user_id = int(arg)
        else:
            try:
                user_entity = await client.get_users(arg)
                target_user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    if target_user_id:
        user_data = reset_user(collection, target_user_id)
        await message.reply_text(f"User resetted successfully.\nUserdata:{user_data}")

@Client.on_message(filters.command("authorize"))
async def authorize_user(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user.id:
        target_user_id = message.reply_to_message.from_user.id

    command_args = message.text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            target_user_id = int(arg)
        else:
            try:
                user_entity = await client.get_users(arg)
                target_user_id = user_entity.id
            except ValueError:
                return await message.reply_text("Cannot find user with the provided username.")

    if target_user_id:
        user_data = authorize_premium_user(collection, target_user_id)
        await message.reply_text(f"User authorized successfully.\nUserdata:{user_data}")

@Client.on_message(filters.command("users"))
async def list_users(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    user_ids = [str(user["user_id"]) for user in collection.find()]
    if user_ids:
        user_list = "\n".join(user_ids)
        user_list += f"\nTotal users: {len(user_ids)}"
        chunk_size = 4000
        chunks = [user_list[i:i+chunk_size] for i in range(0, len(user_list), chunk_size)]
        for chunk in chunks:
            await message.reply_text(chunk)
    else:
        await message.reply_text("No users found.")

@Client.on_message(filters.command("set"))
async def set_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    try:
        input_text = message.text.split('/set ')[1]
        value = input_text.strip()
        collection.update_one({}, {"$set": {'ad': value}}, upsert=True)
        await message.reply_text('Value saved successfully!')
    except IndexError:
        await message.reply_text('Please provide a value after /set')

@Client.on_message(filters.command("ad"))
async def ad_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    try:
        is_ad_value = message.text.split()[1]
        collection.update_one({}, {"$set": {'is_ad': is_ad_value}}, upsert=True)
        await message.reply_text(f'Updated "is_ad" field with: {is_ad_value}')
    except IndexError:
        await message.reply_text('Please provide a value (true/false)')

@Client.on_message(filters.command("get"))
async def get_handler(client: Client, message: Message):
    result = collection.find_one({})
    if result and 'ad' in result:
        await message.reply_text(f'The value is: {result["ad"]}')
    else:
        await message.reply_text('No value found')
