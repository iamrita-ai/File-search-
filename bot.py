import os
import threading
import asyncio
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ----------------- ENV -----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"


# ----------------- FLASK -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Romantic Telegram Bot Is Running Successfully!"


# ----------------- BOT CLIENT -----------------
bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ----------------- BOT COMMANDS -----------------
@bot.on_message(filters.command("start"))
async def start_cmd(_, m):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💖 Owner", url=f"https://t.me/{MY_USERNAME}")]
    ])
    await m.reply_text(
        f"Hello *{m.from_user.first_name}* ❤️\n"
        "Main Online ho Sweetheart 💋\n"
        "Aaj kya help chahiye meri jaan? 😘",
        reply_markup=btn
    )


@bot.on_message(filters.command("help"))
async def help_cmd(_, m):
    await m.reply_text("💞 Sweetheart, Ye Help Menu Hai.\nSab Kuch Perfectly Working Hai 💋")


@bot.on_message(filters.command("status"))
async def status_cmd(_, m):
    await m.reply_text("💘 Jaan, Bot Bilkul Theek Chal Raha Hai!")


# ----------------- RUN BOT WITH ASYNC LOOP -----------------
def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot.run()


# ----------------- MAIN ENTRY -----------------
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)
