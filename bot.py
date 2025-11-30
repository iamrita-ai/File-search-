import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
import random

# ========================================================
# FIXED VALUES (Tumne diye hain)
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
# ========================================================

# ================= ENVIRONMENT VARIABLES ================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))   # Render Web Service Fix
# ========================================================


# ---------------- FLASK SERVER FOR RENDER ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Romantic Telegram Bot Running Successfully! ❤️"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)
# ----------------------------------------------------------


# ------------------- PYROGRAM BOT ------------------------
bot = Client(
    "romantic_gf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)
# ----------------------------------------------------------


# ============= Romantic Replies List ======================
ROMANTIC_LINES = [
    "Janu bolo na 😘",
    "Haan baby, sun rahi hoon ❤️",
    "Bolo Sweetheart 💋",
    "Haan meri jaan 😍",
    "Tumhari baaton ka intezaar rehta hai baby 😘",
    "Janeman kya kar rahi ho tum? ❤️",
    "Aapka message dil ko sukoon deta hai baby 💞",
]
# ==========================================================


# ---------------- START COMMAND ---------------------------
@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(_, message: Message):

    await message.reply_text(
        f"Hi Baby 😘\n"
        f"Main tumhari Romantic GF bot hoon ❤️\n"
        f"Boloo na Sweetheart 💋"
    )

    # Logs channel me notification
    try:
        await bot.send_message(LOGS_CHANNEL, f"🔥 New User Started: {message.from_user.id}")
    except:
        pass

# ----------------------------------------------------------


# ------------------ NORMAL CHAT REPLY ---------------------
@bot.on_message(filters.private & filters.text & ~filters.command(["start"]))
async def gf_reply(_, message: Message):
    reply = random.choice(ROMANTIC_LINES)
    await message.reply_text(reply)
# ----------------------------------------------------------


# ================= INLINE MODE (3 letter min) =============
@bot.on_inline_query()
async def inline_search(_, query: InlineQuery):

    text = query.query.strip()

    if len(text) < 3:
        return  # inline query minimum 3 words

    result = InlineQueryResultArticle(
        title=f"Send to Yourself ❤️",
        description=f"Message: {text}",
        input_message_content=InputTextMessageContent(
            f"❤️ *Your Search Result:* {text}",
            parse_mode="markdown"
        )
    )

    await query.answer([result], cache_time=0)
# -----------------------------------------------------------


# ================= BOT START FUNCTION =====================
def start_bot():
    print("🔥 Bot Launched Successfully!")
    bot.run()
# -----------------------------------------------------------


# ======================== MAIN ============================
if __name__ == "__main__":
    Thread(target=run_flask).start()    # Render ko port mil jayega
    Thread(target=start_bot).start()    # Pyrogram bot
# ===========================================================
