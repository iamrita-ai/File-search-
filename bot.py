# ============================================================
#                    IMPORTS & BASIC SETUP
# ============================================================

import os
import asyncio
from flask import Flask
from threading import Thread

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message
)

from pymongo import MongoClient
from pyrogram.filters import create

import openai

# ============================================================
#                    ENVIRONMENT VARIABLES
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URL = os.getenv("MONGO_DB")

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

openai.api_key = OPENAI_API_KEY

# ============================================================
#                      FLASK KEEP ALIVE
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Alive ❤️"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

# ============================================================
#                      MONGO DATABASE
# ============================================================

mongo = MongoClient(MONGO_URL)
db = mongo["TG_BOT"]
files_col = db["files"]
users_col = db["users"]
premium_col = db["premium"]
settings_col = db["settings"]

# ============================================================
#                      PYROGRAM CLIENT
# ============================================================

bot = Client(
    "main-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
)

# ============================================================
#                    CUSTOM NON-COMMAND FILTER
# ============================================================

def non_command_filter(_, __, msg):
    return not (msg.text and msg.text.startswith("/"))

non_command = create(non_command_filter)

# ============================================================
#                    SAVE USER SETTINGS DEFAULT
# ============================================================

def get_settings(uid):
    data = settings_col.find_one({"user_id": uid})
    if data:
        return data
    
    settings_col.insert_one({
        "user_id": uid,
        "mode": "chatgpt",   # options: chatgpt / filesearch
        "caption": "",
        "replace_words": "",
        "source_channel": "",
        "log_channel": LOGS_CHANNEL
    })
    return settings_col.find_one({"user_id": uid})

# ============================================================
#                     START COMMAND
# ============================================================

@bot.on_message(filters.command("start"))
async def start_cmd(_, m):
    uid = m.from_user.id
    get_settings(uid)

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ My Owner", url="https://t.me/technicalserena")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💬 Chat With GF", callback_data="mode_chat")],
        [InlineKeyboardButton("📁 File Search", callback_data="mode_file")]
    ])

    await m.reply_text(
        f"Hi *Jaan* ❤️\n"
        f"Main tumhari virtual Girlfriend ho 💋\n"
        f"Aaj kya karna chahoge? ☺️",
        reply_markup=btn
    )

# ============================================================
#                     SETTINGS PANEL
# ============================================================

@bot.on_callback_query(filters.regex("settings"))
async def open_settings(_, q):
    uid = q.from_user.id
    s = get_settings(uid)

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 ChatGPT Mode", callback_data="mode_chat"),
            InlineKeyboardButton("📁 File Search", callback_data="mode_file")
        ],
        [
            InlineKeyboardButton("📝 Caption", callback_data="set_caption"),
            InlineKeyboardButton("🔤 Replace Words", callback_data="set_replace")
        ],
        [
            InlineKeyboardButton("📨 Source Channel", callback_data="set_source"),
            InlineKeyboardButton("📢 Logs Channel", callback_data="set_logs")
        ]
    ])
    await q.message.edit_text(
        "⚙️ *Settings Panel* — Choose Any Option 👇",
        reply_markup=btn
    )

# ============================================================
#              MODE SWITCHING (CHATGPT / FILE SEARCH)
# ============================================================

@bot.on_callback_query(filters.regex("mode_chat"))
async def set_chat(_, q):
    settings_col.update_one(
        {"user_id": q.from_user.id},
        {"$set": {"mode": "chatgpt"}},
        upsert=True
    )
    await q.answer("GF Chat Mode Enabled ❤️", show_alert=True)

@bot.on_callback_query(filters.regex("mode_file"))
async def set_file(_, q):
    settings_col.update_one(
        {"user_id": q.from_user.id},
        {"$set": {"mode": "filesearch"}},
        upsert=True
    )
    await q.answer("File Search Enabled 📁", show_alert=True)

# ============================================================
#                 CHATGPT GIRLFRIEND CHAT
# ============================================================

async def gf_chat(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a romantic girlfriend. Reply sweet, caring and flirty."
                },
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message["content"]
    except:
        return "Baby thoda error aa gaya… try again ☺️"

# ============================================================
#                  FILE SEARCH SYSTEM
# ============================================================

def match(query, fname):
    q = query.lower().split()
    f = fname.lower()
    count = sum(1 for w in q if w in f)
    return count >= 1  # minimum 1 match

async def file_search(query):
    result = []
    for doc in files_col.find():
        if match(query, doc["file_name"]):
            result.append(doc)
    return result[:20]

# ============================================================
#               ALL PRIVATE TEXT MESSAGES HANDLER
# ============================================================

@bot.on_message(filters.private & filters.text & non_command)
async def private_main_handler(_, m: Message):
    uid = m.from_user.id
    text = m.text

    s = get_settings(uid)
    mode = s["mode"]

    # ========== PREMIUM CHECK ===========
    if not premium_col.find_one({"user": uid}):
        await m.reply_text("Jaan, tum premium nahi ho… 💔")
        return

    # ========== CHATGPT MODE ==========
    if mode == "chatgpt":
        reply = await gf_chat(text)
        await m.reply_text(reply)
        return

    # ========== FILE SEARCH MODE ==========
    if mode == "filesearch":
        files = await file_search(text)
        if not files:
            await m.reply_text("Jaan koi file nahi mili… try again 💕")
            return

        for f in files:
            await m.reply_document(
                f["file_id"],
                caption=f"❤️ File Tumhare Liye — `{f['file_name']}`"
            )
        return

# ============================================================
#               PREMIUM / REMOVE / STATUS COMMANDS
# ============================================================

@bot.on_message(filters.command("addpremium"))
async def add_p(_, m):
    if m.from_user.id != OWNER_ID:
        return
    if not m.reply_to_message:
        return await m.reply("Reply to a user!")

    uid = m.reply_to_message.from_user.id
    premium_col.insert_one({"user": uid})
    await m.reply("User added to premium ❤️")

@bot.on_message(filters.command("rem"))
async def rm_p(_, m):
    if m.from_user.id != OWNER_ID:
        return
    if not m.reply_to_message:
        return await m.reply("Reply to a user!")

    uid = m.reply_to_message.from_user.id
    premium_col.delete_one({"user": uid})
    await m.reply("User removed 😢")

@bot.on_message(filters.command("status"))
async def status(_, m):
    await m.reply_text("Bot Running Perfectly ❤️")

# ============================================================
#                       START BOT
# ============================================================

def start_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot.run()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    start_bot()
