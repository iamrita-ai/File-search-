import os
import random
from flask import Flask, request
from pyrogram import Client, filters
from pyrogram.types import Update
from pymongo import MongoClient

# ---------------- ENV ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

OWNER_ID = 1598576202
WEBHOOK_HOST = "https://file-search-ejnk.onrender.com"
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "💖 BOT IS LIVE (WEBHOOK MODE)"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_receiver():
    update = Update.de_json(request.get_json(), bot)
    bot.process_update(update)
    return "OK", 200

# ---------------- MONGO ----------------
try:
    mongo = MongoClient(MONGO_URL)
    db = mongo["RomanticBot"]
    users = db["users"]
    premium = db["premium"]
    settings = db["settings"]
    print("Mongo Connected")
except:
    print("❌ MongoDB Failed")

# ---------------- BOT ----------------
bot = Client(
    "RomanticWebhookBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Romantic lines
ROMANTIC_LINES = [
    "Janu kya kar rahi ho? ❤️",
    "Haan meri Sweetheart 💋",
    "Bolo baby, sun rahi hoon 😘",
    "Dil se sun rahi hoon meri jaan ❤️",
]

def romantic():
    return random.choice(ROMANTIC_LINES)

HELP_TEXT = """
💖 Commands 💖

❤️ /start – Romantic Welcome  
✨ /help – Commands  
⚡ /status – Bot Status  
🗑 /cleardb – Clear DB  

Made by @technicalserena 💋
"""

# ---------------- Handlers ----------------

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text(f"Hello {m.from_user.first_name} ❤️\n{romantic()}")

@bot.on_message(filters.private & filters.command("help"))
async def help_cmd(c, m):
    await m.reply_text(HELP_TEXT)

@bot.on_message(filters.private & filters.command("status"))
async def status_cmd(c, m):
    await m.reply_text("Bot Active ❤️ (Webhook Mode)")

@bot.on_message(filters.private & filters.command("cleardb"))
async def clear_db(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply_text("Only Owner Allowed ❌")
    users.drop()
    premium.drop()
    settings.drop()
    await m.reply_text("DB Cleared ❤️")

@bot.on_message(filters.private & filters.text)
async def romantic_reply(c, m):
    await m.reply_text(romantic())

# ---------------- MAIN START ----------------
if __name__ == "__main__":
    print("Starting bot in webhook mode...")

    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    print("Webhook Set:", WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
