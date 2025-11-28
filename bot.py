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
OWNER_ID = 1598576202
BOT_CREDIT = "@technicalserena"

LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003286415377"))
SOURCE_CHANNELS = []

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

if API_ID:
    API_ID = int(API_ID)

# ---------------- MONGO SETUP ----------------
mongo_client = AsyncIOMotorClient(MONGO_DB_URI) if MONGO_DB_URI is not None else None
db = mongo_client["TelegramBotDB"] if mongo_client is not None else None

users_col = db["Users"] if db is not None else None
config_col = db["Config"] if db is not None else None
pending_col = db["Pending"] if db is not None else None

# ---------------- PYROGRAM BOT ----------------
app = Client(
    "SerenaRomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------------- FLASK FOR RENDER ----------------
flask_app = Flask("serena_dummy")

@flask_app.route("/")
def homepage():
    return "Serena Bot is alive ❤️"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ---------------- UTIL ----------------
async def fast_send(client, chat_id, text, **kwargs):
    return await client.send_message(chat_id, text, **kwargs)

async def slow_send(client, chat_id, text, delay=10, **kwargs):
    msg = await client.send_message(chat_id, text, **kwargs)
    await asyncio.sleep(delay)
    return msg

# ---------------- DB HELPERS ----------------
async def load_source_channels():
    global SOURCE_CHANNELS
    if config_col is None:
        return

    cfg = await config_col.find_one({"_id": "source_channels"})
    if cfg is not None and isinstance(cfg.get("channels"), list):
        SOURCE_CHANNELS = cfg["channels"]
    else:
        await config_col.update_one(
            {"_id": "source_channels"},
            {"$set": {"channels": SOURCE_CHANNELS}},
            upsert=True
        )

async def save_source_channels():
    if config_col is not None:
        await config_col.update_one(
            {"_id": "source_channels"},
            {"$set": {"channels": SOURCE_CHANNELS}},
            upsert=True
        )

async def set_pending_action(user_id, action):
    if pending_col is not None:
        await pending_col.update_one(
            {"user_id": user_id},
            {"$set": {"action": action}},
            upsert=True
        )

async def get_pending_action(user_id):
    if pending_col is None:
        return None
    doc = await pending_col.find_one({"user_id": user_id})
    if doc is None:
        return None
    return doc.get("action")

async def clear_pending_action(user_id):
    if pending_col is not None:
        await pending_col.delete_one({"user_id": user_id})

# ---------------- START COMMAND ----------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user = message.from_user
    name = user.first_name if user else "Sweetheart"

    text = (
        f"✨ Hey *{name}* — I'm your romantic bot 💞\n\n"
        "Tumhare liye always here… files search, save, aur sab kuch. 💋\n"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💖 My Creator", url="https://t.me/technicalserena")],
            [InlineKeyboardButton("📮 Contact Owner", url="https://t.me/technicalserena")]
        ]
    )

    await fast_send(client, message.chat.id, text, parse_mode="markdown")
    await message.reply("💌 Menu open karo baby…", reply_markup=keyboard)

    if users_col is not None:
        await users_col.update_one(
            {"user_id": user.id},
            {"$set": {"last_active": datetime.utcnow()}},
            upsert=True
        )

# ---------------- HELP ----------------
@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    txt = (
        "📘 *Sweetheart Help Menu*\n\n"
        "/start — Wake me up 💞\n"
        "/alive — Check me 🔥\n"
        "/addchannel — Add source channel ➕ (Owner)\n"
        "/broadcast <msg> — Send to all users 📣 (Owner)\n"
        "/restart — Restart bot 🔄 (Owner)\n"
        "/cancel — Cancel action ❌\n"
    )
    await fast_send(client, message.chat.id, txt, parse_mode="markdown")

# ---------------- ALIVE ----------------
@app.on_message(filters.command("alive"))
async def alive_cmd(client, message):
    await fast_send(client, message.chat.id, "🔥 Alive sweetheart…")

# ---------------- RESTART ----------------
@app.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def restart_cmd(client, message):
    await fast_send(client, message.chat.id, "🔄 Restarting baby…")
    os.system("kill 1")

# ---------------- CANCEL ----------------
@app.on_message(filters.command("cancel"))
async def cancel_cmd(client, message):
    await clear_pending_action(message.from_user.id)
    await fast_send(client, message.chat.id, "❌ Cancelled baby.")

# ---------------- BROADCAST ----------------
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_cmd(client, message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await fast_send(client, message.chat.id, "Broadcast text do baby…")

    count = 0
    if users_col is not None:
        async for user in users_col.find({}):
            try:
                await fast_send(client, user["user_id"], text)
                count += 1
            except:
                pass

    await fast_send(client, message.chat.id, f"📣 Done. Sent to {count} users.")

# ---------------- ADD CHANNEL ----------------
@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def addchannel_start(client, message):
    await set_pending_action(message.from_user.id, "await_channel")
    await fast_send(client, message.chat.id, "➕ Send channel ID now baby…")

@app.on_message(filters.private & ~filters.command([]))
async def private_messages(client, message):
    user_id = message.from_user.id
    action = await get_pending_action(user_id)

    if action == "await_channel" and user_id == OWNER_ID:
        chan = message.text.strip()
        try:
            if chan.startswith("@"):
                ch = await client.get_chat(chan)
                cid = ch.id
            else:
                cid = int(chan)
        except Exception as e:
            await fast_send(client, message.chat.id, f"Error: {e}")
            return

        if cid not in SOURCE_CHANNELS:
            SOURCE_CHANNELS.append(cid)
            await save_source_channels()

        await fast_send(client, message.chat.id, f"✔ Added: `{cid}`", parse_mode="markdown")
        await clear_pending_action(user_id)
        return

    # Normal search
    query = message.text.lower().strip()
    await fast_send(client, message.chat.id, "🔎 Searching baby…")

    found = []
    async for msg in client.get_chat_history(LOG_CHANNEL, limit=700):
        cap = (msg.caption or "").lower()
        filename = ""

        if msg.document and msg.document.file_name:
            filename = msg.document.file_name.lower()
        if msg.video and msg.video.file_name:
            filename = msg.video.file_name.lower()

        if query in cap or query in filename:
            found.append(msg)

        if len(found) >= 6:
            break

    if not found:
        return await fast_send(client, message.chat.id, "😔 Kuch nahi mila baby…")

    for m in found:
        try:
            await m.copy(message.chat.id)
            await asyncio.sleep(0.8)
        except:
            pass

# ---------------- SAVE SOURCE ----------------
@app.on_message(filters.channel)
async def channel_forward(client, message):
    if message.chat.id not in SOURCE_CHANNELS:
        return

    try:
        await message.copy(LOG_CHANNEL)
        await slow_send(client, LOG_CHANNEL, "✔ Saved baby.")
    except Exception as e:
        await slow_send(client, LOG_CHANNEL, f"❌ Error: {e}")

# ---------------- STARTUP ----------------
async def startup():
    await load_source_channels()
    print("Loaded channels:", SOURCE_CHANNELS)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(startup())
    app.run()
