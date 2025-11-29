import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# =========================
# FIXED VARIABLES
# =========================
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377     # <-- Yaha Apna Logs Channel ID Laga Dena ❤️
SOURCE_CHANNEL = None

# =========================
# ENV VARIABLES (Render)
# =========================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN"))
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# =========================
# MONGO SETUP
# =========================
mongo = MongoClient(MONGO_DB_URI)
db = mongo["sweetheart_love_bot"]
files_col = db["files"]
config_col = db["config"]

saved = config_col.find_one({"_id": "config"})
if saved:
    SOURCE_CHANNEL = saved.get("source")

def save_config():
    config_col.update_one(
        {"_id": "config"},
        {"$set": {"source": SOURCE_CHANNEL}},
        upsert=True
    )

# =========================
# FLASK APP
# =========================
app = Flask("sweetheart_web_bot")
@app.route("/")
def home():
    return "💗 Sweetheart Bot Working on Render!"

# =========================
# PYROGRAM CLIENT
# =========================
bot = Client("sweetheart_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# =====================================================
# SAVE FILES IN DB WHEN POSTED IN SOURCE CHANNEL
# =====================================================
@bot.on_message(filters.channel)
async def log_channel_msg(client, msg):
    global SOURCE_CHANNEL

    # Save ALL messages into Logs channel
    try:
        await msg.copy(LOGS_CHANNEL)
    except:
        pass

    # Only index if it is source channel
    if SOURCE_CHANNEL and msg.chat.id == SOURCE_CHANNEL:
        name = " ".join((msg.caption or msg.text or "file").lower().split()[:6])

        files_col.insert_one({
            "file_id": msg.id,
            "source_chat": SOURCE_CHANNEL,
            "name": name,
            "type": "media"
        })

        await bot.send_message(OWNER_ID, f"🌸 Saved: {name}")


# =====================================================
# SEARCH FILES (MINIMUM 3 WORD MATCH)
# =====================================================
def search_files(query):
    q_words = query.lower().split()
    if len(q_words) < 3:
        return []

    results = []
    for f in files_col.find():
        name_words = f["name"].split()
        matches = len(set(q_words) & set(name_words))
        if matches >= 3:
            results.append(f)

    return results[:10]


@bot.on_message(filters.private & filters.text & ~filters.command(["start","help","settings"]))
async def pm_text(client, message):
    text = message.text.strip()

    # romantic auto reply
    if len(text.split()) < 3:
        return await message.reply("Aww baby… bol na aur kya chahiye meri jaan ❤️✨")

    files = search_files(text)

    if not files:
        return await message.reply("🌸 **No Results Found — Sweetheart try another keyword**.")

    await message.reply(f"🌸 **Found {len(files)} Results**:")

    for f in files:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=f["source_chat"],
                message_id=f["file_id"]
            )
        except:
            pass


# =====================================================
# START
# =====================================================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Contact Owner", url="https://t.me/technicalSerena")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])
    await message.reply("Hello my Sweetheart ❤️ How can I pamper you today?", reply_markup=keyboard)


# =====================================================
# HELP
# =====================================================
@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply(
        "🌸 **How to use me:**\n"
        "➤ Add me to Source Channel\n"
        "➤ Set it using /setsource\n"
        "➤ I store all files into logs\n"
        "➤ Just type filename (min 3 words match)\n\n"
        "👑 Owner: @technicalSerena"
    )


# =====================================================
# SET SOURCE
# =====================================================
@bot.on_message(filters.command("setsource") & filters.user(OWNER_ID))
async def set_source(client, message):
    await message.reply("📡 **Send Source Channel ID (with -100)**")

@bot.on_message(filters.private & filters.text)
async def set_id_handler(client, msg):
    global SOURCE_CHANNEL
    text = msg.text

    if text.startswith("-100") and SOURCE_CHANNEL is None:
        SOURCE_CHANNEL = int(text)
        save_config()
        return await msg.reply("💞 **Source Channel Set Successfully Baby!**")


# =====================================================
# SETTINGS PANEL
# =====================================================
@bot.on_callback_query()
async def cb(client, q):
    if q.data == "settings":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📡 Change Source", callback_data="setsrc")],
            [InlineKeyboardButton("🗑 Clear DB", callback_data="clear")],
            [InlineKeyboardButton("💞 Owner", url="https://t.me/technicalSerena")]
        ])
        await q.message.edit("⚙️ **Settings Panel**", reply_markup=keyboard)

    if q.data == "clear":
        files_col.delete_many({})
        await q.answer("Database Cleared 💗", show_alert=True)

    if q.data == "setsrc":
        await q.message.reply("📡 Send New Source Channel ID (-100)")


# =====================================================
# RUN BOT + FLASK
# =====================================================
def start_bot():
    bot.run()

if __name__ == "__main__":
    threading.Thread(target=start_bot).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
