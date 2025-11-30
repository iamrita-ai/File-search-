# bot.py — Serena Full-featured (Render web service compatible, bool-check fix)
import os
import re
import asyncio
import logging
import datetime
from threading import Thread
from typing import Optional

from flask import Flask
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from motor.motor_asyncio import AsyncIOMotorClient

import openai  # in requirements.txt

# ---------------------- CONFIG ----------------------
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
OWNER_USERNAME = "technicalserena"

API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_DB = os.environ.get("MONGO_DB")
OPENAI_KEY = os.environ.get("OPENAI_KEY")
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("serena")

# ---------------------- FLASK ----------------------
app = Flask("serena_web")
@app.route("/")
def index():
    return "Serena File Bot — Web service alive 💗"

# ---------------------- MONGO -----------------------
mongo = None
db = None
users_col = None
files_col = None
config_col = None
premium_col = None

if MONGO_DB:
    mongo = AsyncIOMotorClient(MONGO_DB)
    db = mongo["serena_bot_db"]
    users_col = db["users"]
    files_col = db["files"]
    config_col = db["config"]
    premium_col = db["premium"]
else:
    log.warning("⚠️ MONGO_DB not set — DB features disabled.")

# ---------------------- OPENAI ------------------------
openai.api_key = OPENAI_KEY

async def ai_reply(prompt: str) -> str:
    if OPENAI_KEY is None:
        return "Janu, OpenAI key missing — offline romantic mode active 😘"

    def call():
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system","content":"You are a romantic girlfriend."},
                    {"role":"user","content":prompt}
                ]
            )
            return resp["choices"][0]["message"]["content"]
        except:
            return "Baby load aa gaya… phir se bolo ❤️"

    return await asyncio.to_thread(call)

# ---------------------- BOT ------------------------
bot = Client(
    "serena_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------------- HELPERS ----------------------
def split_words(s: str):
    return [w for w in re.split(r"\s+", s.lower()) if w]

def min_word_match(query: str, name: str, min_matches: int = 3) -> bool:
    q = split_words(query)
    n = split_words(name)
    if len(q) == 0 or len(n) == 0:
        return False
    matches = sum(1 for w in q if any(w in part for part in n))
    return matches >= min_matches

async def ensure_config_doc():
    if config_col is None:
        return
    await config_col.update_one(
        {"_id":"cfg"},
        {"$setOnInsert":{
            "sources":[],
            "logs":LOGS_CHANNEL,
            "replace_words":[],
            "caption":"❤️ File mil gaya Janu!"
        }},
        upsert=True
    )

async def get_config():
    if config_col is None:
        return {"sources":[], "logs":LOGS_CHANNEL, "replace_words":[], "caption":"❤️ File mil gaya Janu!"}
    cfg = await config_col.find_one({"_id":"cfg"})
    if cfg is None:
        await ensure_config_doc()
        cfg = await config_col.find_one({"_id":"cfg"})
    return cfg

async def save_config(update_data: dict):
    if config_col is None:
        return
    await config_col.update_one({"_id":"cfg"}, {"$set":update_data})

async def typing_n_reply(chat_id, text, reply_to=None):
    try:
        await bot.send_chat_action(chat_id, "typing")
    except:
        pass
    await asyncio.sleep(0.6)
    await bot.send_message(chat_id, text, reply_to_message_id=reply_to)

# ---------------------- START ----------------------
@bot.on_message(filters.command("start"))
async def start_cmd(_, m):
    if users_col is not None:
        await users_col.update_one(
            {"user_id":m.from_user.id},
            {"$set":{"user_id":m.from_user.id}},
            upsert=True
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Inline Chat", switch_inline_query_current_chat="chat: ")],
        [InlineKeyboardButton("🔎 Inline File Search", switch_inline_query_current_chat="file: ")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")],
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    await m.reply("Hey Jaan ❤️ Main tumhari Serena ho 😘", reply_markup=kb)

# ---------------------- HELP ------------------------
@bot.on_message(filters.command("help"))
async def help_cmd(_, m):
    await m.reply("❤️ Help Menu\n- Inline Chat: @Bot chat: msg\n- Inline File: @Bot file: 3+ words")

# ---------------------- STATUS ------------------------
@bot.on_message(filters.command("status"))
async def status_cmd(_, m):
    users = await users_col.count_documents({}) if users_col is not None else 0
    files = await files_col.count_documents({}) if files_col is not None else 0
    await m.reply(f"🤖 Alive\nUsers: {users}\nFiles: {files}")

# ---------------------- PREMIUM ------------------------
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def addpremium(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /addpremium <id>")
    uid = int(m.command[1])
    if premium_col is not None:
        await premium_col.update_one({"user_id":uid},{"$set":{"premium":True}},upsert=True)
    await m.reply("Premium added ❤️")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def rempremium(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /rempremium <id>")
    uid = int(m.command[1])
    if premium_col is not None:
        await premium_col.delete_one({"user_id":uid})
    await m.reply("Removed ❤️")

# ---------------------- CLEAR DB ------------------------
@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_cmd(_, m):
    if users_col is not None: await users_col.delete_many({})
    if files_col is not None: await files_col.delete_many({})
    if config_col is not None: await config_col.delete_one({"_id":"cfg"})
    await m.reply("💥 Database cleared")

# ---------------------- SETTINGS PANEL ----------------------
@bot.on_message(filters.command("settings") & filters.user(OWNER_ID))
async def settings_cmd(_, m):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Set Source", callback_data="set_source"),
         InlineKeyboardButton("Replace Words", callback_data="replace_words")]
    ])
    await m.reply("⚙ Settings", reply_markup=kb)

@bot.on_callback_query()
async def cb(_, q):
    if q.data == "open_settings":
        await settings_cmd(_, q.message)
        await q.answer()
        return

    await q.answer("Coming Soon ❤️")

# ---------------------- CHANNEL INDEXING ----------------------
@bot.on_message(filters.channel)
async def channel_msg(_, msg):
    cfg = await get_config()
    logs = cfg.get("logs", LOGS_CHANNEL)

    # copy to logs
    try:
        await msg.copy(logs)
    except:
        pass

    sources = cfg.get("sources", [])
    if msg.chat.id not in sources:
        return

    if files_col is None:
        return

    file_id = None
    name = ""

    if msg.document:
        file_id = msg.document.file_id
        name = msg.document.file_name or "doc"
    elif msg.video:
        file_id = msg.video.file_id
        name = msg.video.file_name or "video"
    elif msg.audio:
        file_id = msg.audio.file_id
        name = msg.audio.file_name or "audio"

    if file_id is None:
        return

    await files_col.insert_one({
        "file_id":file_id,
        "name":name.lower(),
        "source_chat":msg.chat.id,
        "ts": datetime.datetime.utcnow()
    })

# ---------------------- INLINE QUERY ----------------------
@bot.on_inline_query()
async def inline_query_handler(_, iq):
    q = iq.query.strip()

    # inline chat
    if q.startswith("chat:"):
        msg = q.replace("chat:", "").strip()
        reply = await ai_reply(msg or "hi baby")
        art = InlineQueryResultArticle(
            id="1",
            title="❤️ Romantic Reply",
            input_message_content=InputTextMessageContent(reply)
        )
        return await iq.answer([art], cache_time=0)

    # inline file search
    if q.startswith("file:"):
        query = q.replace("file:", "").strip()
        words = split_words(query)
        if len(words) < 3:
            return await iq.answer([], switch_pm_text="3+ words required", switch_pm_parameter="need3")

        results = []
        if files_col is not None:
            async for d in files_col.find().limit(40):
                if min_word_match(query, d["name"]):
                    title = d["name"][:50]
                    results.append(
                        InlineQueryResultArticle(
                            id=str(d["_id"]),
                            title=title,
                            input_message_content=InputTextMessageContent(f"📁 {title}")
                        )
                    )

        return await iq.answer(results, cache_time=0)

    await iq.answer([])

# ---------------------- PRIVATE SEARCH ----------------------
@bot.on_message(filters.private & filters.text & ~filters.command())
async def private_text(_, m):
    txt = m.text.strip()
    words = split_words(txt)
    if len(words) < 3:
        return await typing_n_reply(m.chat.id, "Baby 3 words do na 😘", reply_to=m.id)

    if files_col is None:
        return await m.reply("DB off hai baby 😢")

    matched = []
    async for d in files_col.find().limit(30):
        if min_word_match(txt, d["name"]):
            matched.append(d)

    if len(matched) == 0:
        return await typing_n_reply(m.chat.id, "No results Found Jaan 💔", reply_to=m.id)

    for d in matched[:6]:
        try:
            await bot.send_document(m.chat.id, d["file_id"])
            await asyncio.sleep(0.5)
        except:
            pass

    await bot.send_message(m.chat.id, f"❤️ Sent {len(matched[:6])} files baby")

# ---------------------- GM/GN SCHEDULER ----------------------
async def gm_gn_task():
    last_gm = None
    last_gn = None
    while True:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
        today = now.date().isoformat()

        if now.hour == 8 and last_gm != today:
            if users_col is not None:
                async for u in users_col.find({}, {"user_id":1}):
                    try:
                        await bot.send_message(u["user_id"], "🌅 Good Morning Jaan ❤️")
                    except:
                        pass
            last_gm = today

        if now.hour == 22 and last_gn != today:
            if users_col is not None:
                async for u in users_col.find({}, {"user_id":1}):
                    try:
                        await bot.send_message(u["user_id"], "🌙 Good Night Baby 😘")
                    except:
                        pass
            last_gn = today

        await asyncio.sleep(60)

# ---------------------- STARTUP ----------------------
async def startup():
    await ensure_config_doc()
    asyncio.create_task(gm_gn_task())

# ---------------------- RUN ----------------------
def run_flask():
    app.run(host="0.0.0.0", port=PORT)

async def run_bot():
    await startup()
    await bot.start()
    while True:
        await asyncio.sleep(30)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_bot())
