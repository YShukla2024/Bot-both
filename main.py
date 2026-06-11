#!/usr/bin/env python3
# ================== SIGNAL FORWARDER BOT ==================
# Telegram Signal Forwarding Bot with Dynamic Source Management
# Features: Auto-parse signals, dynamic sources, statistics, heartbeat, IMAGE FORWARDING
# Version: 2.5 (Image Forwarding Support + Enhanced Debug)

import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import os
import re
import json
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from dotenv import load_dotenv

from normalizer import (
    normalize_text,
    parse_signal,
    format_signal,
    is_valid_signal,
)

# ================== FLASK KEEP ALIVE ==================

app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot Running"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ================== LOAD ENV ==================

load_dotenv()

# Validate required environment variables
required_vars = {
    "API_ID": "Your Telegram API ID",
    "API_HASH": "Your Telegram API Hash",
    "PHONE": "Your Telegram phone number",
    "SESSION_STRING": "Your Telegram session string",
    "TARGET_GROUP_ID": "Target group ID (format: -100123456789)",
}

missing_vars = []
for var, description in required_vars.items():
    if not os.getenv(var):
        missing_vars.append(f"  - {var}: {description}")

if missing_vars:
    print("\n❌ ERROR: Missing required environment variables in .env file\n")
    print("Create a .env file with the following variables:\n")
    for line in missing_vars:
        print(line)
    exit(1)

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_string = os.getenv("SESSION_STRING")

target_group_raw = os.getenv("TARGET_GROUP_ID")
if not target_group_raw:
    print("❌ ERROR: TARGET_GROUP_ID not set in .env file")
    exit(1)

TARGET_GROUP = int(target_group_raw) if target_group_raw.startswith("-100") else target_group_raw

# ================== TELEGRAM CLIENT ==================

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

# ================== CONFIG ==================

SOURCES_FILE = "sources.json"

# Default source groups
DEFAULT_SOURCE_CHATS = [
    -1003550975849,
    -1001897903474,
    -5246702260,
    -1001336715612,
    -1001421473967
]

PRINT_ALL_MESSAGES = True  # ← ALWAYS ON for debugging
SEND_TEST_ON_START = True
HEARTBEAT_INTERVAL = 30 * 60
ENHANCED_DEBUG = True  # ← Enhanced debug logging

# ================== IMAGE FORWARDING CONFIG ==================
ENABLE_IMAGE_FORWARDING = True  # ← Toggle image forwarding ON/OFF
MAX_IMAGE_SIZE_MB = 50  # Maximum image size to forward (MB)
SUPPORTED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp'
]

# BOT MODE (ACTIVE/STANDBY)
BOT_MODE = os.getenv("BOT_MODE", "ACTIVE").upper()
if BOT_MODE not in ["ACTIVE", "STANDBY"]:
    BOT_MODE = "ACTIVE"

print(f"🤖 BOT MODE: {BOT_MODE}")
print(f"🖼️  IMAGE FORWARDING: {'✅ ENABLED' if ENABLE_IMAGE_FORWARDING else '❌ DISABLED'}")

# ================== SAVE / LOAD SOURCES ==================

def save_sources(chats):
    """Save sources to sources.json"""
    try:
        with open(SOURCES_FILE, "w") as f:
            json.dump({"chats": chats}, f, indent=2)
        print(f"💾 Saved {len(chats)} sources to sources.json")
    except Exception as e:
        print(f"❌ Error saving sources: {e}")

def load_sources():
    """Load sources from sources.json"""
    if not os.path.exists(SOURCES_FILE):
        save_sources(DEFAULT_SOURCE_CHATS)
        return DEFAULT_SOURCE_CHATS

    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
            sources = data.get("chats", DEFAULT_SOURCE_CHATS)
            print(f"📡 Loaded {len(sources)} sources from sources.json")
            return sources
    except Exception as e:
        print(f"⚠️ Error loading sources: {e}, using defaults")
        return DEFAULT_SOURCE_CHATS

# Load sources at startup
SOURCE_CHATS = load_sources()

# ================== HEARTBEAT ==================

async def send_heartbeat(target_entity):
    """Send periodic heartbeat message"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            mode_emoji = "🟢" if BOT_MODE == "ACTIVE" else "🟡"
            image_status = "🖼️ Images: ✅" if ENABLE_IMAGE_FORWARDING else "🖼️ Images: ❌"

            msg = (
                f"💓 BOT ALIVE ({mode_emoji} {BOT_MODE})\n"
                f"📡 Monitoring {len(SOURCE_CHATS)} groups\n"
                f"{image_status}\n"
                f"🕐 {now}"
            )

            await client.send_message(target_entity, msg)
            print(f"💓 Heartbeat sent ({BOT_MODE})")

        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

# ================== HELPERS ==================

async def get_chat_name(chat_id):
    """Get chat/group name by ID"""
    try:
        entity = await client.get_entity(chat_id)
        return entity.title or entity.first_name or str(chat_id)
    except Exception:
        return str(chat_id)

async def get_file_size(media):
    """Get file size in MB from media object"""
    try:
        if hasattr(media, 'sizes'):
            size_bytes = media.sizes[-1] if media.sizes else 0
        elif hasattr(media, 'size'):
            size_bytes = media.size
        else:
            return None
        
        return size_bytes / (1024 * 1024)  # Convert to MB
    except:
        return None

# ================== DEBUG LOGGER ==================

@client.on(events.NewMessage)
async def debug_logger(event):
    """Optional debug logger for all messages"""
    if not PRINT_ALL_MESSAGES:
        return

    try:
        chat = await event.get_chat()
        media_info = ""
        
        if event.message.media:
            media_type = type(event.message.media).__name__
            media_info = f"\n   MEDIA: {media_type}"
        
        print("\n📩 NEW MESSAGE")
        print(f"   CHAT: {getattr(chat, 'title', 'Unknown')}")
        print(f"   ID: {event.chat_id}")
        print(f"   TEXT: {event.message.message or '(no text)'}{media_info}")
        print("-" * 60)
    except Exception as e:
        print(f"❌ Debug error: {e}")

# ================== STATISTICS ==================

STATS_FILE = "bot_stats.json"

def load_stats():
    """Load statistics from file"""
    if not os.path.exists(STATS_FILE):
        return {
            "signals": 0,
            "images": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "balance": 0.0
        }
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
            # Ensure 'images' key exists for backward compatibility
            if "images" not in stats:
                stats["images"] = 0
            return stats
    except:
        return {
            "signals": 0,
            "images": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "balance": 0.0
        }

def save_stats(stats):
    """Save statistics to file"""
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

# ================== COMMANDS - SOURCE MANAGEMENT (USER ACCOUNT) ==================

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/addchat\s+(-?\d+)$'
))
async def cmd_addchat(event):
    """Add a new source group (Only for bot account)"""
    global SOURCE_CHATS

    chat_id = int(event.pattern_match.group(1))
    SOURCE_CHATS = load_sources()

    if chat_id in SOURCE_CHATS:
        await event.reply(
            f"⚠️ Already exists: {chat_id}\n\n"
            f"📡 Monitoring {len(SOURCE_CHATS)} groups"
        )
        return

    SOURCE_CHATS.append(chat_id)
    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Added source: {chat_id}\n"
        f"📡 Now monitoring {len(SOURCE_CHATS)} groups\n\n"
        f"⚡ Active immediately!"
    )

    print(f"✅ Added source: {chat_id} (monitoring {len(SOURCE_CHATS)} total)")

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/removechat\s+(-?\d+)$'
))
async def cmd_removechat(event):
    """Remove a source group (Only for bot account)"""
    global SOURCE_CHATS

    chat_id = int(event.pattern_match.group(1))
    SOURCE_CHATS = load_sources()

    if chat_id not in SOURCE_CHATS:
        await event.reply(
            f"❌ Not found: {chat_id}\n\n"
            f"📡 Monitoring {len(SOURCE_CHATS)} groups"
        )
        return

    SOURCE_CHATS.remove(chat_id)
    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Removed source: {chat_id}\n"
        f"📡 Now monitoring {len(SOURCE_CHATS)} groups\n\n"
        f"⚡ Change active immediately!"
    )

    print(f"➖ Removed source: {chat_id} (monitoring {len(SOURCE_CHATS)} total)")

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/listchats$'
))
async def cmd_listchats(event):
    """List all configured source groups (Only for bot account)"""
    global SOURCE_CHATS

    SOURCE_CHATS = load_sources()

    if not SOURCE_CHATS:
        await event.reply("❌ No source chats configured")
        return

    lines = [f"📡 SOURCE CHATS ({len(SOURCE_CHATS)})\n"]
    for i, cid in enumerate(SOURCE_CHATS, 1):
        lines.append(f"{i}. {cid}")

    await event.reply("\n".join(lines))

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/status$'
))
async def cmd_status(event):
    """Check bot status (Only for bot account)"""
    global SOURCE_CHATS
    SOURCE_CHATS = load_sources()

    mode_emoji = "🟢" if BOT_MODE == "ACTIVE" else "🟡"
    mode_text = "ACTIVE - FORWARDING" if BOT_MODE == "ACTIVE" else "STANDBY - BACKUP"
    image_status = "🖼️ Images: ✅" if ENABLE_IMAGE_FORWARDING else "🖼️ Images: ❌"

    await event.reply(
        f"{mode_emoji} Bot {mode_text}\n"
        f"📡 Sources: {len(SOURCE_CHATS)}\n"
        f"{image_status}\n"
        f"🎯 Target: {TARGET_GROUP}"
    )

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r'^/test$'
))
async def cmd_test(event):
    """Send test signal (Only for bot account)"""
    msg = (
        "SELL XAUUSD 4445\n"
        "TP 4440\n"
        "SL 4455"
    )

    await client.send_message(TARGET_GROUP, msg)
    await event.reply("✅ Test signal sent")

# ================== COMMANDS - GROUP MANAGEMENT (ANY USER) ==================

@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    pattern=r'^/addsource\s+(-?\d+)$'
))
async def cmd_group_addsource(event):
    """Add source from target group - WORKS FOR ANY USER"""
    global SOURCE_CHATS

    chat_id = int(event.pattern_match.group(1))
    SOURCE_CHATS = load_sources()

    if chat_id in SOURCE_CHATS:
        await event.reply(
            f"⚠️ Already exists: {chat_id}\n\n"
            f"📡 Monitoring {len(SOURCE_CHATS)} groups"
        )
        return

    SOURCE_CHATS.append(chat_id)
    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Added source: {chat_id}\n"
        f"📡 Now monitoring {len(SOURCE_CHATS)} groups\n\n"
        f"⚡ Active immediately!"
    )

    print(f"✅ Added source from group: {chat_id}")

@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    pattern=r'^/removesource\s+(-?\d+)$'
))
async def cmd_group_removesource(event):
    """Remove source from target group - WORKS FOR ANY USER"""
    global SOURCE_CHATS

    chat_id = int(event.pattern_match.group(1))
    SOURCE_CHATS = load_sources()

    if chat_id not in SOURCE_CHATS:
        await event.reply(
            f"❌ Not found: {chat_id}\n\n"
            f"📡 Monitoring {len(SOURCE_CHATS)} groups"
        )
        return

    SOURCE_CHATS.remove(chat_id)
    save_sources(SOURCE_CHATS)

    await event.reply(
        f"✅ Removed source: {chat_id}\n"
        f"📡 Now monitoring {len(SOURCE_CHATS)} groups\n\n"
        f"⚡ Change active immediately!"
    )

    print(f"➖ Removed source from group: {chat_id}")

@client.on(events.NewMessage(
    chats=[TARGET_GROUP],
    pattern=r'^/sources$'
))
async def cmd_group_sources(event):
    """List sources from target group - WORKS FOR ANY USER"""
    global SOURCE_CHATS
    SOURCE_CHATS = load_sources()

    if not SOURCE_CHATS:
        await event.reply("❌ No source chats configured")
        return

    lines = [f"📡 MONITORING {len(SOURCE_CHATS)} SOURCES\n"]
    for i, cid in enumerate(SOURCE_CHATS, 1):
        chat_name = await get_chat_name(cid)
        lines.append(f"{i}. {chat_name} ({cid})")

    await event.reply("\n".join(lines))

# ================== COMMANDS - STATISTICS ==================

@client.on(events.NewMessage(pattern=r'^/stats$'))
async def cmd_stats(event):
    """Show full statistics"""
    stats = load_stats()
    win_count = stats.get("tp_hits", 0)
    loss_count = stats.get("sl_hits", 0)
    total = win_count + loss_count
    win_rate = (win_count / total * 100) if total > 0 else 0

    msg = (
        f"📊 FULL DASHBOARD\n"
        f"{'='*40}\n"
        f"📈 Total Signals: {stats.get('signals', 0)}\n"
        f"🖼️ Images Forwarded: {stats.get('images', 0)}\n"
        f"💰 Balance: ${stats.get('balance', 0):,.2f}\n"
        f"{'='*40}\n"
        f"✅ TP Hits: {win_count}\n"
        f"   Pips Gained: {stats.get('tp_pips', 0):,.2f}\n"
        f"❌ SL Hits: {loss_count}\n"
        f"   Pips Lost: {stats.get('sl_pips', 0):,.2f}\n"
        f"{'='*40}\n"
        f"📊 Win Rate: {win_rate:.2f}%\n"
    )

    await event.reply(msg)

@client.on(events.NewMessage(pattern=r'^/signals$'))
async def cmd_signals(event):
    """Show signals count"""
    stats = load_stats()
    await event.reply(f"📡 SIGNALS RECEIVED\n{'='*40}\nTotal: {stats.get('signals', 0)}\n")

@client.on(events.NewMessage(pattern=r'^/images$'))
async def cmd_images(event):
    """Show images forwarded"""
    stats = load_stats()
    await event.reply(f"🖼️ IMAGES FORWARDED\n{'='*40}\nTotal: {stats.get('images', 0)}\n")

@client.on(events.NewMessage(pattern=r'^/balance$'))
async def cmd_balance(event):
    """Show account balance"""
    stats = load_stats()
    balance = stats.get('balance', 0)
    await event.reply(f"💰 ACCOUNT BALANCE\n{'='*40}\nBalance: ${balance:,.2f}\n")

@client.on(events.NewMessage(pattern=r'^/tp$'))
async def cmd_tp(event):
    """Show TP hits"""
    stats = load_stats()
    tp_hits = stats.get("tp_hits", 0)
    tp_pips = stats.get("tp_pips", 0)
    await event.reply(f"✅ TARGET PRICE HITS\n{'='*40}\nTP Hits: {tp_hits}\nPips Gained: {tp_pips:,.2f}\n")

@client.on(events.NewMessage(pattern=r'^/sl$'))
async def cmd_sl(event):
    """Show SL hits"""
    stats = load_stats()
    sl_hits = stats.get("sl_hits", 0)
    sl_pips = stats.get("sl_pips", 0)
    await event.reply(f"❌ STOP LOSS HITS\n{'='*40}\nSL Hits: {sl_hits}\nPips Lost: {sl_pips:,.2f}\n")

@client.on(events.NewMessage(pattern=r'^/ratio$'))
async def cmd_ratio(event):
    """Show win/loss ratio"""
    stats = load_stats()
    win_count = stats.get("tp_hits", 0)
    loss_count = stats.get("sl_hits", 0)
    total = win_count + loss_count
    
    if total == 0:
        win_rate = loss_rate = 0
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

# ================== MAIN SIGNAL & IMAGE HANDLER ==================

@client.on(events.NewMessage)
async def handler(event):
    """Main signal processing handler + Image forwarding"""
    try:
        # Skip if in STANDBY mode
        if BOT_MODE == "STANDBY":
            if ENHANCED_DEBUG:
                print(f"\n⏸️  STANDBY MODE - Message skipped")
            return

        chat_id = event.chat_id
        raw_text = event.message.message or ""
        has_media = event.message.media is not None

        if not raw_text.strip() and not has_media:
            return

        # Skip commands
        if raw_text.startswith("/"):
            return

        # Reload sources from file to stay in sync
        global SOURCE_CHATS
        SOURCE_CHATS = load_sources()

        # ================== SOURCE CHECK WITH DEBUG ==================
        is_source = chat_id in SOURCE_CHATS

        if ENHANCED_DEBUG and (raw_text.strip() or has_media):
            print("\n" + "="*70)
            if has_media:
                print("🔍 ENHANCED DEBUG - MEDIA MESSAGE RECEIVED")
            else:
                print("🔍 ENHANCED DEBUG - MESSAGE RECEIVED")
            print("="*70)
            print(f"📨 Chat ID: {chat_id}")
            print(f"📝 Message: {raw_text[:100] if raw_text else '(no text)'}")
            if has_media:
                print(f"🖼️  Media Type: {type(event.message.media).__name__}")

        if ENHANCED_DEBUG and (raw_text.strip() or has_media):
            print(f"\n📋 SOURCE CHECK:")
            print(f"   Current monitored sources: {SOURCE_CHATS}")
            print(f"   Is '{chat_id}' in sources? {'✅ YES' if is_source else '❌ NO'}")
            print(f"   Total sources: {len(SOURCE_CHATS)}")

        # Check if from monitored source
        if not is_source:
            if ENHANCED_DEBUG and (raw_text.strip() or has_media):
                print(f"\n⚠️  SOURCE NOT MONITORED")
                print(f"   Chat ID {chat_id} is NOT in SOURCE_CHATS")
                print(f"   This message will be SKIPPED")
                print(f"   To add this source, use in target group:")
                print(f"   👉 /addsource {chat_id}")
                print("="*70 + "\n")
            if raw_text.strip():
                print(f"\n❌ SKIPPED: Group {chat_id} not in SOURCE_CHATS")
                print(f"   Monitored groups: {SOURCE_CHATS}")
            return

        if ENHANCED_DEBUG and (raw_text.strip() or has_media):
            print(f"\n✅ SOURCE IS MONITORED - Processing message")

        # ================== IMAGE FORWARDING ==================
        if has_media and ENABLE_IMAGE_FORWARDING:
            await handle_image_forwarding(event, chat_id)
            if ENHANCED_DEBUG:
                print("="*70 + "\n")
            return

        # ================== TEXT SIGNAL PROCESSING ==================
        if not raw_text.strip():
            return

        # Normalize text
        text = normalize_text(raw_text)

        if ENHANCED_DEBUG:
            print(f"\n📊 TEXT NORMALIZATION:")
            print(f"   Original:   {raw_text[:80]}")
            print(f"   Normalized: {text[:80]}")

        print(f"\n📨 MESSAGE FROM {chat_id}")
        print(f"   Raw:        {raw_text[:80]}")
        print(f"   Normalized: {text[:80]}")

        # Check if it's a signal
        from normalizer import is_signal
        
        is_sig = is_signal(text)

        if ENHANCED_DEBUG:
            print(f"\n🔎 SIGNAL DETECTION:")
            print(f"   is_signal() returned: {is_sig}")
            if is_sig:
                print(f"   ✅ This IS a signal")
            else:
                print(f"   ❌ This is NOT a signal")

        if not is_sig:
            print(f"   ❌ NOT A SIGNAL (no BUY/SELL or TP/SL detected)")
            return

        print(f"   ✅ Detected as signal")

        # Parse signal
        data = parse_signal(text)
        chat_name = await get_chat_name(chat_id)

        print(f"\n   📊 PARSED DATA:")
        print(f"      Type:   {data['type']}")
        print(f"      Symbol: {data['symbol']}")
        print(f"      Entry:  {data['entry']}")
        print(f"      TP:     {data['tp']}")
        print(f"      SL:     {data['sl']}")

        if ENHANCED_DEBUG:
            print(f"\n📈 PARSING RESULTS:")
            print(f"   Type: {data['type']} {'✅' if data['type'] else '❌'}")
            print(f"   Symbol: {data['symbol']} {'✅' if data['symbol'] else '❌'}")
            print(f"   Entry: {data['entry']} {'✅' if data['entry'] else '❌'}")
            print(f"   TP List: {data['tp']} {'✅' if data['tp'] else '❌'}")
            print(f"   SL: {data['sl']} {'✅' if data['sl'] else '❌'}")

        # Raw fallback if missing data
        if not data["type"] or not data["entry"] or not data["tp"]:
            print(f"\n   ⚠️ INCOMPLETE - Forwarding as RAW")
            missing = []
            if not data["type"]: missing.append("TYPE")
            if not data["entry"]: missing.append("ENTRY")
            if not data["tp"]: missing.append("TP")
            print(f"      Missing: {', '.join(missing)}")
            
            if ENHANCED_DEBUG:
                print(f"\n⚠️  INCOMPLETE SIGNAL - Using Raw Forward")
                print(f"   Missing fields: {', '.join(missing)}")

            await client.send_message(TARGET_GROUP, text)
            print(f"   ✅ Raw forwarded\n")
            
            try:
                stats = load_stats()
                stats["signals"] += 1
                save_stats(stats)
            except Exception as e:
                print(f"   ⚠️ Stats error: {e}")
            return

        # Format and send signal
        output = format_signal(data, source=chat_name)

        try:
            if ENHANCED_DEBUG:
                print(f"\n📤 FORMATTING & SENDING:")
                print(f"   Source: {chat_name}")
                print(f"   Target: {TARGET_GROUP}")

            await client.send_message(TARGET_GROUP, output)
            print(f"\n   📤 FORMATTED OUTPUT:")
            for line in output.split('\n'):
                print(f"      {line}")
            print(f"\n   ✅ FORWARDED TO TARGET GROUP\n")
            
            if ENHANCED_DEBUG:
                print(f"✅ SUCCESSFULLY SENT TO TARGET GROUP")
                print(f"   Message: {output.split(chr(10))[0]}...")

            try:
                stats = load_stats()
                stats["signals"] += 1
                save_stats(stats)
            except Exception as e:
                print(f"   ⚠️ Stats error: {e}")

        except Exception as send_error:
            print(f"\n   ❌ FAILED TO SEND: {send_error}\n")
            if ENHANCED_DEBUG:
                print(f"❌ SEND ERROR: {send_error}")

        if ENHANCED_DEBUG:
            print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ HANDLER ERROR: {e}\n")
        if ENHANCED_DEBUG:
            import traceback
            print("Full traceback:")
            print(traceback.format_exc())

# ================== IMAGE FORWARDING HANDLER ==================

async def handle_image_forwarding(event, chat_id):
    """
    Handle image/photo forwarding from monitored sources
    Forwards images directly to target group with validation
    """
    try:
        if ENHANCED_DEBUG:
            print(f"\n🖼️  IMAGE FORWARDING HANDLER TRIGGERED")

        # Check media type
        media = event.message.media
        media_type = type(media).__name__

        if ENHANCED_DEBUG:
            print(f"   Media Type: {media_type}")

        # Only handle photos and images
        if not isinstance(media, (MessageMediaPhoto, MessageMediaDocument)):
            if ENHANCED_DEBUG:
                print(f"   ❌ Unsupported media type: {media_type}")
                print(f"   Supported: Photos, Images")
            return

        # Get file size
        file_size_mb = await get_file_size(media)
        
        if ENHANCED_DEBUG:
            if file_size_mb:
                print(f"   File Size: {file_size_mb:.2f} MB")
            print(f"   Max Allowed: {MAX_IMAGE_SIZE_MB} MB")

        # Check file size
        if file_size_mb and file_size_mb > MAX_IMAGE_SIZE_MB:
            if ENHANCED_DEBUG:
                print(f"   ❌ File too large - SKIPPED")
                print(f"   {file_size_mb:.2f} MB > {MAX_IMAGE_SIZE_MB} MB limit")
            return

        # Prepare caption if text exists
        caption = event.message.message or ""
        
        if ENHANCED_DEBUG:
            if caption:
                print(f"   Caption: {caption[:50]}")
            else:
                print(f"   Caption: (no text)")

        # Download and forward image
        source_name = await get_chat_name(chat_id)
        
        if ENHANCED_DEBUG:
            print(f"\n📤 FORWARDING IMAGE:")
            print(f"   From: {source_name} ({chat_id})")
            print(f"   To: {TARGET_GROUP}")

        # Forward the message
        await client.forward_messages(
            entity=TARGET_GROUP,
            messages=event.message.id,
            from_peer=event.chat_id
        )

        if ENHANCED_DEBUG:
            print(f"   ✅ IMAGE FORWARDED SUCCESSFULLY")

        # Update statistics
        try:
            stats = load_stats()
            stats["images"] = stats.get("images", 0) + 1
            save_stats(stats)
            if ENHANCED_DEBUG:
                print(f"   📊 Stats updated: {stats['images']} total images")
        except Exception as e:
            print(f"   ⚠️ Stats error: {e}")

        print(f"\n   ✅ IMAGE PROCESSED\n")

    except Exception as e:
        print(f"\n   ❌ IMAGE FORWARDING ERROR: {e}\n")
        if ENHANCED_DEBUG:
            import traceback
            print("Full traceback:")
            print(traceback.format_exc())

# ================== MAIN ==================

async def main():
    """Main bot startup"""
    await client.start()
    print("\n" + "="*70)
    print("✅ TELETHON CONNECTED")
    print("="*70)

    # Load and display sources
    global SOURCE_CHATS
    SOURCE_CHATS = load_sources()

    print(f"\n🔄 Loading {len(SOURCE_CHATS)} source groups...")
    failed = 0
    for i, chat_id in enumerate(SOURCE_CHATS, 1):
        try:
            entity = await client.get_entity(chat_id)
            name = entity.title or str(chat_id)
            print(f"   {i}. ✅ {name} ({chat_id})")
        except Exception as e:
            print(f"   {i}. ❌ {chat_id} - Error: {str(e)[:40]}")
            failed += 1

    if failed > 0:
        print(f"\n⚠️  Warning: {failed} group(s) failed to load (may not have access)")

    # Get target group
    try:
        target_entity = await client.get_entity(TARGET_GROUP)
        print(f"\n🎯 Target group: {target_entity.title} ({TARGET_GROUP})")
    except Exception as e:
        print(f"\n❌ Target group error: {e}")
        return

    # Send startup message
    if SEND_TEST_ON_START:
        try:
            mode_emoji = "🟢" if BOT_MODE == "ACTIVE" else "🟡"
            mode_text = "ACTIVE - FORWARDING" if BOT_MODE == "ACTIVE" else "STANDBY - BACKUP"
            image_status = "🖼️ Images: ✅" if ENABLE_IMAGE_FORWARDING else "🖼️ Images: ❌"

            msg = (
                f"{mode_emoji} BOT {mode_text}\n"
                f"📡 Monitoring {len(SOURCE_CHATS)} groups\n"
                f"{image_status}\n"
                f"⚡ Dynamic source management enabled\n"
                f"🐛 Enhanced Debug logging: ON"
            )

            await client.send_message(target_entity, msg)
            print("✅ Start message sent")

        except Exception as e:
            print(f"❌ Start message failed: {e}")

    # Start heartbeat
    asyncio.ensure_future(send_heartbeat(target_entity))
    print("💓 Heartbeat started")
    print("\n" + "="*70)
    print("🚀 LISTENING FOR SIGNALS & IMAGES")
    print("="*70)
    print("\nEnhanced debug logging enabled")
    print(f"Image forwarding: {'✅ ENABLED' if ENABLE_IMAGE_FORWARDING else '❌ DISABLED'}")
    print("To toggle: Set ENABLE_IMAGE_FORWARDING = True/False in code\n")

    # Run until disconnected
    try:
        await client.run_until_disconnected()
    except asyncio.CancelledError:
        pass
    finally:
        try:
            if not client.is_connected():
                await client.connect()

            await client.send_message(
                target_entity,
                "🔴 BOT STOPPED\n⚠️ Forwarding paused"
            )
        except Exception as e:
            print(f"❌ Stop message error: {e}")
        finally:
            await client.disconnect()

# ================== RUN ==================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("  🚀 SIGNAL FORWARDER BOT v2.5")
        print("  📡 Dynamic Source Management (No Restart Needed!)")
        print("  🖼️  Image Forwarding Support (NEW!)")
        print("  ✅ Enhanced Debug Logging")
        print("="*60 + "\n")
        
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")