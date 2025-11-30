# bot.py — Render web-service friendly, motor (async) mongo, OpenAI (optional)
import os
import asyncio
import requests
from functools import partial
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.filters import create
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import random

logging.basicConfig(level=logging.INFO)

# -------------------------
# CONFIG / ENV
# -------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")  # required for DB features
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional
PORT = int(os.getenv("PORT", "10000"))

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# -------------------------
# FLASK (keep-alive for Render)
# -------------------------
app = Flask("romantic_bot")

@app.route("/")
def index():
    return "❤️ Romantic Bot — alive"

def run_flask():
    # run with default dev server — that's fine for Render keep-alive
    app.run(host="0.0.0.0", port=PORT)

# -------------------------
# MONGO (motor async)
# -------------------------
if not MONGO_URL:
    logging.warning("MONGO_URL not set — DB features disabled.")
    mongo = None
    db = None
else:
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo["romantic_bot_db"]

# collections (may be None)
users_col = db["users"] if db is not None else None       # {user_id, premium, banned, mode}
files_col = db["files"] if db is not None else None       # {file_id, file_type, name, source_chat, date}
config_col = db["config"] if db is not None else None

# -------------------------
# PYROGRAM CLIENT
# -------------------------
bot = Client(
    "romantic_gf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# -------------------------
# utility: non-command filter (Pyrogram v2 safe)
# -------------------------
def non_command_filter(_, __, msg: Message):
    return not (msg.text and msg.text.startswith("/"))
non_command = create(non_command_filter)

# -------------------------
# small helpers
# -------------------------
ROMANTIC_LINES = [
    "Jaanu bolo na 😘",
    "Haan baby, main yahin hoon ❤️",
    "Tumhari baatein dil choo jati hain 💖",
    "Sweetheart, tumne kya socha aaj? 😍"
]

def romantic_fallback(text: str) -> str:
    return random.choice(ROMANTIC_LINES)

async def ensure_user(user_id: int):
    if users_col is None:
        return
    await users_col.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {"user_id": user_id, "premium": False, "banned": False, "mode":"gf"}},
        upsert=True
    )

async def set_user_mode(user_id: int, mode: str):
    if users_col is None:
        return
    await users_col.update_one({"user_id": user_id}, {"$set": {"mode": mode}}, upsert=True)

async def get_user_doc(user_id: int):
    if users_col is None:
        return {"user_id": user_id, "premium": False, "banned": False, "mode": "gf"}
    doc = await users_col.find_one({"user_id": user_id})
    if not doc:
        await ensure_user(user_id)
        doc = await users_col.find_one({"user_id": user_id})
    return doc

async def send_log(text: str):
    try:
        await bot.send_message(LOGS_CHANNEL, text)
    except Exception as e:
        logging.warning("log send failed: %s", e)

# -------------------------
# OpenAI helper (sync) -> we'll run in executor to avoid blocking
# -------------------------
def openai_sync_call(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return romantic_fallback(prompt)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role":"system", "content": "You are a romantic girlfriend. Reply sweetly and playfully (Hindi/English mix ok)."},
            {"role":"user", "content": prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 350
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"]

async def ask_openai(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, partial(openai_sync_call, prompt))
    except Exception as e:
        logging.exception("OpenAI call failed")
        return romantic_fallback(prompt)

# -------------------------
# File search helpers
# -------------------------
def normalize_words(s: str):
    return [w.strip() for w in s.lower().split() if w.strip()]

def match_minimum(query: str, name: str, min_matches:int=3) -> bool:
    q = normalize_words(query)
    if len(q) < min_matches:
        # if user gave fewer than required words, require at least 1 match
        matches = sum(1 for w in q if w in name.lower())
        return matches >= 1
    matches = sum(1 for w in q if w in name.lower())
    return matches >= min_matches

async def search_files_db(query: str, min_matches:int=3, limit:int=20):
    if files_col is None:
        return []
    out = []
    async for doc in files_col.find({}):
        name = doc.get("name","").lower()
        if match_minimum(query, name, min_matches=min_matches):
            out.append(doc)
            if len(out) >= limit:
                break
    return out

# -------------------------
# Handlers
# -------------------------

# /start
@bot.on_message(filters.private & filters.command("start"))
async def cmd_start(_, m: Message):
    await ensure_user(m.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Chat Mode", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
         InlineKeyboardButton("👑 Owner", url=f"https://t.me/technicalserena")]
    ])
    await m.reply_text(f"Hi {m.from_user.first_name} ❤️\nMain tumhari virtual GF hoon. Choose a mode below or /help.", reply_markup=kb)
    await send_log(f"🟢 /start — {m.from_user.id}")

# /help
@bot.on_message(filters.private & filters.command("help"))
async def cmd_help(_, m: Message):
    text = (
        "💖 Commands:\n"
        "/start - Start\n"
        "/help - This message\n"
        "/settings - Mode & options\n"
        "/alive - Check bot\n\n"
        "Owner only:\n"
        "/addpremium <user_id>\n"
        "/rempremium <user_id>\n"
        "/ban <user_id>\n"
        "/unban <user_id>\n"
        "/broadcast <text>\n"
        "/clear - clear DB\n"
    )
    await m.reply_text(text)

# /alive
@bot.on_message(filters.private & filters.command("alive"))
async def cmd_alive(_, m: Message):
    await m.reply_text("❤️ I'm online and listening!")

# settings button open
@bot.on_callback_query(filters.regex("open_settings"))
async def cb_open_settings(_, q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 GF Chat (OpenAI)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("🗑 Clear my data", callback_data="clear_me")]
    ])
    await q.message.edit("Settings — choose:", reply_markup=kb)
    await q.answer()

# mode switches
@bot.on_callback_query(filters.regex("^mode:"))
async def cb_mode(_, q):
    user = q.from_user.id
    payload = q.data.split(":",1)[1]
    await set_user_mode(user, "gf" if payload=="gf" else "search")
    await q.answer(f"Mode set to {payload}", show_alert=False)

# simpler mode handlers for the start keyboard
@bot.on_callback_query(filters.regex("mode:gf"))
async def cb_mode_gf(_, q): 
    await set_user_mode(q.from_user.id, "gf"); await q.answer("GF Chat mode set")

@bot.on_callback_query(filters.regex("mode:search"))
async def cb_mode_search(_, q):
    await set_user_mode(q.from_user.id, "search"); await q.answer("File Search mode set")

# Owner actions
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /addpremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
    await m.reply_text(f"✅ {uid} -> premium")
    await send_log(f"Owner added premium: {uid}")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /rempremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} removed from premium")
    await send_log(f"Owner removed premium: {uid}")

@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def cmd_ban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /ban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
    await m.reply_text(f"⛔ {uid} banned")
    await send_log(f"Owner banned: {uid}")

@bot.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def cmd_unban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /unban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} unbanned")
    await send_log(f"Owner unbanned: {uid}")

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def cmd_broadcast(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured")
    parts = m.text.split(" ",1)
    if len(parts) < 2:
        return await m.reply_text("Usage: /broadcast <text>")
    text = parts[1]
    await m.reply_text("Starting broadcast...")
    count = 0
    async for u in users_col.find({}, {"user_id":1}):
        try:
            await bot.send_message(u["user_id"], text)
            count += 1
        except:
            pass
    await m.reply_text(f"Broadcast done to {count} users")
    await send_log(f"Broadcast by owner, sent to {count}")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, m: Message):
    if users_col is not None:
        await users_col.delete_many({})
    if files_col is not None:
        await files_col.delete_many({})
    await m.reply_text("✅ DB cleared")
    await send_log("DB cleared by owner")

# -------------------------
# Channel indexing: save incoming files (documents, videos, photos)
# -------------------------
@bot.on_message(filters.channel)
async def channel_index(_, m: Message):
    try:
        if files_col is None:
            return
        # detect type and name
        fid = None
        fname = ""
        ftype = ""
        if m.document:
            ftype = "document"; fid = m.document.file_id; fname = m.document.file_name or (m.caption or "")
        elif m.video:
            ftype = "video"; fid = m.video.file_id; fname = m.video.file_name or (m.caption or "")
        elif m.photo:
            ftype = "photo"; fid = m.photo.file_id if hasattr(m.photo, "file_id") else None; fname = m.caption or ""
        else:
            return
        await files_col.insert_one({
            "file_id": fid,
            "file_type": ftype,
            "name": (fname or "").strip(),
            "source_chat": m.chat.id,
            "date": m.date
        })
        try:
            await bot.send_message(LOGS_CHANNEL, f"Saved file from {m.chat.id}: {fname}")
        except:
            pass
    except Exception:
        logging.exception("channel_index error")

# -------------------------
# Non-command private handler (main logic)
# -------------------------
@bot.on_message(filters.private & filters.text & non_command)
async def private_handler(_, m: Message):
    uid = m.from_user.id
    await ensure_user(uid)
    udoc = await get_user_doc(uid)
    if udoc.get("banned"):
        return await m.reply_text("🚫 You are banned.")
    mode = udoc.get("mode","gf")

    text = m.text.strip()
    await send_log(f"User {uid}: {text}")

    if mode == "search":
        if len(normalize_words(text)) < 3:
            return await m.reply_text("🔎 Please send at least 3 words for search.")
        matches = await search_files_db(text, min_matches=3, limit=10)
        if not matches:
            return await m.reply_text("🌸 No Results — try different keywords.")
        sent = 0
        for doc in matches:
            fid = doc.get("file_id")
            try:
                # pick sending method based on type
                if doc.get("file_type") == "document":
                    await bot.send_document(uid, fid)
                elif doc.get("file_type") == "video":
                    await bot.send_video(uid, fid)
                elif doc.get("file_type") == "photo":
                    await bot.send_photo(uid, fid)
                else:
                    await bot.send_message(uid, f"📁 {doc.get('name')}")
                sent += 1
            except Exception:
                pass
        await m.reply_text(f"Sent {sent} items.")
        return

    # gf chat mode
    if OPENAI_API_KEY:
        reply = await ask_openai(text)
    else:
        reply = romantic_fallback(text)

    await m.reply_text(reply)

# -------------------------
# Inline query support (file: or chat:)
# -------------------------
@bot.on_inline_query()
async def inline_query_handler(_, iq: InlineQuery):
    q = (iq.query or "").strip()
    if not q:
        return await iq.answer([], cache_time=0)

    if q.lower().startswith("file:"):
        query = q.split("file:",1)[1].strip()
        if len(normalize_words(query)) < 3:
            return await iq.answer([], switch_pm_text="Send 3+ words to search", switch_pm_parameter="need3")
        matches = await search_files_db(query, min_matches=3, limit=15)
        results = []
        for d in matches:
            title = (d.get("name") or "file")[:64]
            results.append(
                InlineQueryResultArticle(
                    id=str(d.get("_id")),
                    title=title,
                    input_message_content=InputTextMessageContent(f"📁 {title}\nFrom channel {d.get('source_chat')}")
                )
            )
        return await iq.answer(results, cache_time=0)

    if q.lower().startswith("chat:"):
        prompt = q.split("chat:",1)[1].strip()
        if not prompt:
            return await iq.answer([], switch_pm_text="Type message after chat:", switch_pm_parameter="needtext")
        res = await ask_openai(prompt) if OPENAI_API_KEY else romantic_fallback(prompt)
        art = InlineQueryResultArticle(
            id="gpt1",
            title="GF Reply",
            input_message_content=InputTextMessageContent(res)
        )
        return await iq.answer([art], cache_time=0)

    await iq.answer([], cache_time=0)

# -------------------------
# Start services (async)
# -------------------------
async def start_services():
    # start flask in executor so port is bound (Render detection)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_flask)
    logging.info("Flask started on port %s", PORT)

    # start pyrogram
    await bot.start()
    logging.info("🔥 Bot started")

    # ensure some indexes or config if needed
    if config_col is not None:
        await config_col.update_one({"_id":"meta"}, {"$setOnInsert":{"created":True}}, upsert=True)

    # keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except Exception:
        logging.exception("Fatal")
