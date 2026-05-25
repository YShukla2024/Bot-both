# ================== MAIN.PY ==================

import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import os
import re
import json
import threading
import unicodedata

from datetime import datetime, timedelta, timezone
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

from normalizer import (
    normalize_text,
    parse_signal,
    format_signal,
    is_signal,
)

# ================== FLASK KEEP ALIVE ==================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running"


def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, daemon=True).start()

# ================== LOAD ENV ==================

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_string = os.getenv("SESSION_STRING")

# ================== TELEGRAM CLIENT ==================

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

# ================== CONFIG ==================

SOURCES_FILE = "sources.json"

SOURCE_CHATS = [
    -1003550975849,
    -5246702260
]

TARGET_GROUP = -1003923654905

PRINT_ALL_MESSAGES = False
SEND_TEST_ON_START = True

HEARTBEAT_INTERVAL = 30 * 60

# ================== SAVE / LOAD SOURCES ==================

def save_sources(chats):
    with open(SOURCES_FILE, "w") as f:
        json.dump({"chats": chats}, f, indent=2)


def load_sources():
    if not os.path.exists(SOURCES_FILE):
        save_sources(SOURCE_CHATS)
        return SOURCE_CHATS

    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
            return data.get("chats", SOURCE_CHATS)
    except:
        return SOURCE_CHATS


SOURCE_CHATS = load_sources()

# ================== HEARTBEAT ==================

async def send_heartbeat(target_entity):

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            msg = (
                f"💓 BOT ALIVE\n"
                f"📡 Monitoring {len(SOURCE_CHATS)} groups\n"
                f"🕐 {now}"
            )

            await client.send_message(target_entity, msg)

            print(f"💓 Heartbeat sent")

        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

# ================== SIGNAL FILTER ==================

def is_signal(text):

    if not text:
        return False

    t = normalize_text(text).upper().strip()

    # ================= BLOCKED =================

    blocked_patterns = [
        r'BALANCE\s*:',
        r'EQUITY\s*:',
        r'FLOATING\s*:',
        r'STATUS\s*UPDATE',
        r'TARGET\s*HIT',
        r'TP\s*HIT',
        r'SL\s*HIT',
        r'PROFIT\s*BOOKED',
        r'BREAK\s*EVEN',
        r'BREAKEVEN',
        r'LOCK\s*PROFIT',
        r'HALF\s*PROFIT',
        r'BOT\s*ONLINE',
        r'PROXIMITY\s*ALERT',
        r'SKIPPING\s*ORDER',
    ]

    for pattern in blocked_patterns:
        if re.search(pattern, t):
            return False

    # ================= SIMPLE SIGNAL WORDS =================

    signal_words = [
        "BUY",
        "SELL",
        "BUY NOW",
        "SELL NOW",
        "GOLD",
        "SILVER",
        "XAUUSD",
        "XAGUSD",
    ]

    for word in signal_words:
        if word in t:
            return True

    return False

# ================== HELPERS ==================

async def get_chat_name(chat_id):

    try:
        entity = await client.get_entity(chat_id)

        return (
            entity.title
            or entity.first_name
            or str(chat_id)
        )

    except Exception:
        return str(chat_id)

# ================== DEBUG LOGGER ==================

@client.on(events.NewMessage)
async def debug_logger(event):

    if not PRINT_ALL_MESSAGES:
        return

    try:
        chat = await event.get_chat()

        print("\n📩 NEW MESSAGE")
        print("CHAT:", getattr(chat, "title", "Unknown"))
        print("ID:", event.chat_id)
        print("TEXT:", event.message.message)
        print("-" * 50)

    except Exception as e:
        print("❌ Debug error:", e)

# ================== COMMANDS ==================

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/status$'
))
async def cmd_status(event):

    await event.reply(
        f"🟢 Bot Running\n"
        f"📡 Sources: {len(SOURCE_CHATS)}\n"
        f"🎯 Target: {TARGET_GROUP}"
    )


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/test$'
))
async def cmd_test(event):

    msg = (
        "XAUUSD BUY 3360\n"
        "TP 3370\n"
        "SL 3350"
    )

    await client.send_message(
        TARGET_GROUP,
        msg
    )

    await event.reply(
        "✅ Test Sent"
    )


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/addchat\s+(-?\d+)$'
))
async def cmd_addchat(event):

    global SOURCE_CHATS

    chat_id = int(
        event.pattern_match.group(1)
    )

    if chat_id in SOURCE_CHATS:
        await event.reply(
            f"⚠️ Already exists\n{chat_id}"
        )
        return

    SOURCE_CHATS.append(chat_id)

    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Added\n{chat_id}"
    )

    print(f"✅ Added source: {chat_id}")


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/removechat\s+(-?\d+)$'
))
async def cmd_removechat(event):

    global SOURCE_CHATS

    chat_id = int(
        event.pattern_match.group(1)
    )

    if chat_id not in SOURCE_CHATS:
        await event.reply(
            f"❌ Not found\n{chat_id}"
        )
        return

    SOURCE_CHATS.remove(chat_id)

    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Removed\n{chat_id}"
    )

    print(f"➖ Removed source: {chat_id}")


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/listchats$'
))
async def cmd_list(event):

    if not SOURCE_CHATS:
        await event.reply(
            "❌ No source chats"
        )
        return

    lines = [
        f"📡 SOURCE CHATS ({len(SOURCE_CHATS)})\n"
    ]

    for i, cid in enumerate(SOURCE_CHATS, 1):
        lines.append(f"{i}. {cid}")

    await event.reply(
        "\n".join(lines)
    )

# ================== MAIN HANDLER ==================

@client.on(events.NewMessage)
async def handler(event):

    try:
        chat_id = event.chat_id

        raw_text = event.message.message or ""

        if not raw_text.strip():
            return

        if raw_text.startswith("/"):
            return

        if chat_id not in SOURCE_CHATS:
            return

        text = normalize_text(raw_text)

        # DEBUG: Show normalized text and signal check result
        print(f"[DEBUG] Normalized: '{text}' | is_signal: {is_signal(text)}")

        if not is_signal(text):
            return

        data = parse_signal(text)

        chat_name = await get_chat_name(chat_id)

        # RAW FALLBACK

        if not data["type"] or not data["entry"]:

            await client.send_message(
                TARGET_GROUP,
                text
            )

            print(
                f"✅ Raw forwarded from {chat_id}"
            )

            return

        # CLEAN FORMAT

        output = format_signal(
            data,
            source=chat_name
        )

        await client.send_message(
            TARGET_GROUP,
            output
        )

        print(
            f"✅ Clean forwarded from {chat_id}"
        )

    except Exception as e:
        print("❌ Error:", e)

# ================== MAIN ==================

print("🚀 MAIN STARTED")
async def main():

    await client.start()
    print("✅ TELETHON CONNECTED")
    print("🔄 Loading sources...")

    for chat_id in SOURCE_CHATS:

        try:
            await client.get_entity(chat_id)
            print(f"✅ Loaded: {chat_id}")

        except Exception as e:
            print(f"❌ Failed: {chat_id} -> {e}")

    target_entity = await client.get_entity(
        TARGET_GROUP
    )

    print(
        f"🎯 Target group: {target_entity.title}"
    )

    # ================== START MESSAGE ==================

    if SEND_TEST_ON_START:

        try:
            msg = (
                "🟢 BOT STARTED\n"
                f"📡 Monitoring {len(SOURCE_CHATS)} groups"
            )

            await client.send_message(
                target_entity,
                msg
            )

            print("✅ Start message sent")

        except Exception as e:
            print(f"❌ Start message failed: {e}")

    # ================== RECOVER MISSED ==================

    print("🔄 Recovering missed messages...")

    cutoff = datetime.now(
        timezone.utc
    ) - timedelta(minutes=30)

    recovered = 0

    for chat_id in SOURCE_CHATS:

        try:
            async for msg in client.iter_messages(
                chat_id,
                limit=20
            ):

                if msg.date < cutoff:
                    break

                if not msg.text:
                    continue

                text = normalize_text(msg.text)

                if not is_signal(text):
                    continue

                data = parse_signal(text)

                chat_name = await get_chat_name(chat_id)

                output = format_signal(
                    data,
                    source=chat_name
                )

                await client.send_message(
                    TARGET_GROUP,
                    f"📬 MISSED SIGNAL\n\n{output}"
                )

                recovered += 1

                print(
                    f"📬 Recovered from {chat_id}"
                )

                await asyncio.sleep(1)

        except Exception as e:
            print(
                f"❌ Recover failed {chat_id}: {e}"
            )

    print(f"✅ Recovered: {recovered}")

    # ================== HEARTBEAT ==================

    asyncio.ensure_future(
        send_heartbeat(target_entity)
    )

    print("💓 Heartbeat started")
    print("🚀 Listening...")

    try:
        await client.run_until_disconnected()

    except asyncio.CancelledError:
        pass

    finally:

        try:

            if not client.is_connected():
                await client.connect()

            msg = (
                "🔴 BOT STOPPED\n"
                "⚠️ Forwarding paused"
            )

            await client.send_message(
                target_entity,
                msg
            )

        except Exception as e:
            print(f"❌ Stop message error: {e}")

        finally:
            await client.disconnect()

# ================== RUN ==================

if __name__ == "__main__":

    try:
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        print("⚠️ Stopped")