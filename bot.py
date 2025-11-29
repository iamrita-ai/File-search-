# bot.py
import os
import asyncio
import threading
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask

# ---------------- CONFIG ----------------
OWNER_ID = 1598576202
BOT_CREDIT = "@technicalserena"
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003286415377"))
MAX_SOURCE_CHANNELS = 3
SOURCE_CHANNELS = []

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# ---------------- MONGO ----------------
mongo_client = AsyncIOMotorClient(MONGO_DB_URI) if MONGO_DB_URI else None
db = mongo_client["TelegramBotDB"] if mongo_client else None
users_col = db["Users"] if db else None
config_col = db["Config"] if db else None
pending_col = db["Pending"] if db else None

# ---------------- PYROGRAM ----------------
app = Client(
    "SerenaRomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------------- FLASK ----------------
flask_app = Flask("serena_dummy")

@flask_app.route("/")
def homepage():
    return "Serena Bot is alive ❤️"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ---------------- UTILS ----------------
async def fast_send(client, chat_id, text, **kwargs):
    return await client.send_message(chat_id, text, **kwargs)

async def slow_send(client, chat_id, text, delay=10, **kwargs):
    msg = await client.send_message(chat_id, text, **kwargs)
    await asyncio.sleep(delay)
    return msg

# ---------------- DB HELPERS ----------------
async def load_source_channels():
    global SOURCE_CHANNELS
    if config_col:
        cfg = await config_col.find_one({"_id": "source_channels"})
        if cfg and isinstance(cfg.get("channels"), list):
            SOURCE_CHANNELS = cfg["channels"]
        else:
            await config_col.update_one({"_id":"source_channels"}, {"$set":{"channels":SOURCE_CHANNELS}}, upsert=True)

async def save_source_channels():
    if config_col:
        await config_col.update_one({"_id":"source_channels"}, {"$set":{"channels":SOURCE_CHANNELS}}, upsert=True)

async def set_pending_action(user_id, action):
    if pending_col:
        await pending_col.update_one({"user_id": user_id}, {"$set":{"action":action}}, upsert=True)

async def get_pending_action(user_id):
    if pending_col is None:
        return None
    doc = await pending_col.find_one({"user_id": user_id})
    if doc is None:
        return None
    return doc.get("action")

async def clear_pending_action(user_id):
    if pending_col:
        await pending_col.delete_one({"user_id": user_id})

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    name = user.first_name if user else "Sweetheart"
    text = (
        f"✨ Hey *{name}* — I'm your romantic bot 💞\n\n"
        "Tumhare liye files forward karne ke liye ready hoon 💋"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💖 Contact Me", url=f"https://t.me/{BOT_CREDIT.lstrip('@')}")]
        ]
    )
    await fast_send(client, message.chat.id, text, parse_mode="markdown_v2", reply_markup=keyboard)
    if users_col:
        await users_col.update_one({"user_id": user.id},{"$set":{"last_active":datetime.utcnow()}},upsert=True)

# ---------------- HELP ----------------
@app.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    txt = (
        "📘 *Help Menu*\n\n"
        "/start — Start bot 💞\n"
        "/alive — Check if bot is alive 🔥\n"
        "/addchannel — Add source channel ➕ (Owner only)\n"
        "/reset — Remove all added source channels ❌ (Owner only)\n"
        "/broadcast <text> — Send message to all users 📣 (Owner only)\n"
        "/restart — Restart bot 🔄 (Owner only)\n"
        "/cancel — Cancel pending action ❌\n"
        "/ban <user_id> — Ban a user 🚫 (Owner only)\n"
        "/unban <user_id> — Unban user 🔓 (Owner only)"
    )
    await fast_send(client, message.chat.id, txt, parse_mode="markdown_v2")

# ---------------- ALIVE ----------------
@app.on_message(filters.command("alive"))
async def alive_cmd(client: Client, message: Message):
    await fast_send(client, message.chat.id, "🔥 Alive and ready for you 💋")

# ---------------- RESTART ----------------
@app.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def restart_cmd(client: Client, message: Message):
    await fast_send(client, message.chat.id, "🔄 Restarting baby…")
    os.system("kill 1")

# ---------------- CANCEL ----------------
@app.on_message(filters.command("cancel"))
async def cancel_cmd(client: Client, message: Message):
    await clear_pending_action(message.from_user.id)
    await fast_send(client, message.chat.id, "❌ Cancelled action")

# ---------------- ADD CHANNEL ----------------
@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def addchannel_start(client: Client, message: Message):
    if len(SOURCE_CHANNELS)>=MAX_SOURCE_CHANNELS:
        await fast_send(client,message.chat.id,f"❌ Maximum {MAX_SOURCE_CHANNELS} channels already added!")
        return
    await set_pending_action(message.from_user.id,"await_channel_id")
    await fast_send(client,message.chat.id,"➕ Send the channel ID now ❤️")

@app.on_message(filters.command("reset") & filters.user(OWNER_ID))
async def reset_channels(client: Client, message: Message):
    global SOURCE_CHANNELS
    SOURCE_CHANNELS=[]
    await save_source_channels()
    await fast_send(client,message.chat.id,"✅ All source channels removed 💔")

# ---------------- PRIVATE MSG HANDLER ----------------
@app.on_message(filters.private & ~filters.command([]))
async def private_messages(client: Client, message: Message):
    user_id = message.from_user.id
    action = await get_pending_action(user_id)

    # Add channel flow
    if action=="await_channel_id" and user_id==OWNER_ID:
        text = message.text.strip()
        try:
            if text.startswith("@"):
                ch = await client.get_chat(text)
                cid = ch.id
            else:
                cid = int(text)
        except Exception as e:
            await fast_send(client,message.chat.id,f"❌ Invalid channel: {e}")
            await clear_pending_action(user_id)
            return
        if cid not in SOURCE_CHANNELS:
            SOURCE_CHANNELS.append(cid)
            await save_source_channels()
        await fast_send(client,message.chat.id,f"✅ Channel added: `{cid}`",parse_mode="markdown_v2")
        await clear_pending_action(user_id)
        return

    # File search in logs
    query = (message.text or "").strip().lower()
    if not query:
        return
    await fast_send(client,message.chat.id,"🔎 Searching…")
    found=[]
    async for m in client.get_chat_history(LOG_CHANNEL, limit=500):
        cap=(m.caption or "").lower() if m.caption else ""
        fname=""
        if m.document and getattr(m.document,"file_name",None):
            fname=m.document.file_name.lower()
        if m.video and getattr(m.video,"file_name",None):
            fname=m.video.file_name.lower()
        if query in cap or query in fname:
            found.append(m)
        if len(found)>=6:
            break
    if not found:
        await fast_send(client,message.chat.id,"😔 No files found baby…")
        return
    # Forward top results instantly
    for msg in found:
        try:
            await msg.forward(message.chat.id)
        except:
            pass

# ---------------- SOURCE CHANNEL ----------------
@app.on_message(filters.channel)
async def source_channel_forward(client: Client, message: Message):
    if message.chat.id not in SOURCE_CHANNELS:
        return
    try:
        await message.forward(LOG_CHANNEL)  # Save in logs
        # Optional: Forward to users if needed → delay 10s only for bulk
        await asyncio.sleep(10)
    except:
        pass

# ---------------- STARTUP ----------------
async def startup():
    await load_source_channels()
    print("Source Channels Loaded:", SOURCE_CHANNELS)

if __name__=="__main__":
    asyncio.get_event_loop().run_until_complete(startup())
    app.run()
