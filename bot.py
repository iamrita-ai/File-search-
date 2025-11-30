# bot.py — Minimal, robust, Render web-service friendly, Pyrogram main loop safe
import os
import asyncio
import logging
from functools import partial
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.filters import create
import requests
import random

logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional
PORT = int(os.getenv("PORT", "10000"))

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# --------------- FLASK keep-alive ---------------
app = Flask("keepalive")

@app.route("/")
def home():
    return "❤️ Bot is alive"

def run_flask():
    # binds port (Render will detect)
    app.run(host="0.0.0.0", port=PORT)

# --------------- Pyrogram client ---------------
bot = Client(
    "serena_minimal",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

# --------------- safe non-command filter ---------------
def non_command_filter(_, __, msg: Message):
    return not (msg.text and msg.text.startswith("/"))
non_command = create(non_command_filter)

# --------------- in-memory stores (avoid DB issues) ---------------
IN_MEMORY_MODES = {}       # user_id -> "gf" or "search"
FILES_STORE = []           # list of {"file_id":..., "type":"document/video/photo", "name": "..."}

# --------------- helpers ---------------
ROMANTIC_FALLBACKS = [
    "Jaanu, bolo na… 😘",
    "Haan baby, main sun rahi hoon ❤️",
    "Sweetheart, batao kya chahiye? 💕"
]

def romantic_fallback(_):
    return random.choice(ROMANTIC_FALLBACKS)

def normalize_words(s: str):
    return [w for w in s.lower().split() if w]

def match_minimum(query: str, name: str, min_matches: int = 3) -> bool:
    q = normalize_words(query)
    n = name.lower()
    if len(q) < min_matches:
        # if user sent <3 words, allow any single-word match
        return any(w in n for w in q)
    return sum(1 for w in q if w in n) >= min_matches

async def call_openai(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return romantic_fallback(prompt)
    try:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role":"system", "content":"You are a romantic girlfriend. Reply sweetly and playfully."},
                {"role":"user", "content": prompt}
            ],
            "temperature": 0.9,
            "max_tokens": 300
        }
        resp = await asyncio.get_running_loop().run_in_executor(None, partial(requests.post,
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"},
            timeout=20
        ))
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"]
    except Exception:
        return romantic_fallback(prompt)

async def send_log(text: str):
    try:
        await bot.send_message(LOGS_CHANNEL, text)
    except Exception:
        # ignore logging failure
        pass

# --------------- commands & handlers ---------------

@bot.on_message(filters.private & filters.command("start"))
async def cmd_start(_, m: Message):
    IN_MEMORY_MODES[m.from_user.id] = "gf"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Chat (GF)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
         InlineKeyboardButton("👑 Owner", url="https://t.me/technicalserena")]
    ])
    await m.reply_text(
        f"🌹 Hi {m.from_user.first_name}! Mode set to *GF Chat* by default.\nType after choosing a mode or use the buttons.",
        reply_markup=kb
    )
    await send_log(f"/start by {m.from_user.id}")

@bot.on_message(filters.private & filters.command("help"))
async def cmd_help(_, m: Message):
    await m.reply_text(
        "Commands:\n"
        "/start - Start\n"
        "/help - This message\n\n"
        "Use Settings -> choose Chat or File Search.\n"
        "For File Search send >=3 words for best results."
    )

@bot.on_callback_query(filters.regex("^open_settings$"))
async def cb_open_settings(_, q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 GF Chat", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("❓ Current Mode", callback_data="my_mode")]
    ])
    await q.message.edit("Choose a mode:", reply_markup=kb)
    await q.answer()

@bot.on_callback_query(filters.regex("^mode:"))
async def cb_mode(_, q):
    mode = q.data.split(":",1)[1]
    IN_MEMORY_MODES[q.from_user.id] = mode
    await q.answer(f"Mode set to {mode}")
    await q.message.edit_text(f"✅ Mode set to *{mode}*")

@bot.on_callback_query(filters.regex("^my_mode$"))
async def cb_my_mode(_, q):
    mode = IN_MEMORY_MODES.get(q.from_user.id, "gf")
    await q.answer(f"Your mode: {mode}", show_alert=True)

# channel file indexing (in-memory)
@bot.on_message(filters.channel)
async def channel_index(_, m: Message):
    try:
        if m.document:
            FILES_STORE.append({"file_id": m.document.file_id, "type":"document", "name": (m.document.file_name or m.caption or "").strip().lower()})
        elif m.video:
            FILES_STORE.append({"file_id": m.video.file_id, "type":"video", "name": (m.video.file_name or m.caption or "").strip().lower()})
        elif m.photo:
            # photos: use caption
            FILES_STORE.append({"file_id": m.photo.file_id if hasattr(m.photo, "file_id") else None, "type":"photo", "name": (m.caption or "").strip().lower()})
        # log minimal
        await send_log(f"Indexed file from channel {m.chat.id}")
    except Exception:
        pass

# main private non-command handler
@bot.on_message(filters.private & filters.text & non_command)
async def private_text(_, m: Message):
    uid = m.from_user.id
    mode = IN_MEMORY_MODES.get(uid, "gf")
    text = m.text.strip()
    await send_log(f"{uid}: {text}")

    if mode == "search":
        # require at least 3 words for best results, but allow shorter queries too
        if len(normalize_words(text)) < 1:
            return await m.reply_text("🔎 Send some keywords (3+ words recommended).")
        matches = [f for f in FILES_STORE if match_minimum(text, f.get("name",""))]
        if not matches:
            return await m.reply_text("🌸 No Results Found — try different keywords.")
        sent = 0
        for d in matches[:6]:
            try:
                if d["type"] == "document":
                    await bot.send_document(uid, d["file_id"])
                elif d["type"] == "video":
                    await bot.send_video(uid, d["file_id"])
                elif d["type"] == "photo":
                    await bot.send_photo(uid, d["file_id"])
                else:
                    await bot.send_message(uid, f"📁 {d.get('name')}")
                sent += 1
            except Exception:
                pass
        await m.reply_text(f"Sent {sent} items.")
        return

    # GF chat mode (OpenAI if key present)
    if OPENAI_API_KEY:
        reply = await call_openai(text)
    else:
        reply = romantic_fallback(text)
    await m.reply_text(reply)

# ------------------- startup: Flask in executor + Pyrogram in main loop -------------------
async def start_services():
    loop = asyncio.get_running_loop()
    # start flask so Render detects open port
    loop.run_in_executor(None, run_flask)
    logging.info("Flask started on port %s", PORT)

    # start pyrogram
    await bot.start()
    logging.info("🔥 Pyrogram started")

    # keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except Exception as e:
        logging.exception("startup failed")
