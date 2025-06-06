from config import *

import os
import datetime
import time
import shutil
import pymongo
import certifi
from config import *

# MongoDB setup
client = pymongo.MongoClient("mongodb+srv://ankitkr23835:air8858@cluster0.cxh2ryf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", tlsCAFile=certifi.where())
db = client["telegram_bot"]
collection = db["users"]

def setup_directories():
    """Setup required directories and clean old files"""
    ggg = os.getcwd()
    current_dir = f"{ggg}/zipper"
    current_time = datetime.datetime.now()
    print(f"Current Date and Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Create zipper directory if it doesn't exist
    os.makedirs(current_dir, exist_ok=True)
    
    # Clean old files (older than 3 days)
    for dirpath, dirnames, filenames in os.walk(current_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            file_creation_time = os.path.getctime(file_path)
            if (current_time - datetime.datetime.fromtimestamp(file_creation_time)).days >= 3:
                os.remove(file_path)
                print(f"Deleted file: {file_path}")

def get_database_collection():
    """Get the MongoDB collection"""
    return collection

def initialize_bot():
    """Initialize bot components"""
    setup_directories()
    print("Bot components initialized...")
    return get_database_collection()

def get_database_collection():
    """Get the MongoDB collection"""
    return collection
