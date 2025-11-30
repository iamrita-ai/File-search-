# bot.py — Serena Full-featured (Render web service compatible)
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

import openai  # make sure openai is in requirements.txt

# ---------------------- CONFIG (fixed) ----------------------
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
OWNER_USERNAME = "technicalserena"

API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_DB = os.environ.get("MONGO_DB")  # mongodb+srv://...
OPENAI_KEY = os.environ.get("OPENAI_KEY")  # optional
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("serena")

# ---------------------- FLASK KEEPALIVE ----------------------
app = Flask("serena_web")
@app.route("/")
def index():
    return "Serena File Bot — Web service alive 💗"

# ---------------------- MONGO (async) -----------------------
if not MONGO_DB:
    log.warning("MONGO_DB not set — DB features will be disabled.")
    mongo = None
    db = None
else:
    mongo = AsyncIOMotorClient(MONGO_DB)
    db = mongo["serena_bot_db"]

# Collections (may be None if no mongo)
users_col = db["users"] if db else None
files_col = db["files"] if db else None
config_col = db["config"] if db else None
premium_col = db["premium"] if db else None

# ---------------------- OPENAI SETUP ------------------------
openai.api_key = OPENAI_KEY

async def ai_reply(prompt: str) -> str:
    if not OPENAI_KEY:
        return "Janu, OpenAI key missing — abhi offline mode se pyaar bhara reply kar rahi hoon 😘"
    def call():
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system","content":"You are a romantic girlfriend. Reply briefly, lovingly, with emojis."},
                    {"role":"user","content": prompt}
                ],
                temperature=0.9,
                max_tokens=250,
            )
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.exception("OpenAI error")
            return "Janu, thoda sa load aa gaya… dobara bolo na ❤️"
    return await asyncio.to_thread(call)

# ---------------------- PYROGRAM BOT ------------------------
bot = Client(
    "serena_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=None,  # default
    workers=30
)

# ---------------------- UTIL HELPERS -----------------------
def split_words(s: str):
    return [w for w in re.split(r"\s+", s.lower()) if w]

def min_word_match(query: str, name: str, min_matches: int = 3) -> bool:
    q = split_words(query)
    n = split_words(name)
    if not q or not n:
        return False
    matches = sum(1 for w in q if any(w in part for part in n))
    return matches >= min_matches

async def ensure_config_doc():
    if not config_col:
        return
    await config_col.update_one(
        {"_id": "cfg"},
        {"$setOnInsert": {"sources": [], "logs": LOGS_CHANNEL, "replace_words": [], "caption": "❤️ File mil gaya Janu!"}},
        upsert=True
    )

async def get_config() -> dict:
    if not config_col:
        return {"sources": [], "logs": LOGS_CHANNEL, "replace_words": [], "caption": "❤️ File mil gaya Janu!"}
    cfg = await config_col.find_one({"_id": "cfg"})
    if not cfg:
        await ensure_config_doc()
        cfg = await config_col.find_one({"_id": "cfg"})
    return cfg

async def save_config(updates: dict):
    if not config_col:
        return
    await config_col.update_one({"_id": "cfg"}, {"$set": updates}, upsert=True)

async def typing_n_reply(chat_id: int, text: str, reply_to: Optional[int] = None):
    try:
        await bot.send_chat_action(chat_id, "typing")
    except:
        pass
    await asyncio.sleep(0.6)
    await bot.send_message(chat_id, text, reply_to_message_id=reply_to)

# ---------------------- START / HELP / STATUS ----------------
@bot.on_message(filters.command("start"))
async def cmd_start(_, m):
    if users_col:
        await users_col.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id, "first_seen": datetime.datetime.utcnow()}}, upsert=True)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Chat (Inline)", switch_inline_query_current_chat="chat: ")],
        [InlineKeyboardButton("🔎 File search (Inline)", switch_inline_query_current_chat="file: ")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")],
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    await m.reply_text(f"Hey {m.from_user.first_name} ❤️\nMain tumhari Serena ho — bolo kya chahiye? 😘", reply_markup=kb)

@bot.on_message(filters.command("help"))
async def cmd_help(_, m):
    txt = ("💗 *How to use Serena:*\n\n"
           "• Inline Chat: `@YourBot chat: I miss you`\n"
           "• Inline File Search: `@YourBot file: movie season episode` (min 3 words)\n\n"
           "Commands:\n"
           "/addpremium <id> — owner only\n"
           "/rempremium <id> — owner only\n"
           "/status — bot status\n"
           "/clear — owner only clears DB\n"
           "/settings — open settings\n")
    await m.reply_text(txt)

@bot.on_message(filters.command("status"))
async def cmd_status(_, m):
    files_count = await files_col.count_documents({}) if files_col else 0
    users_count = await users_col.count_documents({}) if users_col else 0
    await m.reply_text(f"🤖 Serena is alive!\n📁 Files: {files_count}\n👥 Users: {users_count}")

# ---------------------- PREMIUM / CLEAR -------------------
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, m):
    if len(m.command) < 2:
        return await m.reply_text("Usage: /addpremium <user_id>")
    uid = int(m.command[1])
    if premium_col:
        await premium_col.update_one({"user_id": uid}, {"$set": {"user_id": uid, "premium": True}}, upsert=True)
    await m.reply_text(f"💎 User {uid} added to premium")
    await typing_n_reply(m.chat.id, "Done baby ❤️")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, m):
    if len(m.command) < 2:
        return await m.reply_text("Usage: /rempremium <user_id>")
    uid = int(m.command[1])
    if premium_col:
        await premium_col.update_one({"user_id": uid}, {"$set": {"premium": False}})
    await m.reply_text(f"Removed {uid} from premium")
    await typing_n_reply(m.chat.id, "Removed baby 💔")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, m):
    if files_col:
        await files_col.delete_many({})
    if users_col:
        await users_col.delete_many({})
    if config_col:
        await config_col.delete_one({"_id":"cfg"})
    await m.reply_text("🧹 Database cleared")
    await typing_n_reply(m.chat.id, "Saaf ho gaya meri jaan 💖")

# ---------------------- SETTINGS PANEL --------------------
@bot.on_message(filters.command("settings") & filters.user(OWNER_ID))
async def cmd_settings(_, m):
    cfg = await get_config()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Set source channel", callback_data="set_source"), InlineKeyboardButton("🗑 Remove logs", callback_data="remove_logs")],
        [InlineKeyboardButton("✏️ Replace words", callback_data="replace_words"), InlineKeyboardButton("📝 Set caption", callback_data="set_caption")],
        [InlineKeyboardButton("🤖 Inline Chat ON/OFF", callback_data="toggle_chat"), InlineKeyboardButton("🔎 Inline File Search ON/OFF", callback_data="toggle_file")]
    ])
    await m.reply_text("⚙️ Settings panel — choose:", reply_markup=kb)

# callback handling
@bot.on_callback_query()
async def callback_handler(_, q):
    data = q.data
    uid = q.from_user.id
    if data == "open_settings":
        await cmd_settings(_, q.message)
        await q.answer()
        return

    cfg = await get_config()
    if data == "set_source":
        await q.message.reply("Send source channel id in private, starting with -100")
    elif data == "remove_logs":
        await save_config({"logs": None})
        await q.answer("Logs removed", show_alert=True)
    elif data == "replace_words":
        await q.message.reply("Send replacement pairs like: old1:new1,old2:new2")
    elif data == "set_caption":
        await q.message.reply("Send new caption for forwarded files")
    elif data == "toggle_chat":
        cur = cfg.get("inline_chat", True)
        await save_config({"inline_chat": not cur})
        await q.answer(f"Inline Chat set to {not cur}", show_alert=True)
    elif data == "toggle_file":
        cur = cfg.get("inline_file", True)
        await save_config({"inline_file": not cur})
        await q.answer(f"Inline File Search set to {not cur}", show_alert=True)
    else:
        await q.answer()

# ---------------------- CHANNEL MESSAGES (index & copy to logs) ----------------
@bot.on_message(filters.channel)
async def on_channel_message(_, message):
    try:
        cfg = await get_config()
        # always copy to logs if logs configured
        logs = cfg.get("logs", LOGS_CHANNEL)
        copied = None
        if logs:
            try:
                copied = await message.copy(logs)
            except Exception:
                log.exception("Failed to copy to logs")

        # index if from source channels
        sources = cfg.get("sources", [])
        if message.chat.id in sources:
            file_id = None
            name = ""
            if message.document:
                file_id = message.document.file_id
                name = message.document.file_name or f"document_{message.message_id}"
            elif message.video:
                file_id = message.video.file_id
                name = getattr(message.video, "file_name", f"video_{message.message_id}")
            elif message.photo:
                file_id = message.photo.file_id
                name = f"photo_{message.message_id}"
            elif message.audio:
                file_id = message.audio.file_id
                name = getattr(message.audio, "file_name", f"audio_{message.message_id}")
            if file_id and files_col:
                doc = {"file_id": file_id, "name": name.lower(), "source_chat": message.chat.id, "source_msg_id": message.message_id, "ts": datetime.datetime.utcnow()}
                if copied and getattr(copied, "message_id", None):
                    doc["logs_msg_id"] = copied.message_id
                    doc["logs_chat_id"] = logs
                await files_col.insert_one(doc)
                try:
                    if logs:
                        await bot.send_message(logs, f"📦 Saved: `{name}`")
                except:
                    pass
    except Exception:
        log.exception("on_channel_message error")

# ---------------------- INLINE QUERY (chat: and file:) ----------------
@bot.on_inline_query()
async def on_inline_query(_, iq):
    q = iq.query.strip()
    cfg = await get_config()
    # chat mode
    if q.startswith("chat:"):
        if not cfg.get("inline_chat", True):
            await iq.answer([], switch_pm_text="Inline chat is disabled", switch_pm_parameter="chat_disabled", cache_time=0)
            return
        prompt = q.replace("chat:", "", 1).strip() or "hi baby"
        reply = await ai_reply(prompt)
        art = InlineQueryResultArticle(
            id="chat1",
            title="Romantic reply",
            input_message_content=InputTextMessageContent(reply),
            description=(reply[:80] + "...") if len(reply) > 80 else reply
        )
        await iq.answer([art], cache_time=0, is_personal=True)
        return

    # file mode
    if q.startswith("file:"):
        if not cfg.get("inline_file", True):
            await iq.answer([], switch_pm_text="Inline file search disabled", switch_pm_parameter="file_disabled", cache_time=0)
            return
        query = q.replace("file:", "", 1).strip()
        words = split_words(query)
        if len(words) < 3:
            await iq.answer([], switch_pm_text="Minimum 3 words required", switch_pm_parameter="need3", cache_time=0)
            return
        found = []
        if files_col:
            async for doc in files_col.find().sort("ts", -1).limit(500):
                if min_word_match(query, doc.get("name", ""), min_matches=3):
                    found.append(doc)
        results = []
        for d in found[:50]:
            id_str = str(d.get("_id"))
            title = d.get("name", "")[:60]
            results.append(InlineQueryResultArticle(
                id=id_str,
                title=title,
                input_message_content=InputTextMessageContent(f"📁 File: {d.get('name')}"),
                description="Tap to view/send info"
            ))
        await iq.answer(results, cache_time=0, is_personal=True)
        return

    # default: nothing
    await iq.answer([], cache_time=0)

# ---------------------- PRIVATE DM SEARCH (3-word) ----------------
@bot.on_message(filters.private & filters.text & ~filters.command(["start","help","status","settings","clear","addpremium","rempremium"]))
async def private_search(_, m):
    text = m.text.strip()
    words = split_words(text)
    if len(words) < 3:
        return await typing_n_reply(m.chat.id, "Aww baby… please give at least 3 words so I can find better matches 💕", reply_to=m.message_id)

    matched = []
    if files_col:
        async for doc in files_col.find().sort("ts", -1):
            if min_word_match(text, doc.get("name",""), min_matches=3):
                matched.append(doc)
    if not matched:
        return await typing_n_reply(m.chat.id, "🌸 No Results Found — try a slightly different keyword, meri jaan 💖", reply_to=m.message_id)

    sent = 0
    cfg = await get_config()
    logs = cfg.get("logs", LOGS_CHANNEL)
    for d in matched[:8]:
        try:
            # prefer copy from logs (preserves file/media)
            if d.get("logs_chat_id") and d.get("logs_msg_id"):
                await bot.copy_message(m.chat.id, d["logs_chat_id"], d["logs_msg_id"])
            else:
                # send by file_id (works for documents)
                await bot.send_document(m.chat.id, d["file_id"], caption=cfg.get("caption", "❤️ File mil gaya Janu!"))
            sent += 1
            await asyncio.sleep(0.6)
        except Exception:
            log.exception("send matched file error")
    await bot.send_message(m.chat.id, f"✅ Sent {sent} file(s), Sweetheart 💋")

# ---------------------- GM/GN BACKGROUND TASK ----------------
async def gm_gn_task():
    last_gm_date = None
    last_gn_date = None
    while True:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)  # IST
        today = now.date().isoformat()
        if now.hour == 8 and last_gm_date != today:
            if users_col:
                async for u in users_col.find({}, {"user_id":1}).limit(500):
                    try:
                        await bot.send_message(u["user_id"], "🌅 Good Morning, Jaan! Have a lovely day ❤️")
                        await asyncio.sleep(0.5)
                    except:
                        pass
            last_gm_date = today
        if now.hour == 22 and last_gn_date != today:
            if users_col:
                async for u in users_col.find({}, {"user_id":1}).limit(500):
                    try:
                        await bot.send_message(u["user_id"], "🌙 Good Night, Sweetheart! 😴")
                        await asyncio.sleep(0.5)
                    except:
                        pass
            last_gn_date = today
        await asyncio.sleep(60)

# ---------------------- STARTUP TASKS ----------------
async def startup_tasks():
    # ensure config doc exists
    if config_col:
        await ensure_config_doc()
    # start gm/gn
    asyncio.create_task(gm_gn_task())
    log.info("Startup tasks scheduled")

# ---------------------- RUN: Flask (main thread) + Pyrogram (async main) ----------------
def run_flask():
    app.run(host="0.0.0.0", port=PORT)

async def run_bot():
    await startup_tasks()
    await bot.start()
    log.info("Bot started")
    # keep alive
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    # run flask in a background thread (so Render sees the port)
    fl = Thread(target=run_flask, daemon=True)
    fl.start()

    # run pyrogram bot in main async loop
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log.info("Stopping bot")
        try:
            asyncio.run(bot.stop())
        except:
            pass
