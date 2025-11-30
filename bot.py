import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
import random

# ===========================
#  FIXED IDs (YOUR VALUES)
# ===========================
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# ===========================
#   ENV VALUES
# ===========================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# ---------------------------
#  FLASK SERVER FOR RENDER
# ---------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Romantic Telegram Bot Running Successfully on Render! ❤️"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ----------------------------
#      PYROGRAM CLIENT
# ----------------------------
bot = Client(
    "romantic_gf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ----------------------------
#  Romantic Responses
# ----------------------------
ROMANTIC_LINES = [
    "Haan baby bolo 😘",
    "Janu main hoon na ❤️",
    "Suno sweetheart 💋",
    "Aapki GF yaha hai baby 😘",
    "Janeman tum bologe aur main sunungi ❤️",
    "Tumhare message ka wait rehta hai jaan 💕",
]

# ----------------------------
#       HANDLERS
# ----------------------------

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text(
        "Hi Baby 😘\nMain tumhari Romantic GF bot hoon ❤️\nBoloo na Sweetheart 💋"
    )

    try:
        await bot.send_message(
            LOGS_CHANNEL,
            f"🔥 User Started: {message.from_user.id}"
        )
    except:
        pass


@bot.on_message(filters.private & filters.text & ~filters.command(["start"]))
async def romantic_reply(_, message: Message):
    await message.reply_text(random.choice(ROMANTIC_LINES))


@bot.on_inline_query()
async def inline_mode(_, query: InlineQuery):
    text = query.query.strip()

    if len(text) < 3:
        return

    await query.answer(
        results=[
            InlineQueryResultArticle(
                title="Send ❤️",
                description=f"Message: {text}",
                input_message_content=InputTextMessageContent(
                    f"❤️ Your Search: {text}"
                )
            )
        ],
        cache_time=0
    )

# ----------------------------
#        MAIN START
# ----------------------------
if __name__ == "__main__":
    # Flask in background
    Thread(target=run_flask).start()

    # Pyrogram MUST run in MAIN THREAD
    bot.run()
