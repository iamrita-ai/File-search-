import os
import asyncio
from flask import Flask
from pymongo import MongoClient
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ======================================
# USER FILLED VALUES
# ======================================
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

# ======================================
# ENV VARIABLES (Render)
# ======================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_URI = os.getenv("MONGO_DB_URI")

# ======================================
# MONGO
# ======================================
mongo = MongoClient(MONGO_URI)
db = mongo["sweetheart_db"]
files_db = db["files"]

# ======================================
# FLASK SERVER REQUIRED BY RENDER
# ======================================
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Sweetheart Bot Active — Telegram Bot Running Successfully!"

# ======================================
# PYROGRAM BOT
# ======================================
bot = Client(
    "sweetheart_romantic_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# ======================================
# ROMANTIC AUTO REPLY
# ======================================
romantic_lines = [
    "Janu ❤️", "Baby 😘", "Sweetheart 💕", "Miss you jaan 💋",
    "Come close to me 😍", "Love you baby ❤️"
]

# ======================================
# TYPING EFFECT
# ======================================
async def typing_effect(msg, text):
    await msg.reply_chat_action("typing")
    await asyncio.sleep(0.7)
    await msg.reply_text(text)

# ======================================
# START CMD
# ======================================
@bot.on_message(filters.command("start"))
async def start_cmd(_, m):
    await typing_effect(m, "Hello Sweetheart ❤️ I am here for you 😘")
    await m.reply(
        "Choose an option love 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Me", url=f"https://t.me/{MY_USERNAME}")],
            [InlineKeyboardButton("❤️ Help", callback_data="help")]
        ])
    )

# ======================================
# HELP
# ======================================
@bot.on_callback_query(filters.regex("help"))
async def cb_help(_, q):
    await q.message.edit(
        "**❤️ Sweetheart Bot Commands**\n\n"
        "/start – Start bot\n"
        "/help – Help menu\n"
        "/broadcast – Send message to everyone\n"
        "/status – Bot status\n"
        "/settings – Settings menu\n\n"
        "💕 Send any keyword → I will find similar files for you!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Developer", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

# direct /help
@bot.on_message(filters.command("help"))
async def help_cmd(c, m):
    await cb_help(c, m)

# ======================================
# SAVE FILES automatically
# ======================================
@bot.on_message(filters.document | filters.photo | filters.video)
async def save_file(_, m):
    try:
        file_id = (
            m.document.file_id if m.document else
            m.photo.file_id if m.photo else
            m.video.file_id
        )
        caption = (m.caption or "").lower()

        files_db.insert_one({"file_id": file_id, "caption": caption})
        await typing_effect(m, "Saved Sweetheart ❤️")
    except:
        pass

# ======================================
# SEARCH SYSTEM — partial 2-word matching
# ======================================
def similar(q, caption):
    q_words = q.lower().split()
    c_words = caption.lower().split()
    return sum(1 for w in q_words if w in c_words) >= 2

@bot.on_message(filters.text & ~filters.command(["start", "help"]))
async def search(_, m):
    query = m.text.lower()
    results = list(files_db.find({}))

    matched = []
    for r in results:
        if similar(query, r["caption"]):
            matched.append(r)

    if not matched:
        return await typing_effect(m, "🌸 No Results Found — Try again Sweetheart 💕")

    for f in matched[:20]:
        try:
            await bot.send_cached_media(
                chat_id=m.chat.id,
                file_id=f["file_id"],
                caption="Here Baby ❤️"
            )
        except:
            pass

# ======================================
# BROADCAST
# ======================================
@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def bc(_, m):
    text = m.text.replace("/broadcast ", "")
    await bot.send_message(LOGS_CHANNEL, f"Broadcast: {text}")
    await m.reply("Broadcast sent ❤️")

# ======================================
# STATUS
# ======================================
@bot.on_message(filters.command("status"))
async def status(_, m):
    await m.reply("Bot is active Sweetheart ❤️")

# ======================================
# SETTINGS
# ======================================
@bot.on_message(filters.command("settings"))
async def settings(_, m):
    await m.reply(
        "Settings Menu ❤️",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Dev", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

# ======================================
# RUN BOTH (FLASK + BOT)
# ======================================
async def main():
    await bot.start()
    print("Bot started ❤️")
    await idle()

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))).start()
    asyncio.run(main())
