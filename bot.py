# bot.py
import os
import asyncio
import threading
from datetime import datetime
from typing import Optional

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message
)
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------- CONFIG ----------------
# Owner ID (you gave)
OWNER_ID = 1598576202

# Static UI strings
BOT_CREDIT = "@technicalserena"
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003286415377"))  # optional override
# Initial default sources (can be empty). Real list will be loaded from DB.
SOURCE_CHANNELS = []

# ---------------- ENV (secrets stored in Render env) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# Basic checks (fail fast with clear log if env missing)
if not BOT_TOKEN or not API_ID or not API_HASH or not MONGO_DB_URI:
    print("ERROR: Missing one of required env vars: BOT_TOKEN, API_ID, API_HASH, MONGO_DB_URI")
    print("Make sure to set them in Render environment variables.")
    # Do not exit; Pyrogram will error later - but we log clearly.
# convert API_ID to int safely
try:
    API_ID = int(API_ID) if API_ID else None
except:
    API_ID = None

# ---------------- MONGO SETUP ----------------
mongo_client = AsyncIOMotorClient(MONGO_DB_URI) if MONGO_DB_URI else None
db = mongo_client["TelegramBotDB"] if mongo_client else None
users_col = db["Users"] if db else None
config_col = db["Config"] if db else None
pending_col = db["Pending"] if db else None  # store short-lived "waiting for reply" entries

# ---------------- PYROGRAM CLIENT ----------------
app = Client(
    "SerenaRomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    # you can tune session_name/path here if needed
)

# ---------------- FLASK (dummy web server for Render Web Service) ----------------
flask_app = Flask("serena_dummy")

@flask_app.route("/")
def homepage():
    return "Serena Bot is alive ❤️"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # set debug=False in production
    flask_app.run(host="0.0.0.0", port=port)

# Start flask in background so Render sees an open port
threading.Thread(target=run_flask, daemon=True).start()

# ---------------- UTIL: fast / slow send ----------------
async def fast_send(client: Client, chat_id: int, text: str, **kwargs):
    """Instant replies (used for user-facing replies)."""
    return await client.send_message(chat_id, text, **kwargs)

async def slow_send(client: Client, chat_id: int, text: str, delay: int = 10, **kwargs):
    """Used only when we want to add flood-control pauses (for forwarded/log messages)."""
    msg = await client.send_message(chat_id, text, **kwargs)
    await asyncio.sleep(delay)
    return msg

# ---------------- CONFIG HELPERS ----------------
async def load_source_channels():
    global SOURCE_CHANNELS
    if not config_col:
        print("Warning: config_col not available (Mongo not configured). Using default SOURCE_CHANNELS.")
        return
    cfg = await config_col.find_one({"_id": "source_channels"})
    if cfg and isinstance(cfg.get("channels"), list):
        SOURCE_CHANNELS = cfg["channels"]
    else:
        # ensure DB contains the key (create on first run)
        await config_col.update_one({"_id": "source_channels"}, {"$set": {"channels": SOURCE_CHANNELS}}, upsert=True)

async def save_source_channels():
    if not config_col:
        return
    await config_col.update_one({"_id": "source_channels"}, {"$set": {"channels": SOURCE_CHANNELS}}, upsert=True)

async def set_pending_action(user_id: int, action: str):
    """Store a short pending action in DB so the bot can ask follow-up."""
    if not pending_col:
        return
    await pending_col.update_one({"user_id": user_id}, {"$set": {"action": action, "ts": datetime.utcnow()}}, upsert=True)

async def get_pending_action(user_id: int) -> Optional[str]:
    if not pending_col:
        return None
    doc = await pending_col.find_one({"user_id": user_id})
    return doc.get("action") if doc else None

async def clear_pending_action(user_id: int):
    if not pending_col:
        return
    await pending_col.delete_one({"user_id": user_id})

# ---------------- START COMMAND (romantic + inline button + contact) ----------------
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    name = user.first_name if user and user.first_name else "Sweetheart"

    text = (
        f"✨ Hey *{name}* — I'm your romantic little bot. 💞\n\n"
        "Main tumhare liye hoon — file search, save, aur sab kuch. 🤍\n"
        "Koi bhi cheez chahiye ho toh mujhe message karo, I'll try my best. 😘"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💖 My Creator", url=f"https://t.me/{BOT_CREDIT.lstrip('@')}")],
            [InlineKeyboardButton("📮 Contact Owner", url=f"https://t.me/{BOT_CREDIT.lstrip('@')}")]
        ]
    )

    # send romantic message with inline buttons
    await fast_send(client, message.chat.id, text, parse_mode="markdown")
    await message.reply("💌 Menu open karo baby…", reply_markup=keyboard)

    # save/update user in DB
    if users_col:
        await users_col.update_one(
            {"user_id": user.id},
            {"$set": {"last_active": datetime.utcnow(), "first_name": user.first_name}},
            upsert=True
        )

# ---------------- ALIVE ----------------
@app.on_message(filters.command("alive"))
async def alive_cmd(client: Client, message: Message):
    await fast_send(client, message.chat.id, "🔥 I'm Alive Sweetheart… Tumhare liye 💋")

# ---------------- HELP ----------------
@app.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    txt = (
        "📘 *Sweetheart Help Menu*\n\n"
        "/start — Wake me up 💞\n"
        "/alive — Check if I'm awake 🔥\n"
        "/addchannel — Add a source channel step-by-step (Owner only) ➕\n"
        "/broadcast <text> — Send message to all users (Owner only) 📣\n"
        "/restart — Restart the bot (Owner only) 🔄\n"
        "/cancel — Cancel current action ❌\n"
        "/ban <user_id> — Remove a user (Owner only) 🚫\n\n"
        "📝 *How to search files:* Just send the file title (or part of it) in a private chat with me. "
        "I'll look in saved source messages and send matches. 😘"
    )
    await fast_send(client, message.chat.id, txt, parse_mode="markdown")

# ---------------- RESTART / CANCEL / BAN / BROADCAST ----------------
@app.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def restart_cmd(client: Client, message: Message):
    await fast_send(client, message.chat.id, "🔄 Restarting baby…")
    # Exit process to let Render restart the service
    os.system("kill 1")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(client: Client, message: Message):
    await clear_pending_action(message.from_user.id)
    await fast_send(client, message.chat.id, "❌ Koi action ab cancel kar diya gaya hai meri jaan.")

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_cmd(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await fast_send(client, message.chat.id, "🚫 ID do baby… /ban <user_id>")

    try:
        uid = int(parts[1])
    except:
        return await fast_send(client, message.chat.id, "Invalid ID, numeric chahiye baby.")

    if users_col:
        await users_col.delete_one({"user_id": uid})
    await fast_send(client, message.chat.id, f"🚫 Banned: `{uid}`", parse_mode="markdown")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_cmd(client: Client, message: Message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await fast_send(client, message.chat.id, "Please provide the message to broadcast.")
    sent = 0
    if users_col:
        async for user in users_col.find({}):
            try:
                await fast_send(client, user["user_id"], text)
                sent += 1
            except:
                pass
    await fast_send(client, message.chat.id, f"📣 Broadcast sent to {sent} users.")

# ---------------- ADD CHANNEL (step-by-step) ----------------
@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def addchannel_start(client: Client, message: Message):
    """Starts interactive flow: asks owner for channel id."""
    await set_pending_action(message.from_user.id, "await_channel_id")
    await fast_send(client, message.chat.id, "➕ Send the channel ID now (example: `-1001234567890`) — I'll add it as a source. ❤️", parse_mode="markdown")

# This handler will catch normal messages and process pending action if exists
@app.on_message(filters.private & ~filters.command([]))
async def handle_private_messages(client: Client, message: Message):
    """Handles: follow-up for /addchannel, normal searches, and other private messages."""
    user_id = message.from_user.id
    pending = await get_pending_action(user_id)

    # If owner is in pending 'await_channel_id' flow, treat next message as channel id
    if pending == "await_channel_id" and user_id == OWNER_ID:
        text = (message.text or "").strip()
        # attempt to parse channel id (int) or username (like @channelusername)
        if not text:
            await fast_send(client, message.chat.id, "Please send a valid channel id or username.")
            return

        # handle username (starts with @) or numeric id
        try:
            if text.startswith("@"):
                # resolve username -> try to get chat info
                chat = await client.get_chat(text)
                chan_id = chat.id
            else:
                chan_id = int(text)
        except Exception as e:
            await fast_send(client, message.chat.id, f"Couldn't resolve that channel: {e}")
            await clear_pending_action(user_id)
            return

        # add to SOURCE_CHANNELS and persist
        if chan_id not in SOURCE_CHANNELS:
            SOURCE_CHANNELS.append(chan_id)
            await save_source_channels()
            await fast_send(client, message.chat.id, f"✅ Channel added as source: `{chan_id}`", parse_mode="markdown")
            # notify log channel
            try:
                await fast_send(client, LOG_CHANNEL, f"➕ New source channel added: `{chan_id}`")
            except:
                pass
        else:
            await fast_send(client, message.chat.id, "This channel is already in source list.")

        await clear_pending_action(user_id)
        return

    # If no pending action -> treat as a search query (only in private chats)
    query = (message.text or "").strip()
    if not query:
        return

    # search saved messages in LOG_CHANNEL for media with matching caption or filename
    await fast_send(client, message.chat.id, "🔎 Searching for files… hold on baby…")
    found = []
    try:
        # scan recent messages from LOG_CHANNEL
        async for msg in client.get_chat_history(LOG_CHANNEL, limit=800):
            caption = (msg.caption or "").lower() if msg.caption else ""
            fname = ""
            if msg.document and getattr(msg.document, "file_name", None):
                fname = msg.document.file_name.lower()
            elif msg.video and getattr(msg.video, "file_name", None):
                fname = msg.video.file_name.lower()
            elif msg.audio and getattr(msg.audio, "file_name", None):
                fname = msg.audio.file_name.lower()
            # photo doesn't have file_name; rely on caption
            if query.lower() in caption or query.lower() in fname:
                found.append(msg)
            # small optimization: stop if too many
            if len(found) >= 12:
                break
    except Exception as e:
        await fast_send(client, message.chat.id, f"Error while searching: {e}")
        return

    if not found:
        await fast_send(client, message.chat.id, "😔 Kuch nahi mila meri jaan… Try different keywords.")
        return

    await fast_send(client, message.chat.id, f"📂 {len(found)} result(s) found — sending top results…")
    sent = 0
    for m in found[:6]:  # limit to top 6 to be gentle
        try:
            await m.copy(message.chat.id)
            sent += 1
            await asyncio.sleep(0.8)  # small pause
        except Exception:
            pass

    await fast_send(client, message.chat.id, f"✅ Sent {sent} files. Mahal meri, agar aur chahiye toh batana. 💋")

# ---------------- SAVE SOURCE MESSAGES TO LOG_CHANNEL ----------------
@app.on_message(filters.channel)
async def channel_forward(client: Client, message: Message):
    """When a message appears in any source channel, save a copy into LOG_CHANNEL for searching."""
    global SOURCE_CHANNELS
    # allow both numeric and username sources — but check if we maintain list
    if SOURCE_CHANNELS and message.chat.id not in SOURCE_CHANNELS:
        return

    try:
        # copy the message into log channel for persistence/search
        await message.copy(LOG_CHANNEL)
        # slow_send ensures a pause for flood limits in log chat
        await slow_send(client, LOG_CHANNEL, "✔ File saved Sweetheart.")
    except Exception as e:
        # if copying fails, log it
        try:
            await slow_send(client, LOG_CHANNEL, f"❌ Error while saving source message: {e}")
        except:
            pass

# ---------------- BOOT / RUN ----------------
async def startup_tasks():
    # load channels from DB (if any)
    await load_source_channels()
    print("Source Channels Loaded:", SOURCE_CHANNELS)

    # ensure log channel exists (best-effort)
    try:
        await app.get_chat(LOG_CHANNEL)
    except Exception:
        print("Warning: LOG_CHANNEL might be invalid or bot isn't added to it yet.")

    print("Startup tasks completed.")

if __name__ == "__main__":
    print("Booting bot…")
    # run startup tasks then run the bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(startup_tasks())
    print("Bot Started Successfully ❤️")
    app.run()
