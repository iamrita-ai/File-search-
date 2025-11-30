import os
import asyncio
import logging
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import requests
import random

logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional
PORT = int(os.getenv("PORT", "10000"))

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# ---------------- FLASK KEEP ALIVE ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Bot is running successfully!"

def start_flask():
    app.run(host="0.0.0.0", port=PORT)

# ---------------- PYROGRAM BOT ----------------
bot = Client(
    "SerenaBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# memory stores
MODES = {}  # user_id -> gf/search
FILES = []  # stored files

# ---------------- HELPERS ----------------

ROMANTIC_LINES = [
    "Haan baby 😘 bolo na ❤️",
    "Jaanu main yahin hoon 💋",
    "Sweetheart, batao na 😍"
]

def romantic():
    return random.choice(ROMANTIC_LINES)

async def ask_gpt(text):
    if not OPENAI_API_KEY:
        return romantic()
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "Act like a romantic girlfriend."},
                    {"role": "user", "content": text}
                ]
            },
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
        )
        j = r.json()
        return j["choices"][0]["message"]["content"]
    except:
        return romantic()

def split_words(t):
    return [w for w in t.lower().split() if w]

def match(q, name):
    q = split_words(q)
    name = name.lower()
    return sum(w in name for w in q) >= 2

# ---------------- COMMAND HANDLERS ----------------

@bot.on_message(filters.private & filters.command("start"))
async def start(_, m):
    MODES[m.from_user.id] = "gf"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 GF Chat", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("⚙ Settings", callback_data="settings")]
    ])

    await m.reply_text(
        "🌹 Hello baby! Mode: *GF Chat*\nChoose from below:",
        reply_markup=kb
    )

@bot.on_callback_query(filters.regex("^mode:"))
async def mode_change(_, q):
    mode = q.data.split(":")[1]
    MODES[q.from_user.id] = mode
    await q.answer(f"Mode changed to {mode}")
    await q.message.edit(f"Mode changed to: *{mode}*")

# ---------------- CHANNEL INDEXING ----------------

@bot.on_message(filters.channel)
async def index(_, m: Message):
    try:
        if m.document:
            FILES.append({"id": m.document.file_id, "name": m.document.file_name.lower(), "type": "document"})
        elif m.video:
            FILES.append({"id": m.video.file_id, "name": m.video.file_name.lower(), "type": "video"})
        elif m.photo:
            FILES.append({"id": m.photo.file_id, "name": m.caption.lower() if m.caption else "", "type": "photo"})
    except:
        pass

# ---------------- MAIN TEXT HANDLER ----------------

@bot.on_message(filters.private & filters.text & ~filters.command())
async def chat(_, m: Message):
    uid = m.from_user.id
    text = m.text

    mode = MODES.get(uid, "gf")

    if mode == "search":
        words = split_words(text)
        if len(words) < 2:
            return await m.reply("🔍 Send at least 2 keywords!")

        results = [f for f in FILES if match(text, f["name"])]
        if not results:
            return await m.reply("😢 No results found.")

        for f in results[:8]:
            if f["type"] == "document":
                await bot.send_document(uid, f["id"])
            elif f["type"] == "video":
                await bot.send_video(uid, f["id"])
            else:
                await bot.send_photo(uid, f["id"])

        return

    # GF MODE (OpenAI)
    reply = await ask_gpt(text)
    await m.reply_text(reply)

# ---------------- START BOT + FLASK ----------------

async def main():
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, start_flask)

    await bot.start()
    logging.info("🔥 BOT STARTED SUCCESSFULLY!")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
