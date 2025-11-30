import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message

# =========== ENV VARIABLES ===========
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = int(os.getenv("OWNER_ID"))          # your id
LOGS_CHANNEL = int(os.getenv("LOGS_CHANNEL"))  # your logs channel id

PORT = int(os.getenv("PORT", "10000"))         # FIXED
# ======================================


# ---------- FLASK SERVER (Render Ke Liye) ----------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is Running Successfully! 🔥"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)
# ---------------------------------------------------


# ---------- PYROGRAM BOT CLIENT ----------
bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)
# ---------------------------------------------------


# ========== HANDLERS ==========

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(_, message: Message):
    await message.reply(
        f"Hi Baby 😘\n"
        f"Main online hoon… tumhare liye ❤️\n"
        f"/help bhi try kro Sweetheart 💋"
    )

    # logging to channel
    try:
        await bot.send_message(LOGS_CHANNEL, f"New User Started: {message.from_user.id}")
    except:
        pass


@bot.on_message(filters.private & filters.text)
async def romantic_reply(_, message: Message):
    text = message.text.lower()

    # romantic style
    replies = [
        "Janu bolooo 😘",
        "Haan Sweetheart ❤️",
        "Bolo na Baby 💋",
        "Janeman batao na 😍",
        "Tumhari baatein sunke acha lgta hai ❤️"
    ]

    await message.reply(replies[0])


# ========== BOT START FUNCTION (NO DEADLOCK) ==========
def start_bot():
    print("🔥 Bot is starting…")
    bot.run()   # keeps running properly inside thread
# ======================================================


# ========== MAIN STARTUP ==========
if __name__ == "__main__":
    # Start Flask (no blocking)
    Thread(target=run_flask).start()

    # Start Bot (no blocking, no await issues)
    Thread(target=start_bot).start()
