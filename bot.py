# bot.py
import os
import asyncio
import threading
from datetime import datetime
from typing import List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask

# ---------------- CONFIG (change only if you want defaults) ----------------
OWNER_ID = 1598576202
BOT_CREDIT = "@technicalserena"
MAX_SOURCE_CHANNELS = 3

# ENV (set these in Render environment variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID")) if os.getenv("API_ID") else None
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003286415377"))

# ---------------- MONGO (safe init) ----------------
mongo_client = AsyncIOMotorClient(MONGO_DB_URI) if MONGO_DB_URI is not None else None
db = mongo_client["TelegramBotDB"] if mongo_client is not None else None
users_col = db["Users"] if db is not None else None
config_col = db["Config"] if db is not None else None
pending_col = db["Pending"] if db is not None else None
files_col = db["Files"] if db is not None else None  # store metadata for search

# ---------------- PYROGRAM ----------------
app = Client("SerenaRomanticBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- FLASK (Render port) ----------------
flask_app = Flask("serena_dummy")


@flask_app.route("/")
def home():
    return "Serena Bot is alive ❤️"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_flask, daemon=True).start()

# ---------------- IN-MEMORY SOURCE LIST (loaded from DB on startup) ----------------
SOURCE_CHANNELS: List[int] = []


# ---------------- UTIL FUNCTIONS ----------------
async def fast_send(chat_id: int, text: str, **kwargs):
    return await app.send_message(chat_id, text, **kwargs)


async def slow_send(chat_id: int, text: str, delay: int = 10, **kwargs):
    msg = await app.send_message(chat_id, text, **kwargs)
    await asyncio.sleep(delay)
    return msg


# ---------------- DB HELPERS ----------------
async def load_source_channels():
    global SOURCE_CHANNELS
    if config_col is not None:
        cfg = await config_col.find_one({"_id": "source_channels"})
        if cfg is not None and isinstance(cfg.get("channels"), list):
            SOURCE_CHANNELS = cfg["channels"]
        else:
            # initialise if not present
            await config_col.update_one({"_id": "source_channels"}, {"$set": {"channels": SOURCE_CHANNELS}}, upsert=True)


async def save_source_channels():
    if config_col is not None:
        await config_col.update_one({"_id": "source_channels"}, {"$set": {"channels": SOURCE_CHANNELS}}, upsert=True)


async def set_pending(user_id: int, action: str):
    if pending_col is not None:
        await pending_col.update_one({"user_id": user_id}, {"$set": {"action": action, "ts": datetime.utcnow()}}, upsert=True)


async def get_pending(user_id: int) -> Optional[str]:
    if pending_col is None:
        return None
    doc = await pending_col.find_one({"user_id": user_id})
    return doc.get("action") if doc else None


async def clear_pending(user_id: int):
    if pending_col is not None:
        await pending_col.delete_one({"user_id": user_id})


# store file metadata when copying to LOG_CHANNEL
async def save_file_record(log_msg_id: int, caption: str, filename: Optional[str], original_chat: int, original_msg_id: int):
    if files_col is None:
        return
    doc = {
        "log_chat_id": LOG_CHANNEL,
        "log_msg_id": log_msg_id,
        "caption": caption or "",
        "filename": filename or "",
        "original_chat_id": original_chat,
        "original_msg_id": original_msg_id,
        "ts": datetime.utcnow(),
    }
    await files_col.insert_one(doc)


# ---------------- COMMANDS ----------------
@app.on_message(filters.command("start"))
async def cmd_start(_, message: Message):
    user = message.from_user
    name = (user.first_name or "Sweetheart")
    text = (
        f"💖 Hey *{name}* — main tumhari romantic bot hoon. 💞\n\n"
        "Tum mujhe kisi bhi file ka title bhejo — agar milla to turant bhej dungi. 😘\n\n"
        "Use /help to see commands."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💌 Contact Me", url=f"https://t.me/{BOT_CREDIT.lstrip('@')}")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
        ]
    )
    await fast_send(message.chat.id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    if users_col is not None:
        await users_col.update_one({"user_id": user.id}, {"$set": {"first_name": user.first_name, "last_seen": datetime.utcnow()}}, upsert=True)


@app.on_message(filters.command("help"))
async def cmd_help(_, message: Message):
    txt = (
        "📘 *Help Menu*\n\n"
        "/start — Start bot 💞\n"
        "/alive — Check if bot is alive 🔥\n"
        "/setting — Open settings menu ⚙️\n"
        "/addchannel — Add source channel ➕ (Owner only, max 3)\n"
        "/reset — Remove all source channels ❌ (Owner only)\n"
        "/broadcast <text> — Send message to all users 📣 (Owner only)\n"
        "/ban <user_id> — Ban a user 🚫 (Owner only)\n"
        "/unban <user_id> — Unban user 🔓 (Owner only)\n"
        "/clear — Clear DB (Owner only)\n"
        "/cancel — Cancel pending action\n\n"
        "📌 *How to search:* Send any part of the file title or caption to me in private — I will send matching files (matching contains)."
    )
    await fast_send(message.chat.id, txt, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("alive"))
async def cmd_alive(_, message: Message):
    await fast_send(message.chat.id, "🔥 I'm alive and listening for your sweet requests 💋")


@app.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def cmd_restart(_, message: Message):
    await fast_send(message.chat.id, "🔄 Restarting for you…")
    os._exit(0)


@app.on_message(filters.command("cancel"))
async def cmd_cancel(_, message: Message):
    await clear_pending(message.from_user.id)
    await fast_send(message.chat.id, "❌ All pending actions cancelled, meri jaan.")


@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cmd_clear(_, message: Message):
    if db is not None:
        coll_names = await db.list_collection_names()
        for c in coll_names:
            await db[c].delete_many({})
        await fast_send(message.chat.id, "🗑️ Database cleared. Sab kuch saf ho gaya ❤️")
    else:
        await fast_send(message.chat.id, "❌ Database not connected baby.")


@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def cmd_addchannel(_, message: Message):
    if len(SOURCE_CHANNELS) >= MAX_SOURCE_CHANNELS:
        await fast_send(message.chat.id, f"❌ Max {MAX_SOURCE_CHANNELS} sources already added.")
        return
    await set_pending(message.from_user.id, "await_add_channel")
    await fast_send(message.chat.id, "➕ Send the channel ID or @username now — I'll add it as source. 💖")


@app.on_message(filters.command("reset") & filters.user(OWNER_ID))
async def cmd_reset(_, message: Message):
    global SOURCE_CHANNELS
    SOURCE_CHANNELS = []
    await save_source_channels()
    await fast_send(message.chat.id, "💔 All source channels removed. Settings reset, meri jaan.")


@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def cmd_broadcast(_, message: Message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await fast_send(message.chat.id, "📣 Message text required.")
    count = 0
    if users_col is not None:
        async for u in users_col.find({}):
            try:
                await fast_send(u["user_id"], text)
                count += 1
            except:
                pass
    await fast_send(message.chat.id, f"📣 Broadcast sent to {count} users. ❤️")


@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def cmd_ban(_, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await fast_send(message.chat.id, "Usage: /ban <user_id>")
    try:
        uid = int(parts[1])
    except:
        return await fast_send(message.chat.id, "Invalid user id.")
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
    await fast_send(message.chat.id, f"🚫 User `{uid}` banned.", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def cmd_unban(_, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await fast_send(message.chat.id, "Usage: /unban <user_id>")
    try:
        uid = int(parts[1])
    except:
        return await fast_send(message.chat.id, "Invalid user id.")
    if users_col is not None:
        await users_col.update_one({"user_id": uid}, {"$set": {"banned": False}}, upsert=True)
    await fast_send(message.chat.id, f"🔓 User `{uid}` unbanned.", parse_mode=ParseMode.MARKDOWN)


# ---------------- SETTINGS MENU (callback) ----------------
@app.on_callback_query(filters.regex(r"settings_menu"))
async def cb_settings_menu(_, cq):
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add Source Channel", callback_data="settings_add")],
            [InlineKeyboardButton("🗑 Reset Settings", callback_data="settings_reset")],
            [InlineKeyboardButton("📄 Set Log Channel ID", callback_data="settings_set_log")],
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")]
        ]
    )
    await cq.answer()
    await cq.message.edit_text("⚙️ *Settings Menu*", parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"settings_close"))
async def cb_settings_close(_, cq):
    await cq.answer()
    try:
        await cq.message.delete()
    except:
        pass


@app.on_callback_query(filters.regex(r"settings_reset"))
async def cb_settings_reset(_, cq):
    await cq.answer("Resetting settings…")
    global SOURCE_CHANNELS
    SOURCE_CHANNELS = []
    await save_source_channels()
    await cq.message.edit_text("✅ Settings reset. All source channels removed. 💔")


@app.on_callback_query(filters.regex(r"settings_add"))
async def cb_settings_add(_, cq):
    await cq.answer()
    # start pending flow for owner
    await set_pending(cq.from_user.id, "await_add_channel")
    try:
        await cq.message.edit_text("➕ Send the channel ID or @username in chat with me (private).")
    except:
        pass


@app.on_callback_query(filters.regex(r"settings_set_log"))
async def cb_settings_set_log(_, cq):
    await cq.answer()
    await set_pending(cq.from_user.id, "await_set_log")
    try:
        await cq.message.edit_text("📄 Send the Log Channel ID now (in private chat with me).")
    except:
        pass


# ---------------- PRIVATE MESSAGE HANDLER (pending flows + search) ----------------
@app.on_message(filters.private & ~filters.command(["start", "help", "alive", "addchannel", "reset", "broadcast", "ban", "unban", "clear", "restart", "cancel"]))
async def private_handler(_, message: Message):
    user_id = message.from_user.id
    pending = await get_pending(user_id)

    # --- pending add channel ---
    if pending == "await_add_channel" and user_id == OWNER_ID:
        text = (message.text or "").strip()
        try:
            if text.startswith("@"):
                ch = await app.get_chat(text)
                cid = ch.id
            else:
                cid = int(text)
        except Exception as e:
            await fast_send(message.chat.id, f"❌ Invalid channel: {e}")
            await clear_pending(user_id)
            return
        if cid not in SOURCE_CHANNELS:
            SOURCE_CHANNELS.append(cid)
            await save_source_channels()
        await fast_send(message.chat.id, f"✅ Channel added: `{cid}`\nI'll start saving files from this channel. 💞", parse_mode=ParseMode.MARKDOWN)
        await clear_pending(user_id)
        return

    # --- pending set log ---
    if pending == "await_set_log" and user_id == OWNER_ID:
        text = (message.text or "").strip()
        try:
            if text.startswith("@"):
                ch = await app.get_chat(text)
                new_log = ch.id
            else:
                new_log = int(text)
        except Exception as e:
            await fast_send(message.chat.id, f"❌ Invalid log channel: {e}")
            await clear_pending(user_id)
            return
        # set global LOG_CHANNEL (and persist in config)
        global LOG_CHANNEL
        LOG_CHANNEL = new_log
        if config_col is not None:
            await config_col.update_one({"_id": "log_channel"}, {"$set": {"id": LOG_CHANNEL}}, upsert=True)
        await fast_send(message.chat.id, f"✅ Log channel set to `{LOG_CHANNEL}`. I'll save incoming files there. 😘", parse_mode=ParseMode.MARKDOWN)
        await clear_pending(user_id)
        return

    # --- otherwise: treat as a search query (matching contains) ---
    query = (message.text or "").strip().lower()
    if not query:
        return await fast_send(message.chat.id, "Please send a filename or keyword to search. 💋")

    # search files_col for 'contains' in caption or filename
    if files_col is None:
        return await fast_send(message.chat.id, "Search not available — DB disconnected.")
    await fast_send(message.chat.id, "🔎 Searching for matches…")
    cursor = files_col.find({
        "$or": [
            {"caption": {"$regex": query, "$options": "i"}},
            {"filename": {"$regex": query, "$options": "i"}}
        ]
    }).sort("ts", -1).limit(6)

    results = []
    async for doc in cursor:
        results.append(doc)

    if not results:
        return await fast_send(message.chat.id, "😔 No matching files found, try different keywords.")

    # copy matching messages from LOG_CHANNEL to user (removes forward tag)
    sent = 0
    for r in results:
        try:
            log_msg_id = r.get("log_msg_id")
            if log_msg_id:
                await app.copy_message(message.chat.id, LOG_CHANNEL, log_msg_id)
                sent += 1
                await asyncio.sleep(0.6)
        except Exception:
            pass

    await fast_send(message.chat.id, f"✅ Sent {sent} file(s). Tell me if you need more, meri jaan 💋")


# ---------------- SOURCE CHANNEL HANDLER (copy to LOG + save metadata) ----------------
@app.on_message(filters.channel)
async def on_source_channel_message(_, message: Message):
    # only respond if this channel is in SOURCE_CHANNELS (if list empty -> not configured)
    if len(SOURCE_CHANNELS) > 0 and message.chat.id not in SOURCE_CHANNELS:
        return

    try:
        # copy message into LOG_CHANNEL (copy => no forward header)
        copied = await app.copy_message(LOG_CHANNEL, message.chat.id, message.message_id)
        # extract caption and filename
        cap = message.caption or ""
        fname = ""
        if message.document and getattr(message.document, "file_name", None):
            fname = message.document.file_name
        elif message.video and getattr(message.video, "file_name", None):
            fname = message.video.file_name
        # save to DB for search later
        if files_col is not None:
            await save_file_record(copied.message_id, cap, fname, message.chat.id, message.message_id)
        # announce in log channel softly (optional)
        try:
            await app.send_message(LOG_CHANNEL, "✔ File saved to logs.", reply_to_message_id=copied.message_id)
        except:
            pass
        # delay only for bulk protection
        await asyncio.sleep(10)
    except Exception as e:
        # log to LOG_CHANNEL or ignore
        try:
            await app.send_message(LOG_CHANNEL, f"❌ Error saving message: {e}")
        except:
            pass


# ---------------- STARTUP TASKS ----------------
async def startup():
    # load persisted config
    if config_col is not None:
        cfg = await config_col.find_one({"_id": "log_channel"})
        if cfg and cfg.get("id"):
            global LOG_CHANNEL
            LOG_CHANNEL = cfg["id"]
    await load_source_channels()


if __name__ == "__main__":
    # run startup and then start bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(startup())
    print("Source channels loaded:", SOURCE_CHANNELS)
    app.run()
