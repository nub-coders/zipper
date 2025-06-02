
import os
import time

def is_admin(user_id):
    """Check if user is admin"""
    ggg = os.getcwd()
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            return user_id in admin_ids
    return False

def get_admin_ids():
    """Get list of admin IDs"""
    ggg = os.getcwd()
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            return [int(line.strip()) for line in file.readlines()]
    return []

async def broadcast_message(app, collection, message):
    """Broadcast message to all users"""
    stored_user_ids = [user["user_id"] for user in collection.find()]
    success_count = 0

    if message.reply_to_message:
        for user_id in stored_user_ids:
            try:
                await message.reply_to_message.forward(user_id)
                success_count += 1
            except Exception as e:
                print(f"Failed to forward message: {e}")
        
        await message.reply_text(f"Broadcasted to {success_count} users")

def authorize_premium_user(collection, user_id, days=30):
    """Authorize user for premium access"""
    timestamp = int(time.time()) + (days * 24 * 60 * 60)
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)
    return collection.find_one({"user_id": user_id})

def reset_user(collection, user_id):
    """Reset user verification status"""
    timestamp = int(time.time()) - 12600
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)
    return collection.find_one({"user_id": user_id})
