# bot.py — Render web service friendly, async motor Mongo, optional OpenAI GF chat + file search + premium/ban
import os
import asyncio
import logging
from functools import partial
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.filters import create
from motor.motor_asyncio import AsyncIOMotorClient
import requests
import random

logging.basicConfig(level=logging.INFO)

# ========== CONFIG ==========
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URL = os.getenv("MONGO_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
PORT = int(os.getenv("PORT", "10000"))

# Replace these with your values (you already gave them)
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# ========== FLASK (keep-alive for Render) ==========
app = Flask("serena_bot")

@app.route("/")
def index():
    return "❤️ Serena Bot — running"

def _run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ========== MONGO (motor async) ==========
if not MONGO_URL:
    logging.warning("MONGO_URL not provided — DB features disabled.")
    mongo = None
    db = None
else:
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo["serena_bot_db"]

users_col = db["users"] if db is not None else None    # {user_id, premium, banned, mode}
files_col = db["files"] if db is not None else None    # {file_id, file_type, name, source_chat, date}
config_col = db["config"] if db is not None else None

# ========== PYROGRAM CLIENT ==========
bot = Client("serena_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# ========== utility: non-command filter (Pyrogram v2 safe) ==========
def non_command_filter(_, __, msg: Message):
    return not (msg.text and msg.text.startswith("/"))
non_command = create(non_command_filter)

# ========== small helpers ==========
ROMANTIC_FALLBACKS = [
    "Jaanu, bolo na… 😘",
    "Haan baby, main sun rahi hoon ❤️",
    "Aawww, tum kya keh rahe ho sweetheart? 💕",
    "Meri jaan, tumhare messages se dil khil uthta hai 😍"
]

def romantic_fallback(text: str) -> str:
    return random.choice(ROMANTIC_FALLBACKS)

async def ensure_user_doc(user_id: int):
    if users_col is None:
        return
    await users_col.update_one({"user_id": user_id}, {"$setOnInsert": {"user_id": user_id, "premium": False, "banned": False, "mode": "gf"}}, upsert=True)

async def set_mode(user_id: int, mode: str):
    if users_col is None:
        return
    await users_col.update_one({"user_id": user_id}, {"$set": {"mode": mode}}, upsert=True)

async def get_user(user_id: int):
    if users_col is None:
        return {"user_id": user_id, "premium": False, "banned": False, "mode": "gf"}
    doc = await users_col.find_one({"user_id": user_id})
    if not doc:
        await ensure_user_doc(user_id)
        doc = await users_col.find_one({"user_id": user_id})
    return doc

async def send_log(text: str):
    try:
        await bot.send_message(LOGS_CHANNEL, text)
    except Exception:
        logging.exception("Failed to send log")

# ========== OpenAI helper (sync) => run in executor to avoid blocking ==========
def openai_sync_call(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return romantic_fallback(prompt)
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role":"system","content":"You are a romantic girlfriend. Reply sweetly and playfully, use words like Jaan, Baby, Sweetheart."},
                    {"role":"user","content":prompt}
                ],
                "max_tokens":300,
                "temperature":0.9
            },
            timeout=20
        )
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        logging.exception("OpenAI error")
        return romantic_fallback(prompt)

async def ask_openai(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(openai_sync_call, prompt))

# ========== File search helpers ==========
def normalize_words(s: str):
    return [w for w in s.lower().split() if w]

def match_minimum(query: str, name: str, min_matches:int=3) -> bool:
    q = normalize_words(query)
    n = name.lower()
    if len(q) < min_matches:
        # if user provided fewer words allow 1-word match
        return any(w in n for w in q)
    return sum(1 for w in q if w in n) >= min_matches

async def search_files(query: str, min_matches:int=3, limit:int=20):
    if files_col is None:
        return []
    out = []
    async for doc in files_col.find({}):
        name = doc.get("name","").lower()
        if match_minimum(query, name, min_matches):
            out.append(doc)
            if len(out) >= limit:
                break
    return out

# ========== Handlers ==========

# /start — new welcome (no old "test" text)
@bot.on_message(filters.private & filters.command("start"))
async def cmd_start(_, m: Message):
    await ensure_user_doc(m.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Chat (GF)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
         InlineKeyboardButton("👑 Owner", url="https://t.me/technicalserena")]
    ])
    text = (
        f"🌹 Hi {m.from_user.first_name} — main tumhari Serena hoon!\n\n"
        "Choose a mode: Chat with GF (AI) or File Search. Use /settings to change.\n"
        "Type in the chat after choosing a mode."
    )
    await m.reply_text(text, reply_markup=kb)
    await send_log(f"🟢 /start by {m.from_user.id}")

# /help
@bot.on_message(filters.private & filters.command("help"))
async def cmd_help(_, m: Message):
    txt = (
        "💝 Commands:\n"
        "/start - Start\n"
        "/help - This message\n"
        "/settings - Mode selection\n"
        "/alive - Bot status\n\n"
        "Owner only: /addpremium /rempremium /ban /unban /broadcast /clear\n"
    )
    await m.reply_text(txt)

# /alive
@bot.on_message(filters.private & filters.command("alive"))
async def cmd_alive(_, m: Message):
    await m.reply_text("💗 I'm online and listening for you!")

# Settings panel
@bot.on_callback_query(filters.regex("^open_settings"))
async def cb_settings(_, q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 GF Chat (AI)", callback_data="mode:gf"),
         InlineKeyboardButton("🔎 File Search", callback_data="mode:search")],
        [InlineKeyboardButton("🧾 My Mode", callback_data="my_mode")]
    ])
    await q.message.edit("⚙️ Settings — choose a mode:", reply_markup=kb)
    await q.answer()

# set mode callback
@bot.on_callback_query(filters.regex("^mode:"))
async def cb_mode(_, q):
    user = q.from_user.id
    mode = q.data.split(":",1)[1]
    await set_mode(user, "gf" if mode=="gf" else "search")
    await q.answer(f"Mode set to {mode}", show_alert=False)

@bot.on_callback_query(filters.regex("^my_mode"))
async def cb_my_mode(_, q):
    u = await get_user(q.from_user.id)
    await q.answer(f"Your mode: {u.get('mode','gf')}", show_alert=True)

# Owner commands: addpremium, rempremium, ban, unban, broadcast, clear
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /addpremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
    await m.reply_text(f"✅ {uid} added to premium")
    await send_log(f"🔹 Owner added premium: {uid}")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /rempremium <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"premium": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} removed from premium")
    await send_log(f"🔹 Owner removed premium: {uid}")

@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def cmd_ban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /ban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
    await m.reply_text(f"⛔ {uid} banned")
    await send_log(f"⛔ Owner banned: {uid}")

@bot.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def cmd_unban(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply_text("Usage: /unban <user_id>")
    uid = int(parts[1])
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} unbanned")
    await send_log(f"✅ Owner unbanned: {uid}")

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def cmd_broadcast(_, m: Message):
    parts = m.text.split(" ",1)
    if len(parts) < 2:
        return await m.reply_text("Usage: /broadcast <message>")
    text = parts[1]
    if users_col is None:
        return await m.reply_text("DB not configured")
    count = 0
    async for u in users_col.find({}, {"user_id":1}):
        try:
            await bot.send_message(u["user_id"], text)
            count += 1
        except:
            pass
    await m.reply_text(f"Broadcast sent to {count}")
    await send_log(f"📣 Broadcast by owner to {count} users")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, m: Message):
    if users_col is not None:
        await users_col.delete_many({})
    if files_col is not None:
        await files_col.delete_many({})
    await m.reply_text("✅ DB cleared")
    await send_log("🗑️ DB cleared by owner")

# Channel indexing (store files)
@bot.on_message(filters.channel)
async def channel_index(_, m: Message):
    try:
        if files_col is None:
            return
        fid = None; fname = ""; ftype = ""
        if m.document:
            ftype = "document"; fid = m.document.file_id; fname = m.document.file_name or (m.caption or "")
        elif m.video:
            ftype = "video"; fid = m.video.file_id; fname = m.video.file_name or (m.caption or "")
        elif m.photo:
            ftype = "photo"; fid = m.photo.file_id if hasattr(m.photo, "file_id") else None; fname = m.caption or ""
        else:
            return
        await files_col.insert_one({"file_id": fid, "file_type": ftype, "name": (fname or "").strip(), "source_chat": m.chat.id, "date": m.date})
        try:
            await bot.send_message(LOGS_CHANNEL, f"Saved file from {m.chat.id}: {fname}")
        except:
            pass
    except Exception:
        logging.exception("channel_index error")

# Non-command private handler — main logic (GF chat or File search)
@bot.on_message(filters.private & filters.text & non_command)
async def private_handler(_, m: Message):
    uid = m.from_user.id
    await ensure_user_doc(uid)
    user = await get_user(uid)
    if user.get("banned"):
        return await m.reply_text("🚫 You are banned.")
    mode = user.get("mode","gf")
    text = m.text.strip()
    await send_log(f"👤 {uid}: {text}")

    if mode == "search":
        if len(normalize_words(text)) < 3:
            return await m.reply_text("🔎 Send at least 3 words for file search.")
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

    # GF chat mode
    if OPENAI_API_KEY:
        reply = await ask_openai(text)
    else:
        reply = romantic_fallback(text)
    await m.reply_text(reply)

# Inline support for quick search/chat
@bot.on_inline_query()
async def inline_handler(_, iq: InlineQuery):
    q = (iq.query or "").strip()
    if not q:
        return await iq.answer([], cache_time=0)

    if q.lower().startswith("file:"):
        query = q.split("file:",1)[1].strip()
        if len(normalize_words(query)) < 3:
            return await iq.answer([], switch_pm_text="Send 3+ words to search", switch_pm_parameter="need3")
        matches = await search_files(query, min_matches=3, limit=15)
        results = []
        for d in matches:
            title = (d.get("name") or "file")[:64]
            results.append(InlineQueryResultArticle(id=str(d.get("_id")), title=title, input_message_content=InputTextMessageContent(f"📁 {title}\nFrom channel {d.get('source_chat')}")))
        return await iq.answer(results, cache_time=0)

    if q.lower().startswith("chat:"):
        prompt = q.split("chat:",1)[1].strip()
        if not prompt:
            return await iq.answer([], switch_pm_text="Type message after chat:", switch_pm_parameter="needtext")
        res = await ask_openai(prompt) if OPENAI_API_KEY else romantic_fallback(prompt)
        art = InlineQueryResultArticle(id="g1", title="GF Reply", input_message_content=InputTextMessageContent(res))
        return await iq.answer([art], cache_time=0)

    return await iq.answer([], cache_time=0)

# ========== start services ==========
async def start_services():
    # run flask in executor so render sees an open port
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_flask)
    logging.info("Flask started on port %s", PORT)

    # start bot (pyrogram) — main loop
    await bot.start()
    logging.info("🔥 Pyrogram started")

    # ensure meta
    if config_col is not None:
        await config_col.update_one({"_id":"meta"}, {"$setOnInsert":{"created":True}}, upsert=True)

    # keep alive forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except Exception:
        logging.exception("Fatal error on startup")
