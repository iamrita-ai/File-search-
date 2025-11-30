# bot.py
import os
import asyncio
import logging
import datetime
import re
from flask import Flask
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from motor.motor_asyncio import AsyncIOMotorClient
import openai

# ---------------- config (owner / defaults) ----------------
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
OWNER_USERNAME = "technicalserena"

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB = os.getenv("MONGO_DB")          # required
OPENAI_KEY = os.getenv("OPENAI_KEY")      # optional
PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("serena")

# ---------------- flask (web service port) ----------------
app = Flask("serena_service")

@app.route("/")
def index():
    return "Serena File Bot — Web service alive 💗"

# ---------------- mongo (async) ----------------
mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo["serena_bot_db"]
users_col = db["users"]
files_col = db["files"]
config_col = db["config"]

# ensure default config doc exists
async def ensure_config():
    await config_col.update_one({"_id":"cfg"}, {"$setOnInsert": {"sources": [], "logs": LOGS_CHANNEL, "replace_words": [], "caption": "❤️ File mil gaya Janu!"}}, upsert=True)
# run sync check on startup (we will schedule in bot loop)

# ---------------- pyrogram client ----------------
bot = Client("serena_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=50)

# ---------------- helpers ----------------
def min_word_match(query, name, min_matches=3):
    q = [w for w in re.split(r"\s+", query.lower()) if w]
    n = [w for w in re.split(r"\s+", name.lower()) if w]
    if not q or not n: return False
    matches = sum(1 for w in q if any(w in part for part in n))
    return matches >= min_matches

async def typing_then_send(chat_id, text):
    try:
        await bot.send_chat_action(chat_id, "typing")
    except:
        pass
    await asyncio.sleep(0.6)
    await bot.send_message(chat_id, text)

# ---------------- OpenAI helper (sync call via thread) ----------------
openai.api_key = OPENAI_KEY if OPENAI_KEY else None

async def ai_reply_async(prompt: str):
    if not OPENAI_KEY:
        return "Janu, OpenAI key set nahi hai — mujhe abhi offline mode me pyaar se reply karna padega 😘"
    # call in thread to avoid blocking loop
    def call_openai():
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"You are a loving romantic girlfriend. Keep replies short, affectionate, with emojis."},
                    {"role":"user","content": prompt}
                ],
                temperature=0.9,
                max_tokens=220
            )
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.exception("openai error")
            return "Janu, thoda sa load aa gaya… dobara bolo na ❤️"
    return await asyncio.to_thread(call_openai)

# ---------------- config helpers ----------------
async def get_config():
    cfg = await config_col.find_one({"_id":"cfg"})
    if not cfg:
        await ensure_config()
        cfg = await config_col.find_one({"_id":"cfg"})
    return cfg

async def save_config(cfg_updates: dict):
    await config_col.update_one({"_id":"cfg"}, {"$set": cfg_updates}, upsert=True)

# ---------------- start/help/status ----------------
@bot.on_message(filters.command("start"))
async def cmd_start(client, message):
    await users_col.update_one({"user_id": message.from_user.id}, {"$set": {"user_id": message.from_user.id, "first_seen": datetime.datetime.utcnow()}}, upsert=True)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Chat (Inline)", switch_inline_query_current_chat="chat: ")],
        [InlineKeyboardButton("🔎 File search (Inline)", switch_inline_query_current_chat="file: ")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")],
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    text = f"Heyy my love {message.from_user.first_name} ❤️\nMain tumhari Serena ho — bolo kya chahiye? 😘"
    await message.reply_text(text, reply_markup=kb)

@bot.on_message(filters.command("help"))
async def cmd_help(client, message):
    text = (
        "💗 How to use Serena:\n\n"
        "• *Inline Chat* — Type in any chat: `@YourBotUsername chat: I miss you` → romantic reply\n"
        "• *Inline File Search* — `@YourBotUsername file: movie season episode 1` (minimum 3 words)\n\n"
        "Commands:\n"
        "/addpremium <id> — (owner) give premium\n"
        "/rempremium <id> — (owner) remove premium\n"
        "/status — bot status\n"
        "/clear — (owner) clear DB\n"
        "/settings — open settings panel\n\n"
        "Example inline: `file: the great movie part 1 2020`"
    )
    await message.reply_text(text)

@bot.on_message(filters.command("status"))
async def cmd_status(client, message):
    count = await files_col.count_documents({})
    await message.reply_text(f"🤖 Serena is alive!\n📁 Files indexed: {count}")

# ---------------- premium / clear ----------------
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def cmd_addpremium(_, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addpremium <user_id>")
    uid = int(message.command[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
    await message.reply_text(f"User {uid} added to premium 💎")

@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def cmd_rempremium(_, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /rempremium <user_id>")
    uid = int(message.command[1])
    await users_col.update_one({"user_id": uid}, {"$set": {"premium": False}})
    await message.reply_text(f"User {uid} removed from premium ❌")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, message):
    await files_col.delete_many({})
    await message.reply_text("Database cleared 🧹")

# ---------------- settings panel ----------------
@bot.on_message(filters.command("settings"))
async def cmd_settings(client, message):
    cfg = await get_config()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Set source channel", callback_data="set_source") , InlineKeyboardButton("🗑 Remove logs channel", callback_data="remove_logs")],
        [InlineKeyboardButton("✏️ Replace words", callback_data="replace_words"), InlineKeyboardButton("📝 Set caption", callback_data="set_caption")],
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ])
    await message.reply_text("⚙️ Settings panel — choose an option", reply_markup=kb)

@bot.on_callback_query()
async def cb_handler(client, query):
    data = query.data
    uid = query.from_user.id
    if data == "open_settings":
        await cmd_settings(client, query.message)
        return
    if data == "set_source":
        await query.message.reply("Send me source channel id in private (use -100...)")
    elif data == "remove_logs":
        await save_config({"logs": None})
        await query.answer("Logs removed", show_alert=True)
    elif data == "replace_words":
        await query.message.reply("Send replace pairs as: old1:new1,old2:new2")
    elif data == "set_caption":
        await query.message.reply("Send new caption text for forwarded files")
    await query.answer()

# ---------------- channel -> logs copy & index ----------------
@bot.on_message(filters.channel)
async def on_channel_message(client, message):
    cfg = await get_config()
    sources = cfg.get("sources", [])
    # always copy to logs if logs configured
    logs = cfg.get("logs", LOGS_CHANNEL)
    try:
        if logs:
            await message.copy(logs)
    except Exception:
        pass

    # if message from a configured source, index file(s)
    if message.chat.id in sources:
        # document, video, audio, photo handling
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
        if file_id:
            await files_col.insert_one({"file_id": file_id, "name": name.lower(), "ts": datetime.datetime.utcnow()})
            # optional notify owner/logs
            try:
                if logs:
                    await bot.send_message(logs, f"📦 Saved: `{name}`")
            except:
                pass

# ---------------- inline query handler (chat: and file:) ----------------
@bot.on_inline_query()
async def on_inline_query(client, inline_query):
    q = inline_query.query.strip()
    if q.startswith("chat:"):
        text = q.replace("chat:", "", 1).strip() or "hi baby"
        # get ai reply
        reply = await ai_reply_async(text)
        result = InlineQueryResultArticle(
            id="chat1",
            title="Romantic reply",
            input_message_content=InputTextMessageContent(reply),
            description=reply[:80]
        )
        await inline_query.answer([result], cache_time=0, is_personal=True)
        return

    if q.startswith("file:"):
        text = q.replace("file:", "", 1).strip()
        words = [w for w in re.split(r"\s+", text) if w]
        if len(words) < 3:
            await inline_query.answer([], switch_pm_text="Minimum 3 words required", switch_pm_parameter="need3", cache_time=0)
            return
        # build regex to require presence (loose) - simpler approach: check min_word_match
        found = []
        async for doc in files_col.find().sort("ts", -1).limit(200):
            if min_word_match(text, doc.get("name",""), min_matches=3):
                found.append(doc)
        results = []
        for d in found[:20]:
            results.append(InlineQueryResultArticle(
                id=str(d.get("_id")),
                title=d.get("name", "")[:40],
                input_message_content=InputTextMessageContent(f"📁 File: {d.get('name')}"),
                description="Tap to send file info"
            ))
        await inline_query.answer(results, cache_time=0, is_personal=True)
        return

# ---------------- private DM search (3-word min) ----------------
@bot.on_message(filters.private & filters.text & ~filters.command(["start","help","status","settings","clear","addpremium","rempremium"]))
async def private_search(client, message):
    text = message.text.strip()
    words = [w for w in re.split(r"\s+", text) if w]
    if len(words) < 3:
        # romantic nudge
        return await typing_then_send(message.chat.id, "Aww baby, thoda batao (at least 3 words) 💕")

    # search
    matched = []
    async for doc in files_col.find().sort("ts",-1):
        if min_word_match(text, doc.get("name",""), min_matches=3):
            matched.append(doc)
    if not matched:
        return await typing_then_send(message.chat.id, "🌸 No Results Found — try a slightly different keyword, meri jaan 💖")

    # send up to 8 matches (copy from logs if logs stored)
    cfg = await get_config()
    logs = cfg.get("logs", LOGS_CHANNEL)
    sent = 0
    for d in matched[:8]:
        fid = d.get("file_id")
        try:
            # if we have logs channel and message was copied there previously, prefer copy, else send by file_id
            if logs:
                # we can't copy by file_id; just send document by file_id
                await bot.send_document(message.chat.id, fid, caption=f"❤️ Found: {d.get('name')}")
            else:
                await bot.send_document(message.chat.id, fid, caption=f"❤️ Found: {d.get('name')}")
            sent += 1
            await asyncio.sleep(0.6)
        except Exception:
            pass
    await bot.send_message(message.chat.id, f"✅ Sent {sent} file(s), Sweetheart 💋")

# ---------------- auto Good Morning / Good Night (runs in bot loop) ----------------
async def gm_gn_task():
    last_gm = None
    last_gn = None
    while True:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)  # IST
        date_str = now.date().isoformat()
        if now.hour == 8 and last_gm != date_str:
            # send to all users (limited)
            cursor = users_col.find({}, {"user_id":1}).limit(300)
            async for u in cursor:
                try:
                    await bot.send_message(u["user_id"], "🌅 Good Morning, Jaan! Have a lovely day ❤️")
                except:
                    pass
            last_gm = date_str
        if now.hour == 22 and last_gn != date_str:
            cursor = users_col.find({}, {"user_id":1}).limit(300)
            async for u in cursor:
                try:
                    await bot.send_message(u["user_id"], "🌙 Good Night, Sweetheart! 😴")
                except:
                    pass
            last_gn = date_str
        await asyncio.sleep(60)

# ---------------- startup/shutdown tasks ----------------
async def start_background_tasks(loop):
    await ensure_config()
    # start gm/gn task
    loop.create_task(gm_gn_task())

# ---------------- run bot in background thread (safe for Render web service) ----------------
def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # run client.start() and then keep loop running
    loop.run_until_complete(start_background_tasks(loop))
    loop.run_until_complete(bot.start())
    log.info("Bot started in background loop")
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(bot.stop())

# ---------------- main entry - run flask (main thread) and bot in background thread ----------------
if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_bot_loop, daemon=True)
    t.start()
    # run flask to satisfy Render web-service port binding
    app.run(host="0.0.0.0", port=PORT)
