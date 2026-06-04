import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os

load_dotenv()

api_id = int(os.getenv("API_ID") or 0)
api_hash = os.getenv("API_HASH")
phone = os.getenv("PHONE")

async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    await client.send_code_request(phone)
    code = input("Enter the code you received: ").strip()
    
    await client.sign_in(phone, code)
    
    print("SESSION STRING:")
    print(client.session.save())
    await client.disconnect()

asyncio.run(main())