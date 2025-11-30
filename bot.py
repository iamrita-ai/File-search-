import os
import threading
from flask import Flask
from pyrogram import Client, filters, enums
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
    return "❤️ Romantic Telegram Bot Active"

# ----------------- BOT -----------------
bot = Client(
    "romantic_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# --------------- START -------------------
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


# -------------- HELP ---------------------
@bot.on_message(filters.command("help"))
async def help_cmd(_, m):
    await m.reply_text("❤️ Help Menu Working Successfully")


# -------------- STATUS -------------------
@bot.on_message(filters.command("status"))
async def status_cmd(_, m):
    await m.reply_text("💘 Bot Responding Successfully!")


# -------------- RUN BOT -------------------
def run_bot():
    bot.run()

# -------------- START THREAD -------------
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)
