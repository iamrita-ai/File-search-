import os
import asyncio
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, idle
from pymongo import MongoClient
import random

# ---------------- ENV ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
PORT = int(os.getenv("PORT", 10000))

OWNER_ID = 1598576202

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ BOT IS RUNNING ON RENDER (PYROGRAM POLLING ACTIVE)"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ---------------- MONGO ----------------
try:
    mongo = MongoClient(MONGO_URL)
    db = mongo["RomanticBot"]
    users = db["users"]
    premium = db["premium"]
    settings = db["settings"]
except:
    print("❌ MongoDB Connection Failed")

# ---------------- BOT ----------------
bot = Client(
    "RomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
    in_memory=True
)

# ---------------- TEXTS ----------------
HELP_TEXT = """
💖 **Sweetheart Commands** 💖

❤️ `/start` – Romantic Welcome  
✨ `/help` – How to use me  
⚡ `/status` – Bot Status  
🗑 `/cleardb` – Clear MongoDB  
🔍 Just send any text → Romantic reply  

Made with love by @technicalserena 💋
"""

ROMANTIC_LINES = [
    "Jaanu batao na, kya chahiye tumhe ❤️",
    "Haan meri Sweetheart, sun rahi hoon 💋",
    "Aap bolte raho baby… mujhe acha lagta hai 😘",
    "Dil se sun rahi hoon Janu ❤️",
]

def romantic():
    return random.choice(ROMANTIC_LINES)

# ---------------- HANDLERS ----------------

@bot.on_message(filters.private & filters.command(["start"]))
async def start_cmd(c, m):
    await m.reply_text(f"❤️ Hello {m.from_user.first_name}!\n\n{romantic()}")


@bot.on_message(filters.private & filters.command(["help"]))
async def help_cmd(c, m):
    await m.reply_text(HELP_TEXT)


@bot.on_message(filters.private & filters.command(["status"]))
async def status_cmd(c, m):
    await m.reply_text("💖 Bot Active Hai Baby\n⚡ Speed: Fast\n❤️ Love Mode: ON")


@bot.on_message(filters.private & filters.command(["cleardb"]))
async def clear_db(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply_text("Only Owner Allowed ❌")
    users.drop()
    premium.drop()
    settings.drop()
    await m.reply_text("🗑 MongoDB Cleared Sweetheart ❤️")


# ⭐ FINAL FIX — No filters.command bug
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "help", "status", "cleardb"]))
async def romantic_reply(c, m):
    text = m.text.lower()
    match = users.find_one({"text": {"$regex": text}})
    if match:
        await m.reply_document(match["file"])
        return
    await m.reply_text(romantic())


# ---------------- MAIN LOOP ----------------
async def main():
    Thread(target=run_flask).start()
    await bot.start()
    print("🔥 BOT STARTED & POLLING ACTIVE")
    await idle()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
