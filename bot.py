import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle
from pymongo import MongoClient

# ---------- ENV ----------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
PORT = int(os.getenv("PORT", 10000))

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

# ---------- FLASK ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ BOT IS RUNNING ON RENDER"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ---------- MONGO ----------
db = None
users = None
premium = None
settings = None

try:
    mongo = MongoClient(MONGO_URL)
    db = mongo["RomanticBot"]
    users = db["users"]
    premium = db["premium"]
    settings = db["settings"]
except:
    print("❌ MongoDB Connection Failed")

# ---------- BOT ----------
bot = Client(
    "RomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------- HELP MESSAGE ----------
HELP_TEXT = """
💖 **Sweetheart Commands** 💖

❤️ `/start` – Romantic Welcome  
✨ `/help` – How to use me  
👑 `/addpremium <id>` – Add user  
💔 `/rempremium <id>` – Remove user  
⚡ `/status` – Bot Status  
🗑 `/cleardb` – Clear MongoDB  
⚙️ `/setting` – Manage settings  
🔍 Just send text → File Search  

Made with love by @technicalserena 💋
"""

# ------------ Romantic Replies ------------
ROMANTIC_LINES = [
    "Jaanu batao na, kya chahiye tumhe ❤️",
    "Haan meri *Sweetheart*, sun rahi hoon 💋",
    "Aap bolte raho baby… mujhe acha lagta hai 😘",
    "Dil se sun rahi hoon janu ❤️",
]

import random

def romantic():
    return random.choice(ROMANTIC_LINES)

# ------------ Handlers ------------

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text(
        f"❤️ Hello {m.from_user.first_name}!\n\n"
        f"Main tumhari Romantic Assistant hoon, {romantic()}",
        reply_markup=None
    )

@bot.on_message(filters.private & filters.command("help"))
async def help_cmd(c, m):
    await m.reply_text(HELP_TEXT)

@bot.on_message(filters.private & filters.command("status"))
async def status_cmd(c, m):
    await m.reply_text("💖 Bot is Active\n⚡ Speed: Fast\n❤️ Love Mode: ON")

@bot.on_message(filters.private & filters.command("cleardb"))
async def clear_db(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply_text("Only Owner Allowed ❌")
    users.drop()
    premium.drop()
    settings.drop()
    await m.reply_text("🗑 MongoDB Cleared Sweetheart ❤️")

@bot.on_message(filters.private & filters.text & ~filters.command(["start","help","status","cleardb"]))
async def romantic_reply(c, m):
    text = m.text.lower()
    match = users.find_one({"text": {"$regex": text}})
    if match:
        await m.reply_document(match["file"])
        return

    await m.reply_text(romantic())

# ---------- MAIN LOOP ----------
async def main():
    Thread(target=run_flask).start()
    await bot.start()
    print("BOT STARTED ❤️")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
