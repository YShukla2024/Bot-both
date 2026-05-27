from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os   

import asyncio
load_dotenv()


api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

async def main():
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print(client.session.save())

if __name__ == "__main__":
    asyncio.run(main())