import os
import re
import random
import asyncio
from datetime import datetime
from flask import Flask
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import idle

# ==========================
# ENV + CONSTANTS
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

MONGO_URI = os.getenv("MONGO_DB_URI")   # ⭐ ADDED AGAIN
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

# ==========================
# MONGO CONNECT
# ==========================
mongo = MongoClient(MONGO_URI)
db = mongo["sweetheart_db"]
files_db = db["files"]

# ==========================
# TELEGRAM BOT
# ==========================
bot = Client(
    "sweetheart-romantic-bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# ==========================
# ROMANTIC LINES
# ==========================
romantic_lines = [
    "Janu ❤️", "Baby 😘", "Sweetheart 💕",
    "Come near me 😍", "Miss you meri jaan 💋",
    "Hold me tight 💞", "Love you baby ❤️"
]

# ==========================
# TYPING EFFECT
# ==========================
async def type(msg, txt):
    await msg.reply_chat_action("typing")
    await asyncio.sleep(0.8)
    await msg.reply_text(txt)

# ==========================
# AUTO GREETINGS
# ==========================
async def auto_greet():
    while True:
        h = datetime.now().hour
        if h == 7:
            await bot.send_message(OWNER_ID, "Good Morning Sweetheart 🌅❤️")
            await asyncio.sleep(3600)
        elif h == 22:
            await bot.send_message(OWNER_ID, "Good Night Baby 🌙💤❤️")
            await asyncio.sleep(3600)
        await asyncio.sleep(600)

# ==========================
# START
# ==========================
@bot.on_message(filters.command("start"))
async def start(_, m):
    await type(m, f"Hello Sweetheart ❤️ I am always with you 😘")
    await m.reply(
        "Choose an option love 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Me", url=f"https://t.me/{MY_USERNAME}")],
            [InlineKeyboardButton("❤️ Help Menu", callback_data="help")]
        ])
    )

# ==========================
# HELP
# ==========================
@bot.on_callback_query(filters.regex("help"))
async def help_btn(_, q):
    await q.message.edit(
        "**❤️ Romantic Bot Commands**\n\n"
        "• /start – Start bot\n"
        "• /help – Help Menu\n"
        "• /broadcast – Send msg to all users\n"
        "• /addpremium – Add Premium User\n"
        "• /rmpremium – Remove Premium User\n"
        "• /plan – Show premium plans\n"
        "• /status – Bot stats\n"
        "• /settings – Open settings\n\n"
        "**Send any keyword to fetch files from database** 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Dev", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

@bot.on_message(filters.command("help"))
async def help_cmd(c, m):
    await help_btn(c, m)

# ==========================
# SAVE FILES (to Mongo)
# ==========================
@bot.on_message(filters.document | filters.photo | filters.video)
async def save_file(_, m):
    try:
        file_id = (
            m.document.file_id if m.document else
            m.photo.file_id if m.photo else
            m.video.file_id
        )

        caption = m.caption or ""

        files_db.insert_one({
            "file_id": file_id,
            "caption": caption.lower()
        })

        await type(m, "Saved Meri Jaan ❤️")
    except:
        pass

# ==========================
# FILE SEARCH (2–3 word match)
# ==========================
def similar(q, caption):
    q_words = q.lower().split()
    c_words = caption.lower().split()
    return sum(1 for w in q_words if w in c_words) >= 2

@bot.on_message(filters.text & ~filters.command(["start", "help"]))
async def search(_, m):
    q = m.text.lower()
    results = list(files_db.find({}))

    final = []
    for i in results:
        if similar(q, i["caption"]):
            final.append(i)

    if not final:
        return await type(m, "🌸 No Results Found — But I am here, Sweetheart 💕")

    for f in final[:15]:
        try:
            await bot.send_cached_media(
                chat_id=m.chat.id,
                file_id=f["file_id"],
                caption="Here baby ❤️"
            )
            await asyncio.sleep(0.4)
        except:
            pass

# ==========================
# OWNER COMMANDS
# ==========================
@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(_, m):
    msg = m.text.replace("/broadcast ", "")
    await bot.send_message(LOGS_CHANNEL, f"Broadcast: {msg}")
    await m.reply("Broadcast sent ❤️")

@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def add_p(_, m):
    await m.reply("Premium Added 💎")

@bot.on_message(filters.command("rmpremium") & filters.user(OWNER_ID))
async def rm_p(_, m):
    await m.reply("Premium Removed ❌")

@bot.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status(_, m):
    await m.reply("Bot running smoothly ❤️")

@bot.on_message(filters.command("settings"))
async def settings(_, m):
    await m.reply(
        "Settings Menu ❤️",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Contact Dev", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

# ==========================
# FLASK (REQUIRED FOR RENDER)
# ==========================
server = Flask(__name__)

@server.route("/")
def home():
    return "Sweetheart Bot Running ❤️"

# ==========================
# RUN BOTH (BOT + FLASK)
# ==========================
async def run_all():
    asyncio.create_task(auto_greet())
    await bot.start()
    print("Bot Running… ❤️")
    await idle()

if __name__ == "__main__":
    import threading

    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))).start()

    asyncio.run(run_all())
