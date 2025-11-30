# bot.py — Render web-service ready, Pyrogram (async) + optional motor + OpenAI
import os
import asyncio
import logging
from functools import partial
from flask import Flask
import requests
import random
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG (fill in Render env) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
MONGO_URL = os.getenv("MONGO_URL")  # optional
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional
PORT = int(os.getenv("PORT", "10000"))

# Owner / logs (fixed as requested)
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

# ---------------- Flask keep-alive (so Render detects open port) ----------------
app = Flask("serena_keepalive")

@app.route("/")
def index():
    return "💗 Serena Bot — service is running"

def _run_flask():
    # Bind to PORT so Render shows open port
    app.run(host="0.0.0.0", port=PORT)

# ---------------- Database setup (async motor) or in-memory fallback ----------------
if MONGO_URL:
    try:
        mongo = AsyncIOMotorClient(MONGO_URL)
        db = mongo.get_database("serena_bot_db")
        users_col = db.get_collection("users")      # {user_id, premium, banned, mode}
        files_col = db.get_collection("files")      # {file_id, file_type, name, source_chat, date}
        config_col = db.get_collection("config")
        logging.info("MongoDB connected.")
    except Exception:
        logging.exception("MongoDB connection failed, switching to memory.")
        users_col = None
        files_col = None
        config_col = None
else:
    users_col = None
    files_col = None
    config_col = None
    logging.info("MongoDB not configured — running with in-memory fallback.")

# In-memory fallbacks
IN_MEMORY_USERS = {}   # user_id -> {"premium":bool,"banned":bool,"mode":"gf"/"search"}
IN_MEMORY_FILES = []   # list of {"file_id","file_type","name","source_chat","date"}

# ---------------- Pyrogram client ----------------
bot = Client(
    "serena_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ---------------- Helpers ----------------
ROMANTIC_FALLBACKS = [
    "Jaanu, bolo na… 😘",
    "Haan baby, main yahi hoon ❤️",
    "Sweetheart, tumhari baatein acchi lagti hain 💕"
]

def romantic_fallback():
    return random.choice(ROMANTIC_FALLBACKS)

async def ensure_user_doc(user_id: int):
    """Ensure a user doc exists (DB) or seed in-memory"""
    if users_col is not None:
        await users_col.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"user_id": user_id, "premium": False, "banned": False, "mode": "gf"}},
            upsert=True
        )
    else:
        IN_MEMORY_USERS.setdefault(user_id, {"premium": False, "banned": False, "mode": "gf"})

async def set_user_mode(user_id: int, mode: str):
    if users_col is not None:
        await users_col.update_one({"user_id": user_id}, {"$set": {"mode": mode}}, upsert=True)
    else:
        u = IN_MEMORY_USERS.setdefault(user_id, {"premium": False, "banned": False, "mode": "gf"})
        u["mode"] = mode

async def get_user_doc(user_id: int):
    if users_col is not None:
        doc = await users_col.find_one({"user_id": user_id})
        if not doc:
            await ensure_user_doc(user_id)
            doc = await users_col.find_one({"user_id": user_id})
        return doc
    else:
        return IN_MEMORY_USERS.setdefault(user_id, {"premium": False, "banned": False, "mode": "gf"})

async def send_log(text: str):
    try:
        await bot.send_message(LOGS_CHANNEL, text)
    except Exception:
        logging.debug("Failed to send log to logs channel.")

# OpenAI (sync requests) executed in executor
def openai_sync(text: str) -> str:
    if not OPENAI_API_KEY:
        return romantic_fallback()
    try:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a romantic girlfriend. Reply sweetly and playfully."},
                {"role": "user", "content": text}
            ],
            "temperature": 0.9,
            "max_tokens": 300
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            timeout=20
        )
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]
    except Exception:
        logging.exception("OpenAI request failed")
        return romantic_fallback()

async def ask_openai(text: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(openai_sync, text))

# File search helpers
def normalize_words(s: str):
    return [w.strip() for w in s.lower().split() if w.strip()]

def match_minimum(query: str, name: str, min_matches: int = 3) -> bool:
    q = normalize_words(query)
    n = name.lower()
    if len(q) < min_matches:
        return any(w in n for w in q)
    return sum(1 for w in q if w in n) >= min_matches

async def search_files(query: str, min_matches: int = 3, limit: int = 20):
    out = []
    if files_col is not None:
        async for doc in files_col.find({}):
            name = doc.get("name","")
            if match_minimum(query, name, min_matches=min_matches):
                out.append(doc)
                if len(out) >= limit:
                    break
    else:
        for doc in IN_MEMORY_FILES:
            if match_minimum(query, doc.get("name",""), min_matches=min_matches):
                out.append(doc)
                if len(out) >= limit:
                    break
    return out

# ---------------- Command Handlers ----------------

@bot.on_message(filters.private & filters.command("start"))
async def cmd_start(_, m: Message):
    await ensure_user_doc(m.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Chat (GF)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
         InlineKeyboardButton("👑 Owner", url=f"https://t.me/{MY_USERNAME}")]
    ])
    await m.reply_text(
        f"🌹 Hi {m.from_user.first_name}! Choose a mode below — GF Chat or File Search.",
        reply_markup=kb
    )
    await send_log(f"🟢 /start by {m.from_user.id}")

@bot.on_message(filters.private & filters.command("help"))
async def cmd_help(_, m: Message):
    text = (
        "✨ *How to use this bot*\n\n"
        "1. /start -> Settings -> choose GF Chat or File Search.\n"
        "2. In File Search, send a descriptive file name (3+ words recommended).\n\n"
        "Commands:\n"
        "/start, /help, /alive\n"
        "Owner only: /addpremium <id>, /rempremium <id>, /ban <id>, /unban <id>, /broadcast <text>, /clear, /status\n\n"
        f"Owner: @{MY_USERNAME}"
    )
    await m.reply_text(text)

@bot.on_message(filters.private & filters.command("alive"))
async def cmd_alive(_, m: Message):
    await m.reply_text("💗 I'm online and ready.")

# Owner-only commands
@bot.on_message(filters.private & filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /addpremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
    else:
        IN_MEMORY_USERS.setdefault(uid, {"premium": True, "banned": False, "mode": "gf"})["premium"] = True
    await m.reply_text(f"✅ {uid} added to premium")
    await send_log(f"Owner added premium: {uid}")

@bot.on_message(filters.private & filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /rempremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": False}})
    else:
        IN_MEMORY_USERS.setdefault(uid, {"premium": False, "banned": False, "mode": "gf"})["premium"] = False
    await m.reply_text(f"✅ {uid} removed from premium")
    await send_log(f"Owner removed premium: {uid}")

@bot.on_message(filters.private & filters.command("ban") & filters.user(OWNER_ID))
async def cmd_ban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /ban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
    else:
        IN_MEMORY_USERS.setdefault(uid, {"premium": False, "banned": True, "mode": "gf"})["banned"] = True
    await m.reply_text(f"⛔ {uid} banned")
    await send_log(f"Owner banned: {uid}")

@bot.on_message(filters.private & filters.command("unban") & filters.user(OWNER_ID))
async def cmd_unban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /unban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": False}}, upsert=True)
    else:
        IN_MEMORY_USERS.setdefault(uid, {"premium": False, "banned": False, "mode": "gf"})["banned"] = False
    await m.reply_text(f"✅ {uid} unbanned")
    await send_log(f"Owner unbanned: {uid}")

@bot.on_message(filters.private & filters.command("broadcast") & filters.user(OWNER_ID))
async def cmd_broadcast(_, m: Message):
    parts = m.text.split(" ", 1)
    if len(parts) < 2:
        return await m.reply_text("Usage: /broadcast <text>")
    text = parts[1]
    count = 0
    if users_col is not None:
        async for u in users_col.find({}, {"user_id": 1}):
            try:
                await bot.send_message(u["user_id"], text)
                count += 1
            except:
                pass
    else:
        for uid in IN_MEMORY_USERS.keys():
            try:
                await bot.send_message(uid, text)
                count += 1
            except:
                pass
    await m.reply_text(f"Broadcast sent to {count} users")
    await send_log(f"Broadcast by owner to {count} users")

@bot.on_message(filters.private & filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, m: Message):
    if users_col is not None:
        await users_col.delete_many({})
    if files_col is not None:
        await files_col.delete_many({})
    IN_MEMORY_USERS.clear()
    IN_MEMORY_FILES.clear()
    await m.reply_text("✅ DB cleared")
    await send_log("DB cleared by owner")

@bot.on_message(filters.private & filters.command("status") & filters.user(OWNER_ID))
async def cmd_status(_, m: Message):
    await m.reply_text("✅ Bot is running (status OK)")
    await send_log("Status requested by owner")

# ---------------- Settings panel and mode switching ----------------
@bot.on_callback_query(filters.regex("^open_settings$"))
async def cb_open_settings(_, q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 GF Chat (OpenAI)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("📨 My Mode", callback_data="my_mode")]
    ])
    await q.message.edit_text("⚙️ Settings — choose mode:", reply_markup=kb)
    await q.answer()

@bot.on_callback_query(filters.regex("^mode:"))
async def cb_mode(_, q):
    mode = q.data.split(":", 1)[1]
    await set_user_mode(q.from_user.id, mode)
    await q.answer(f"Mode set to {mode}", show_alert=False)
    await q.message.edit_text(f"✅ Mode set to: {mode}")

@bot.on_callback_query(filters.regex("^my_mode$"))
async def cb_my_mode(_, q):
    u = await get_user_doc(q.from_user.id)
    await q.answer(f"Your mode: {u.get('mode','gf')}", show_alert=True)

# ---------------- Channel indexing (save files) ----------------
@bot.on_message(filters.channel)
async def channel_index(_, m: Message):
    try:
        if m.document:
            doc = {"file_id": m.document.file_id, "file_type": "document", "name": (m.document.file_name or m.caption or "").strip(), "source_chat": m.chat.id, "date": m.date}
        elif m.video:
            doc = {"file_id": m.video.file_id, "file_type": "video", "name": (m.video.file_name or m.caption or "").strip(), "source_chat": m.chat.id, "date": m.date}
        elif m.photo:
            file_id = None
            if m.photo:
                # pyrogram photo is a list: take last size
                try:
                    file_id = m.photo.file_id
                except Exception:
                    file_id = None
            doc = {"file_id": file_id, "file_type": "photo", "name": (m.caption or "").strip(), "source_chat": m.chat.id, "date": m.date}
        else:
            return
        # save to DB or memory
        if files_col is not None:
            await files_col.insert_one({"file_id": doc["file_id"], "file_type": doc["file_type"], "name": doc["name"].lower(), "source_chat": doc["source_chat"], "date": doc["date"]})
        else:
            IN_MEMORY_FILES.append({"file_id": doc["file_id"], "file_type": doc["file_type"], "name": doc["name"].lower(), "source_chat": doc["source_chat"], "date": doc["date"]})
        try:
            await bot.send_message(LOGS_CHANNEL, f"📦 Saved file from {m.chat.id}: {doc['name']}")
        except:
            pass
    except Exception:
        logging.exception("channel_index error")

# ---------------- Main private text handler (no empty filters.command use) ----------------
@bot.on_message(filters.private & filters.text)
async def private_message_handler(_, m: Message):
    uid = m.from_user.id
    text = (m.text or "").strip()
    await ensure_user_doc(uid)
    user = await get_user_doc(uid)

    if user.get("banned"):
        return await m.reply_text("🚫 You are banned.")

    mode = user.get("mode", "gf") if users_col is not None else IN_MEMORY_USERS.get(uid, {"mode":"gf"})["mode"]

    await send_log(f"User {uid}: {text}")

    if mode == "search":
        words = normalize_words(text)
        if not words:
            return await m.reply_text("🔎 Send some keywords to search (3+ words recommended).")
        # search DB or memory
        matches = await search_files(text, min_matches=3, limit=10)
        if not matches:
            return await m.reply_text("🌸 No matching files found — try different keywords.")
        sent = 0
        for d in matches[:6]:
            fid = d.get("file_id")
            try:
                if d.get("file_type") == "document":
                    await bot.send_document(uid, fid)
                elif d.get("file_type") == "video":
                    await bot.send_video(uid, fid)
                elif d.get("file_type") == "photo":
                    await bot.send_photo(uid, fid)
                else:
                    await bot.send_message(uid, f"📁 {d.get('name')}")
                sent += 1
            except Exception:
                pass
        await m.reply_text(f"Sent {sent} items.")
        return

    # GF chat
    if OPENAI_API_KEY:
        reply = await ask_openai(text)
    else:
        reply = romantic_fallback()
    await m.reply_text(reply)

# ---------------- Startup: run Flask in executor and start bot in main loop ----------------
async def start_services():
    loop = asyncio.get_running_loop()
    # run flask so Render sees open port
    loop.run_in_executor(None, _run_flask)
    logging.info("Flask started on port %s", PORT)

    # start pyrogram
    await bot.start()
    logging.info("🔥 Pyrogram started")

    # warm config doc
    if config_col is not None:
        await config_col.update_one({"_id":"meta"}, {"$setOnInsert": {"created": True}}, upsert=True)

    # keep running forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except Exception:
        logging.exception("Fatal startup error")
