import os
import datetime
import certifi
import pymongo
from config import collection


def setup_directories():
    """Create the zipper directory and clean files older than 3 days."""
    current_dir = os.path.join(os.getcwd(), "zipper")
    now = datetime.datetime.now()
    print(f"Current Date and Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    os.makedirs(current_dir, exist_ok=True)

    for dirpath, _, filenames in os.walk(current_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            creation_time = os.path.getctime(file_path)
            if (now - datetime.datetime.fromtimestamp(creation_time)).days >= 3:
                os.remove(file_path)
                print(f"Deleted old file: {file_path}")


def get_database_collection():
    """Get the MongoDB collection (shared from config)."""
    return collection


def initialize_bot():
    """Initialize bot components."""
    setup_directories()
    print("Bot components initialized…")
    return get_database_collection()
