from config import *

import time
import string
import random

def store_user(collection, user_id):
    """Store user with current timestamp"""
    timestamp = int(time.time())
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_userr(collection, user_id):
    """Store user with timestamp 6 hours ago"""
    timestamp = int(time.time()) - 21600
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def store_code(collection, user_id, verifycode):
    """Store verification code for user"""
    user_data = {"user_id": user_id, "verifycode": verifycode}
    collection.update_one({"user_id": user_id}, {'$set': user_data}, upsert=True)

def storre_user(collection, user_id, timestamp):
    """Store user with custom timestamp"""
    user_data = {"user_id": user_id, "timestamp": timestamp}
    collection.replace_one({"user_id": user_id}, user_data, upsert=True)

def generate_random_code(length=10):
    """Generate random verification code"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_user_status(collection, user_id):
    """Get user verification status and limits"""
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if not user_data:
        return False, 200 * 1024 * 1024, 200 * 1024 * 1024

    stored_time = user_data["timestamp"]
    time_difference = current_time - stored_time

    if time_difference < 0:  # Premium user
        return True, 10 * 1024 * 1024 * 1024, 3.5 * 1024 * 1024 * 1024
    elif time_difference < 21600:  # Verified user
        return True, 4.5 * 1024 * 1024 * 1024, 2.5 * 1024 * 1024 * 1024
    else:  # Non-verified user
        return False, 200 * 1024 * 1024, 200 * 1024 * 1024
