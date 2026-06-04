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
    -1001897903474,
    -5246702260,
    -1001336715612
]

TARGET_GROUP = -1003923654905

PRINT_ALL_MESSAGES = False
SEND_TEST_ON_START = True

HEARTBEAT_INTERVAL = 30 * 60

# ================== BOT MODE (ACTIVE/STANDBY) ==================

BOT_MODE = os.getenv("BOT_MODE", "ACTIVE").upper()

if BOT_MODE not in ["ACTIVE", "STANDBY"]:
    BOT_MODE = "ACTIVE"

print(f"🤖 BOT MODE: {BOT_MODE}")

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
            mode_emoji = "🟢" if BOT_MODE == "ACTIVE" else "🟡"

            msg = (
                f"💓 BOT ALIVE ({mode_emoji} {BOT_MODE})\n"
                f"📡 Monitoring {len(SOURCE_CHATS)} groups\n"
                f"🕐 {now}"
            )

            await client.send_message(target_entity, msg)

            print(f"💓 Heartbeat sent ({BOT_MODE})")

        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

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

# ================== STATISTICS ==================

STATS_FILE = "bot_stats.json"

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {
            "signals": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "balance": 0.0
        }
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "signals": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "balance": 0.0
        }

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

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


# ================== GROUP COMMANDS ==================
# Allow adding/removing sources from within the target group

@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    outgoing=True,
    pattern=r'^/addsource\s+(-?\d+)$'
))
async def cmd_group_addsource(event):

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
        f"✅ Added source: {chat_id}\n"
        f"📡 Now monitoring: {len(SOURCE_CHATS)} groups"
    )

    print(f"✅ Added source from group: {chat_id}")


@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    outgoing=True,
    pattern=r'^/removesource\s+(-?\d+)$'
))
async def cmd_group_removesource(event):

    global SOURCE_CHATS

    chat_id = int(
        event.pattern_match.group(1)
    )

    if chat_id not in SOURCE_CHATS:
        await event.reply(
            f"❌ Not found: {chat_id}"
        )
        return

    SOURCE_CHATS.remove(chat_id)
    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Removed source: {chat_id}\n"
        f"📡 Now monitoring: {len(SOURCE_CHATS)} groups"
    )

    print(f"➖ Removed source from group: {chat_id}")


@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    outgoing=True,
    pattern=r'^/sources$'
))
async def cmd_group_sources(event):

    if not SOURCE_CHATS:
        await event.reply(
            "❌ No source chats configured"
        )
        return

    lines = [
        f"📡 MONITORING {len(SOURCE_CHATS)} SOURCES\n"
    ]

    for i, cid in enumerate(SOURCE_CHATS, 1):
        chat_name = await get_chat_name(cid)
        lines.append(f"{i}. {chat_name} ({cid})")

    await event.reply(
        "\n".join(lines)
    )

# ================== STATISTICS COMMANDS ==================

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/stats$'
))
async def cmd_stats(event):
    stats = load_stats()
    
    win_count = stats.get("tp_hits", 0)
    loss_count = stats.get("sl_hits", 0)
    total = win_count + loss_count
    win_rate = (win_count / total * 100) if total > 0 else 0
    
    msg = (
        f"📊 FULL DASHBOARD\n"
        f"{'='*40}\n"
        f"📈 Total Signals: {stats.get('signals', 0)}\n"
        f"💰 Balance: ${stats.get('balance', 0):,.2f}\n"
        f"{'='*40}\n"
        f"✅ TP Hits: {win_count}\n"
        f"   Pips Gained: {stats.get('tp_pips', 0):,.2f}\n"
        f"❌ SL Hits: {loss_count}\n"
        f"   Pips Lost: {stats.get('sl_pips', 0):,.2f}\n"
        f"{'='*40}\n"
        f"📊 Win Rate: {win_rate:.2f}%\n"
        f"📊 Loss Rate: {100-win_rate:.2f}%\n"
    )
    
    await event.reply(msg)


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/signals$'
))
async def cmd_signals(event):
    stats = load_stats()
    
    msg = (
        f"📡 SIGNALS RECEIVED\n"
        f"{'='*40}\n"
        f"Total: {stats.get('signals', 0)}\n"
    )
    
    await event.reply(msg)


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/balance$'
))
async def cmd_balance(event):
    stats = load_stats()
    balance = stats.get('balance', 0)
    
    msg = (
        f"💰 ACCOUNT BALANCE\n"
        f"{'='*40}\n"
        f"Balance: ${balance:,.2f}\n"
    )
    
    await event.reply(msg)


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/tp$'
))
async def cmd_tp(event):
    stats = load_stats()
    
    tp_hits = stats.get("tp_hits", 0)
    tp_pips = stats.get("tp_pips", 0)
    
    msg = (
        f"✅ TARGET PRICE HITS\n"
        f"{'='*40}\n"
        f"TP Hits: {tp_hits}\n"
        f"Pips Gained: {tp_pips:,.2f}\n"
    )
    
    await event.reply(msg)


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/sl$'
))
async def cmd_sl(event):
    stats = load_stats()
    
    sl_hits = stats.get("sl_hits", 0)
    sl_pips = stats.get("sl_pips", 0)
    
    msg = (
        f"❌ STOP LOSS HITS\n"
        f"{'='*40}\n"
        f"SL Hits: {sl_hits}\n"
        f"Pips Lost: {sl_pips:,.2f}\n"
    )
    
    await event.reply(msg)


@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/ratio$'
))
async def cmd_ratio(event):
    stats = load_stats()
    
    win_count = stats.get("tp_hits", 0)
    loss_count = stats.get("sl_hits", 0)
    total = win_count + loss_count
    
    if total == 0:
        win_rate = 0
        loss_rate = 0
    else:
        win_rate = (win_count / total * 100)
        loss_rate = (loss_count / total * 100)
    
    msg = (
        f"📊 WIN / LOSS RATIO\n"
        f"{'='*40}\n"
        f"Wins: {win_count} ({win_rate:.2f}%)\n"
        f"Losses: {loss_count} ({loss_rate:.2f}%)\n"
        f"Total Trades: {total}\n"
    )
    
    await event.reply(msg)

# ================== MAIN HANDLER ==================

@client.on(events.NewMessage)
async def handler(event):

    try:
        # Skip if in STANDBY mode
        if BOT_MODE == "STANDBY":
            return

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

        if not data["type"] or not data["entry"] or not data["tp"]:

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
            mode_emoji = "🟢" if BOT_MODE == "ACTIVE" else "🟡"
            mode_text = "ACTIVE - FORWARDING ENABLED" if BOT_MODE == "ACTIVE" else "STANDBY - BACKUP MODE"
            
            msg = (
                f"{mode_emoji} BOT {mode_text}\n"
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