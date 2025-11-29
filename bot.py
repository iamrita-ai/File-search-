import os
import asyncio
import logging
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import datetime

# ------------------- CONFIG ------------------------
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

PORT = int(os.environ.get("PORT", 10000))
logging.basicConfig(level=logging.INFO)

# ------------------- ENV VARIABLES ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB = os.getenv("MONGO_DB")

# ------------------- FLASK ------------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "💗 Sweetheart Bot is Running! ❤️"

# ------------------- MONGO ------------------------
mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo["sweetheart_bot"]
users_col = db["users"]
files_col = db["files"]
config_col = db["config"]

# ------------------- BOT --------------------------
bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50
)

# ------------------- SETTINGS ---------------------
async def get_config():
    cfg = await config_col.find_one({"_id": "config"})
    if not cfg:
        cfg = {"source": None, "logs": LOGS_CHANNEL, "caption": "❤️ File mil gaya Janu!"}
        await config_col.insert_one({"_id": "config", **cfg})
    return cfg

async def save_config(cfg):
    await config_col.update_one({"_id": "config"}, {"$set": cfg}, upsert=True)

# ------------------- COMMANDS ---------------------
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    buttons = [
        [InlineKeyboardButton("❤️ Owner", url=f"https://t.me/{MY_USERNAME}")],
        [InlineKeyboardButton("📁 Search Files", switch_inline_query_current_chat="")]
    ]
    await message.reply_text(
        f"Hello *Janu* ❤️\nMain tumhari Romantic Assistant ho ✨\nAaj kya help chahiye meri Sweetheart? 💋",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "✨ *How to use this Bot*\n\n"
        "1️⃣ Type file name → bot sends matching files\n"
        "2️⃣ Add to Source Channel → files auto-saved\n"
        "3️⃣ /addpremium → give user premium access\n"
        "4️⃣ /rem → remove user from premium\n"
        "5️⃣ /status → check bot speed/storage\n"
        "6️⃣ /clear → clear DB\n"
        "7️⃣ /setting → open settings panel\n\n"
        "Example:\nSend 'holiday video' → bot searches minimum 3-word match\n\n"
        f"👑 Owner: @{MY_USERNAME}"
    )
    await message.reply_text(text)

@bot.on_message(filters.command("alive"))
async def alive_cmd(client, message):
    await message.reply_text("❤️ *Janu, I'm Always With You… Online & Active!*")

@bot.on_message(filters.command("status"))
async def status_cmd(client, message):
    count = await files_col.count_documents({})
    await message.reply_text(f"📊 Files in DB: {count}\n❤️ Owner: @{MY_USERNAME}")

@bot.on_message(filters.command("addpremium"))
async def add_premium(client, message):
    user_id = message.from_user.id
    await users_col.update_one({"_id": user_id}, {"$set": {"premium": True}}, upsert=True)
    await message.reply_text("💞 Premium Access Granted!")
    
@bot.on_message(filters.command("rem"))
async def remove_premium(client, message):
    user_id = message.from_user.id
    await users_col.update_one({"_id": user_id}, {"$set": {"premium": False}})
    await message.reply_text("💔 Premium Access Removed!")

@bot.on_message(filters.command("clear"))
async def clear_cmd(client, message):
    await files_col.delete_many({})
    await message.reply_text("🗑 Database Cleared!")

# ------------------- SETTINGS PANEL -----------------
async def send_settings(message):
    cfg = await get_config()
    buttons = [
        [
            InlineKeyboardButton("📡 Set Source", callback_data="set_source"),
            InlineKeyboardButton("🗑 Remove Logs", callback_data="remove_logs")
        ],
        [
            InlineKeyboardButton("✏️ Replace Words", callback_data="replace_words"),
            InlineKeyboardButton("📝 Set Caption", callback_data="set_caption")
        ],
        [
            InlineKeyboardButton("👑 Owner", url=f"https://t.me/{MY_USERNAME}")
        ]
    ]
    await message.reply_text("⚙️ Settings Panel:", reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_message(filters.command("setting"))
async def setting_cmd(client, message):
    await send_settings(message)

# ------------------- CALLBACK -----------------------
@bot.on_callback_query()
async def callback_handler(client, query):
    data = query.data
    cfg = await get_config()

    if data == "set_source":
        await query.message.reply("📡 Send Source Channel ID (-100)")
    elif data == "remove_logs":
        cfg["logs"] = None
        await save_config(cfg)
        await query.answer("Logs removed 💖", show_alert=True)
    elif data == "set_caption":
        await query.message.reply("📝 Send caption for incoming files")
    elif data == "replace_words":
        await query.message.reply("✏️ Send old_word:new_word pair separated by commas")
    await query.answer()

# ------------------- PRIVATE TEXT HANDLER -----------
@bot.on_message(filters.private & ~filters.command(["start","help","alive","status","addpremium","rem","clear","setting"]))
async def private_text_handler(client, message):
    text = message.text.strip().lower()
    cfg = await get_config()

    # Source/Caption/Replace logic
    if text.startswith("-100"):
        cfg["source"] = int(text)
        await save_config(cfg)
        await message.reply_text("💞 Source Channel Saved Successfully!")
        return
    elif text.startswith("caption:"):
        cfg["caption"] = text.replace("caption:", "").strip()
        await save_config(cfg)
        await message.reply_text("📝 Caption Set Successfully!")
        return

    # File search
    results = []
    async for f in files_col.find():
        match_count = sum(1 for w in text.split() if w in f["file_name"].lower())
        if match_count >= 3:
            results.append(f)

    if not results:
        await message.reply_text("🌸 No Results Found — try different keyword 💕")
        return

    for r in results[:20]:
        caption = cfg.get("caption", "❤️ File mil gaya Janu!")
        await message.reply_document(r["file_id"], caption=caption)

# ------------------- CHANNEL FILES -------------------
@bot.on_message(filters.channel)
async def save_channel_files(client, message):
    cfg = await get_config()
    if cfg.get("source") and message.chat.id == cfg["source"]:
        if message.document or message.video or message.photo:
            if message.document:
                name = message.document.file_name
                file_id = message.document.file_id
            elif message.video:
                name = message.video.file_name or f"video_{message.message_id}.mp4"
                file_id = message.video.file_id
            elif message.photo:
                name = f"photo_{message.message_id}.jpg"
                file_id = message.photo.file_id
            await files_col.insert_one({"file_name": name.lower(), "file_id": file_id})
            if cfg.get("logs"):
                try:
                    await bot.send_message(cfg["logs"], f"📦 New File Saved\n**Name:** `{name}`")
                except:
                    await bot.send_message(OWNER_ID, f"Error saving log for {name}")

# ------------------- RUN ---------------------------
def run():
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start())
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    run()
