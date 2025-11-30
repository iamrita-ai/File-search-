# bot.py — Render web-service ready, MongoDB, premium/ban, ChatGPT GF, file search, settings
import os
import asyncio
import traceback
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from motor.motor_asyncio import AsyncIOMotorClient
import random
from typing import Dict, Any

# ----------------------------
# CONFIG (edit if you want hard-coded)
# ----------------------------
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")   # required
OPENAI_KEY = os.getenv("OPENAI_API_KEY")  # optional
PORT = int(os.getenv("PORT", "10000"))

# ----------------------------
# Flask keep-alive (Render)
# ----------------------------
app = Flask("romantic_bot")

@app.route("/")
def index():
    return "❤️ Romantic Bot (Render) — alive"

# ----------------------------
# Mongo (motor async)
# ----------------------------
if not MONGO_URL:
    print("WARNING: MONGO_URL not set. DB features disabled.")
    mongo = None
    db = None
else:
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo["romantic_bot_db"]

users_col = db["users"] if db is not None else None   # stores {user_id, premium:bool, banned:bool}
files_col = db["files"] if db is not None else None   # stores {file_id, file_type, name, source_chat, date}
config_col = db["config"] if db is not None else None # optional config

# ----------------------------
# Pyrogram client
# ----------------------------
bot = Client(
    "romantic_gf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----------------------------
# small helpers
# ----------------------------
ROMANTIC_LINES = [
    "Janu boloo 😘",
    "Haan baby, sun rahi hoon ❤️",
    "Bolo Sweetheart 💋",
    "Meri jaan, tumhe dekh ke khushi hoti hai 😍",
    "Tumhari baaton se dil khil uthta hai 💞"
]

def romantic_fallback(text: str) -> str:
    return random.choice(ROMANTIC_LINES)

def log_exc(tag="ERR"):
    traceback.print_exc()
    print(tag)

async def ensure_user_doc(user_id: int):
    if users_col is None:
        return
    await users_col.update_one({"user_id": user_id}, {"$setOnInsert": {"user_id": user_id, "premium": False, "banned": False}}, upsert=True)

async def send_log(text: str):
    try:
        await bot.send_message(LOGS_CHANNEL, text)
    except Exception:
        # don't crash on logging failure
        print("Failed to send log to LOGS_CHANNEL")

# ----------------------------
# OpenAI helper (ChatGPT)
# ----------------------------
def gpt_reply_sync(prompt: str) -> str:
    """Synchronous helper to call OpenAI (used via run_in_executor)."""
    if not OPENAI_KEY:
        return romantic_fallback(prompt)
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role":"system","content":"You are a romantic girlfriend. Speak kindly, playfully, in Hindi/English with words like Jaan, Baby, Sweetheart."},
                    {"role":"user","content":prompt}
                ],
                "max_tokens": 300,
                "temperature": 0.9
            },
            timeout=20
        )
        j = resp.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        print("OpenAI error:", e)
        return romantic_fallback(prompt)

async def gpt_reply(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, gpt_reply_sync, prompt)

# ----------------------------
# File search helper (simple word-match)
# - requires files_col to be populated by channel message handler
# ----------------------------
def normalize_words(s: str):
    return [w for w in s.lower().split() if w]

def match_minimum(query: str, name: str, min_matches:int=3) -> bool:
    q = normalize_words(query)
    n = name.lower()
    if len(q) < min_matches:
        # require at least min_matches words in query; if user provided fewer, allow matching by any word
        # but we will enforce search command to send >=3 words
        pass
    matches = sum(1 for w in q if w in n)
    return matches >= min_matches

async def search_files_by_query(query: str, min_matches:int=3, limit:int=20):
    if files_col is None:
        return []
    res = []
    async for doc in files_col.find({}):
        name = doc.get("name","").lower()
        if match_minimum(query, name, min_matches=min_matches):
            res.append(doc)
            if len(res) >= limit:
                break
    return res

# ----------------------------
# Commands & Handlers
# ----------------------------

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(_, m: Message):
    await ensure_user_doc(m.from_user.id)
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")],
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/technicalserena")]
    ])
    text = f"🥰 Hi {m.from_user.first_name} — I'm your romantic assistant.\n\nChoose /help to see commands."
    await m.reply_text(text, reply_markup=buttons)
    await send_log(f"🟢 /start by `{m.from_user.id}`")

@bot.on_message(filters.command("help") & filters.private)
async def cmd_help(_, m: Message):
    text = (
        "💖 *Commands*\n\n"
        "/start - Start\n"
        "/help - This message\n"
        "/settings - Choose GF Chat or File Search\n"
        "/alive - Bot status\n\n"
        "Owner only:\n"
        "/addpremium <user_id>\n"
        "/rempremium <user_id>\n"
        "/ban <user_id>\n"
        "/unban <user_id>\n"
        "/broadcast <text>\n"
        "/clear - Clear DB\n"
    )
    await m.reply_text(text)

@bot.on_message(filters.command("alive") & filters.private)
async def cmd_alive(_, m: Message):
    await m.reply_text("💗 I'm alive and listening ❤️")

# ------------- OWNER ACTIONS -------------
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured.")
    parts = m.text.split()
    if len(parts) < 2: return await m.reply_text("Usage: /addpremium <user_id>")
    uid = int(parts[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
    await m.reply_text(f"✅ {uid} is now premium.")
    await send_log(f"🔹 Owner added premium: {uid}")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured.")
    parts = m.text.split()
    if len(parts) < 2: return await m.reply_text("Usage: /rempremium <user_id>")
    uid = int(parts[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"premium": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} removed from premium.")
    await send_log(f"🔹 Owner removed premium: {uid}")

@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def cmd_ban(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured.")
    parts = m.text.split()
    if len(parts) < 2: return await m.reply_text("Usage: /ban <user_id>")
    uid = int(parts[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
    await m.reply_text(f"🚫 {uid} banned.")
    await send_log(f"⛔ Owner banned {uid}")

@bot.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def cmd_unban(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured.")
    parts = m.text.split()
    if len(parts) < 2: return await m.reply_text("Usage: /unban <user_id>")
    uid = int(parts[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"banned": False}}, upsert=True)
    await m.reply_text(f"✅ {uid} unbanned.")
    await send_log(f"✅ Owner unbanned {uid}")

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def cmd_broadcast(_, m: Message):
    if users_col is None:
        return await m.reply_text("DB not configured.")
    text = m.text.split(" ",1)
    if len(text) < 2:
        return await m.reply_text("Usage: /broadcast <message>")
    msg = text[1]
    await m.reply_text("Broadcast starting...")
    count = 0
    async for u in users_col.find({}, {"user_id":1}):
        uid = u["user_id"]
        try:
            await bot.send_message(uid, msg)
            count += 1
        except Exception:
            pass
    await m.reply_text(f"Broadcast sent to {count} users.")
    await send_log(f"📣 Broadcast by owner: sent to {count}")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, m: Message):
    if users_col is not None: await users_col.delete_many({})
    if files_col is not None: await files_col.delete_many({})
    if config_col is not None: await config_col.delete_many({})
    await m.reply_text("✅ All DB collections cleared.")
    await send_log("🗑️ DB cleared by owner")

# ----------------------------
# Settings panel & mode selection
# ----------------------------
@bot.on_message(filters.command("settings") & filters.private)
async def cmd_settings(_, m: Message):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ GF Chat Mode", callback_data="mode:gf")],
        [InlineKeyboardButton("🔎 File Search Mode", callback_data="mode:search")],
    ])
    await m.reply_text("Select mode — Chat or File Search", reply_markup=kb)

@bot.on_callback_query()
async def cb_mode(_, q):
    try:
        user = q.from_user.id
        data = q.data or ""
        if data.startswith("mode:"):
            mode = data.split(":",1)[1]
            # store in DB config per user
            if users_col is not None:
                await users_col.update_one({"user_id": user}, {"$set": {"mode": mode}}, upsert=True)
            else:
                # fallback to in-memory if DB missing
                pass
            await q.answer(f"Mode set to {mode}", show_alert=False)
            await q.message.reply_text(f"✅ Mode set to *{mode}*")
        else:
            await q.answer()
    except Exception:
        log_exc("cb_mode")

# ----------------------------
# Channel message indexing (save files posted in source channels)
# - Owner can add source channels via DB if needed (not implemented UI here)
# ----------------------------
@bot.on_message(filters.channel)
async def channel_index(_, m: Message):
    # store documents/videos/audios/photos with name/caption
    try:
        if files_col is None: return
        doc = None
        name = ""
        ftype = ""
        fid = None
        if m.document:
            doc = m.document
            ftype = "document"
            fid = doc.file_id
            name = doc.file_name or (m.caption or "")
        elif m.video:
            doc = m.video
            ftype = "video"
            fid = doc.file_id
            name = doc.file_name or (m.caption or "")
        elif m.photo:
            # photos have no file_name; use caption as name
            ftype = "photo"
            fid = m.photo.file_id if isinstance(m.photo, list) else m.photo.file_id
            name = m.caption or ""
        else:
            return

        await files_col.insert_one({
            "file_id": fid,
            "file_type": ftype,
            "name": (name or "").lower(),
            "source_chat": m.chat.id,
            "date": m.date
        })
        # also log to LOGS_CHANNEL
        try:
            await bot.send_message(LOGS_CHANNEL, f"📥 Saved file from channel `{m.chat.id}`: `{name}`")
        except:
            pass
    except Exception:
        log_exc("channel_index")

# ----------------------------
# Private search & chat handler
# ----------------------------
@bot.on_message(filters.private & filters.text & ~filters.command())
async def private_message_handler(_, m: Message):
    uid = m.from_user.id
    # ensure user doc
    if users_col is not None:
        user_doc = await users_col.find_one({"user_id": uid})
        if not user_doc:
            await users_col.insert_one({"user_id": uid, "premium": False, "banned": False, "mode":"gf"})
            user_doc = await users_col.find_one({"user_id": uid})
    else:
        user_doc = {"premium": False, "banned": False, "mode":"gf"}

    # banned check
    if user_doc.get("banned"):
        return await m.reply_text("🚫 You are banned.")

    # mode: prefer DB value, else default "gf"
    mode = user_doc.get("mode","gf")

    text = m.text.strip()
    await send_log(f"✉️ {uid}: {text}")

    # MODE LOGIC
    if mode == "search":
        # require min 3 words
        if len(normalize_words(text)) < 3:
            return await m.reply_text("🔎 Please send at least 3 words for file search.")
        matches = await search_files_by_query(text, min_matches=3, limit=20)
        if not matches:
            return await m.reply_text("🌸 No matching files found — try different keywords.")
        # reply with top 5 results (send file_id if available)
        sent = 0
        for d in matches[:6]:
            try:
                fid = d.get("file_id")
                if fid:
                    # send original file type as appropriate
                    try:
                        await bot.send_document(uid, fid)
                    except:
                        # fallback send as document
                        await bot.send_message(uid, f"📁 {d.get('name')}")
                else:
                    await bot.send_message(uid, f"📁 {d.get('name')}")
                sent += 1
            except Exception:
                pass
        await m.reply_text(f"Sent {sent} items.")
        return

    # else GF (chat) mode — call GPT if available
    try:
        if OPENAI_KEY:
            reply = await gpt_reply(text)
        else:
            reply = romantic_fallback(text)
    except Exception:
        reply = romantic_fallback(text)
    await m.reply_text(reply)

# ----------------------------
# Inline query: if user types @Bot file: or chat:, provide options
# ----------------------------
@bot.on_inline_query()
async def inline_handler(_, iq: InlineQuery):
    q = iq.query.strip()
    if not q:
        return await iq.answer([], cache_time=0)

    # if user writes "file: ..." do file search
    if q.lower().startswith("file:"):
        query = q.split("file:",1)[1].strip()
        if len(normalize_words(query)) < 3:
            return await iq.answer([], switch_pm_text="Send 3+ words to search", switch_pm_parameter="need3")
        matches = await search_files_by_query(query, min_matches=3, limit=20)
        results = []
        for m in matches[:15]:
            title = m.get("name","")[:64]
            results.append(
                InlineQueryResultArticle(
                    id=str(m["_id"]),
                    title=title or "file",
                    input_message_content=InputTextMessageContent(f"📁 {title}\nFrom channel {m.get('source_chat')}")
                )
            )
        await iq.answer(results, cache_time=0)
        return

    # chat mode: pass to GPT (limit length)
    if q.lower().startswith("chat:"):
        prompt = q.split("chat:",1)[1].strip()
        if not prompt:
            return await iq.answer([], switch_pm_text="Type message after chat:", switch_pm_parameter="needtext")
        # run gpt sync in executor
        try:
            res = await gpt_reply(prompt)
            art = InlineQueryResultArticle(
                id="g1",
                title="GF Reply",
                input_message_content=InputTextMessageContent(res)
            )
            await iq.answer([art], cache_time=0)
            return
        except Exception:
            return await iq.answer([], cache_time=0)

    # default: no results
    await iq.answer([], cache_time=0)

# ----------------------------
# Startup routine
# ----------------------------
async def startup():
    # ensure indexes/db documents if needed
    if config_col is not None:
        await config_col.update_one({"_id":"meta"}, {"$setOnInsert": {"created": True}}, upsert=True)
    print("Startup complete.")

async def start_services():
    # start bot
    await startup()
    await bot.start()
    print("🔥 Pyrogram started")

    # start flask in executor thread so Render sees a bound port
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, lambda: app.run(host="0.0.0.0", port=PORT))
    print(f"🌐 Flask started on port {PORT}")

    # keep process alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    # run main asyncio loop
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        print("Stopping...")
    except Exception:
        log_exc("main")
