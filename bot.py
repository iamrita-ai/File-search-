import os
from flask import Flask
from pyrogram import Client, filters
from pymongo import MongoClient
import asyncio
import requests

# =====================
# ENV VARIABLES (Render)
# =====================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
GPT_KEY = os.environ.get("GPT_KEY")

# ================
# MongoDB Connect
# ================
mongo = MongoClient(MONGO_URL)
db = mongo["MAIN_DB"]
users = db["users"]

# =============
# Flask Web App
# =============
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Babe your bot is alive on Render Web Service!"

# =====================
# Pyrogram Telegram Bot
# =====================
bot = Client(
    "love-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# =============
# ChatGPT Reply
# =============
def gpt_reply(text):
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {GPT_KEY}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are romantic girlfriend bot replying with love vibes."},
                    {"role": "user", "content": text}
                ]
            }
        ).json()
        return r["choices"][0]["message"]["content"]
    except:
        return "Baby… mujhe thodi der do, main thodii si shy ho gayi hu 😳💗"

# ===========================
# START COMMAND (Romantic)
# ===========================
@bot.on_message(filters.command("start"))
async def start_cmd(c, m):
    users.update_one({"id": m.from_user.id}, {"$set": {"id": m.from_user.id}}, upsert=True)
    await m.reply_text(
        f"Hello {m.from_user.first_name} Janu 💗\n\n"
        f"Main tumhari cute romantic chatbot hoon 😘"
    )

# ===========================
# Normal Chat (Romantic GPT)
# ===========================
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "help"]))
async def chat_gpt_reply(c, m):
    reply = gpt_reply(m.text)
    await m.reply_text(reply)

# =====================
# HELP COMMAND
# =====================
@bot.on_message(filters.command("help"))
async def help_cmd(c, m):
    await m.reply_text(
        "❤️ *Bot Commands* ❤️\n\n"
        "/start - Romantic welcome\n"
        "/help - Commands\n"
        "/status - Bot speed, ping\n"
        "/addpremium - Add user to premium\n"
        "/rempremium - Remove user\n"
        "/clear - Clear MongoDB\n"
        "/settings - Owner settings\n",
        quote=True
    )

# =====================
# PREVENT THREAD BUG
# =====================
# We DO NOT use bot.run()
# We DO NOT use threading
# We DO NOT use separate event loops
# Render web service only calls THIS:
async def start_all():
    print("💗 Starting Telegram bot & Flask server...")

    # Start Pyrogram in background
    await bot.start()
    print("Bot started on Telegram.")

    # Keep it alive forever
    while True:
        await asyncio.sleep(100)

# ============
# ENTRY POINT
# ============
if __name__ == "__main__":
    # Start Flask (port required for Render Web Service)
    port = int(os.environ.get("PORT", 10000))

    # Run Flask on a separate thread-safe server
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()

    # Run bot (async-safe)
    asyncio.run(start_all())
