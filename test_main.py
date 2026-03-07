from pyrogram import Client, StopPropagation
from pyrogram.handlers import MessageHandler
import asyncio

async def middleware(client, message):
    print("Middleware triggered")
    raise StopPropagation()

async def dummy_main():
    app = Client("test", in_memory=True, api_id=1, api_hash="a")
    app.add_handler(MessageHandler(middleware), group=-1)

asyncio.run(dummy_main())
print("Success")
