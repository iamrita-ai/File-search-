# bot.py — Final stable version for Render (Python 3.13, PyMongo)
import os
import re
import time
import threading
import traceback
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# -------------------------- CONFIG --------------------------
OWNER_ID = 1598576202                 # hard-coded as requested
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID")) if os.getenv("API_ID") else None
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")  # exact name as you asked
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL")) if os.getenv("LOG_CHANNEL") else None

# Quick env validation (fail early with clear message)
missing = []
if not BOT_TOKEN:
    missing.append("BOT_TOKEN")
if API_ID is None:
    missing.append("API_ID")
if not API_HASH:
    missing.append("API_HASH")
if not MONGO_DB_URI:
    missing.append("MONGO_DB_URI")

if missing:
    raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

# -------------------------- DB (synchronous pymongo) --------------------------
mongo = MongoClient(MONGO_DB_URI)
db = mongo.get_database("SerenaBotDB")
users_col = db.get_collection("Users")
config_col = db.get_collection("Config")
files_col = db.get_collection("Files")
premium_col = db.get_collection("Premium")
bans_col = db.get_collection("Bans")

# -------------------------- APP (Pyrogram) --------------------------
app = Client("SerenaRomanticBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------------- GLOBALS --------------------------
SOURCE_CHANNELS = []  # loaded from DB on startup
MAX_SOURCES = 3

# Anti-spam simple in-memory counters (reset every minute by background thread)
spam_counters = {}
SPAM_LIMIT = 8
SPAM_RESET_SECONDS = 60

# Auto-delete config (bot messages will be deleted after X seconds if >0)
AUTO_DELETE_SECONDS = 0  # set >0 to enable auto-delete of bot replies


# -------------------------- UTILITIES --------------------------
def romantic_confirmation():
    msgs = [
        "Ho gaya Sweetheart 😘",
        "Done meri jaan ❤️",
        "Bas tum bolo, main kar doongi 💋",
        "Tumhara kaam ho gaya, muskurado 🥹"
    ]
    return msgs[int(time.time()) % len(msgs)]


def safe_print_exc(prefix="Error"):
    print(prefix)
    traceback.print_exc()


def save_config_to_db():
    config_col.update_one({"_id": "main"}, {"$set": {"sources": SOURCE_CHANNELS, "log_channel": LOG_CHANNEL}}, upsert=True)


def load_config_from_db():
    global SOURCE_CHANNELS, LOG_CHANNEL
    doc = config_col.find_one({"_id": "main"})
    if doc:
        SOURCE_CHANNELS = doc.get("sources", [])
        if doc.get("log_channel"):
            LOG_CHANNEL = doc.get("log_channel")


def schedule_delete(chat_id, message_id, delay_seconds):
    if not delay_seconds or delay_seconds <= 0:
        return
    def worker():
        time.sleep(delay_seconds)
        try:
            app.delete_messages(chat_id, message_id)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


def db_store_file(log_msg_id, caption, filename, original_chat_id, original_msg_id):
    try:
        files_col.insert_one({
            "log_chat_id": LOG_CHANNEL,
            "log_msg_id": int(log_msg_id),
            "caption": (caption or ""),
            "filename": (filename or ""),
            "original_chat_id": int(original_chat_id),
            "original_msg_id": int(original_msg_id),
            "ts": datetime.utcnow()
        })
    except Exception:
        safe_print_exc("db_store_file error")


# -------------------------- BACKGROUND TASKS --------------------------
def spam_reset_worker():
    while True:
        time.sleep(SPAM_RESET_SECONDS)
        spam_counters.clear()


threading.Thread(target=spam_reset_worker, daemon=True).start()

# -------------------------- FLASK for Render (port binding) --------------------------
def run_flask_server():
    # import here to avoid heavy dependency unless used
    try:
        from flask import Flask
        flask_app = Flask("serena_healthcheck")

        @flask_app.route("/")
        def index():
            return "Serena Bot is running ❤️"

        port = int(os.environ.get("PORT", "10000"))  # Render injects PORT
        flask_app.run(host="0.0.0.0", port=port, threaded=True)
    except Exception:
        safe_print_exc("Flask server failed")


threading.Thread(target=run_flask_server, daemon=True).start()


# -------------------------- STARTUP (load config) --------------------------
load_config_from_db()


# -------------------------- COMMANDS --------------------------
@app.on_message(filters.command("start"))
def cmd_start(client, message):
    try:
        user = message.from_user
        if user:
            users_col.update_one({"user_id": user.id}, {"$set": {"first_name": user.first_name, "last_seen": datetime.utcnow()}}, upsert=True)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Owner", url="https://t.me/technicalSerena")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
        ])

        sent = client.send_message(message.chat.id,
                                   f"💖 Hey {user.first_name or 'Sweetheart'} — I'm your romantic bot. Use /help to see commands.\n\n{romantic_confirmation()}",
                                   reply_markup=keyboard)
        # auto-delete if configured
        if AUTO_DELETE_SECONDS > 0:
            # sent is a future-like — get message_id after result; but here send_message returns Message
            try:
                sent_msg = sent.result() if hasattr(sent, "result") else sent
                schedule_delete(message.chat.id, sent_msg.message_id, AUTO_DELETE_SECONDS)
            except Exception:
                pass
    except Exception:
        safe_print_exc("start command error")


@app.on_message(filters.command("help"))
def cmd_help(client, message):
    try:
        text = (
            "📘 *Help Menu*\n\n"
            "/start — Romantic welcome\n"
            "/help — This help message\n"
            "/setting — Open settings (or press Settings button)\n"
            "/addchannel <id|@username> — Add source channel (Owner only, max 3)\n"
            "/resetchannel — Remove all sources (Owner only)\n"
            "/setlog <id|@username> — Set log channel (Owner only)\n"
            "/clear — Clear DB (Owner only)\n"
            "/broadcast — Reply to a message with /broadcast to send to all users (Owner only)\n"
            "/ban <user_id> — Ban user (Owner only)\n"
            "/unban <user_id> — Unban user (Owner only)\n"
            "/premium add/remove/check <user_id> — Manage premium (Owner only)\n\n"
            "To search: send any part of the file name or caption in private chat with me — I'll send matches."
        )
        client.send_message(message.chat.id, text)
    except Exception:
        safe_print_exc("help command error")


@app.on_message(filters.command("setlog") & filters.user(OWNER_ID))
def cmd_setlog(client, message):
    global LOG_CHANNEL
    try:
        if len(message.command) >= 2:
            arg = message.command[1].strip()
            if arg.startswith("@"):
                chat = client.get_chat(arg)
                LOG_CHANNEL = int(chat.id)
            else:
                LOG_CHANNEL = int(arg)
            save_config_to_db()
            client.send_message(message.chat.id, f"✅ Log channel set to `{LOG_CHANNEL}`.\n{romantic_confirmation()}")
        else:
            client.send_message(message.chat.id, "Usage: /setlog <channel_id or @username>")
    except Exception as e:
        safe_print_exc("setlog error")
        client.send_message(message.chat.id, f"Error setting log channel: {e}")


@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
def cmd_addchannel(client, message):
    try:
        if len(SOURCE_CHANNELS) >= MAX_SOURCES:
            return client.send_message(message.chat.id, f"❌ Max {MAX_SOURCES} source channels already added.")
        if len(message.command) >= 2:
            arg = message.command[1].strip()
            if arg.startswith("@"):
                ch = client.get_chat(arg)
                cid = int(ch.id)
            else:
                cid = int(arg)
            if cid not in SOURCE_CHANNELS:
                SOURCE_CHANNELS.append(cid)
                save_config_to_db()
            client.send_message(message.chat.id, f"✅ Source channel added: `{cid}`\n{romantic_confirmation()}")
        else:
            client.send_message(message.chat.id, "Usage: /addchannel <channel_id or @username>")
    except Exception:
        safe_print_exc("addchannel error")
        client.send_message(message.chat.id, "Failed to add channel. Make sure bot is member of that channel.")


@app.on_message(filters.command("resetchannel") & filters.user(OWNER_ID))
def cmd_resetchannel(client, message):
    try:
        SOURCE_CHANNELS.clear()
        save_config_to_db()
        client.send_message(message.chat.id, f"💔 All source channels removed.\n{romantic_confirmation()}")
    except Exception:
        safe_print_exc("resetchannel error")
        client.send_message(message.chat.id, "Failed to reset channels.")


@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
def cmd_clear(client, message):
    try:
        # remove contents of collections (not drop DB)
        files_col.delete_many({})
        users_col.delete_many({})
        premium_col.delete_many({})
        bans_col.delete_many({})
        client.send_message(message.chat.id, "🗑️ All collections cleared from database.")
    except Exception:
        safe_print_exc("clear error")
        client.send_message(message.chat.id, "Clear failed.")


@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
def cmd_broadcast(client, message):
    try:
        if not message.reply_to_message:
            return client.send_message(message.chat.id, "Reply to a message with /broadcast to send it to all users.")
        sent = 0
        for u in users_col.find({}, {"user_id": 1}):
            try:
                message.reply_to_message.copy(int(u["user_id"]))
                sent += 1
            except Exception:
                pass
        client.send_message(message.chat.id, f"📣 Broadcast attempted to {sent} users.\n{romantic_confirmation()}")
    except Exception:
        safe_print_exc("broadcast error")
        client.send_message(message.chat.id, "Broadcast failed.")


@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
def cmd_ban(client, message):
    try:
        if len(message.command) < 2:
            return client.send_message(message.chat.id, "Usage: /ban <user_id>")
        uid = int(message.command[1])
        bans_col.update_one({"user_id": uid}, {"$set": {"banned": True}}, upsert=True)
        client.send_message(message.chat.id, f"🚫 User {uid} banned.\n{romantic_confirmation()}")
    except Exception:
        safe_print_exc("ban error")
        client.send_message(message.chat.id, "Ban failed.")


@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
def cmd_unban(client, message):
    try:
        if len(message.command) < 2:
            return client.send_message(message.chat.id, "Usage: /unban <user_id>")
        uid = int(message.command[1])
        bans_col.delete_one({"user_id": uid})
        client.send_message(message.chat.id, f"🔓 User {uid} unbanned.\n{romantic_confirmation()}")
    except Exception:
        safe_print_exc("unban error")
        client.send_message(message.chat.id, "Unban failed.")


@app.on_message(filters.command("premium") & filters.user(OWNER_ID))
def cmd_premium(client, message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            return client.send_message(message.chat.id, "Usage: /premium add/remove/check <user_id>")
        action = parts[1].lower()
        uid = int(parts[2])
        if action == "add":
            premium_col.update_one({"user_id": uid}, {"$set": {"premium": True}}, upsert=True)
            client.send_message(message.chat.id, f"⭐ User {uid} marked premium.")
        elif action == "remove":
            premium_col.delete_one({"user_id": uid})
            client.send_message(message.chat.id, f"❌ Premium removed for {uid}.")
        elif action == "check":
            doc = premium_col.find_one({"user_id": uid})
            client.send_message(message.chat.id, f"Premium: {'Yes' if doc else 'No'}")
        else:
            client.send_message(message.chat.id, "Unknown action. Use add/remove/check.")
    except Exception:
        safe_print_exc("premium error")
        client.send_message(message.chat.id, "Premium command failed.")


# -------------------------- SETTINGS BUTTON (callback) --------------------------
@app.on_callback_query(filters.regex(r"settings_menu"))
def cb_settings_menu(client, cq):
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Source Channel", callback_data="settings_add")],
            [InlineKeyboardButton("🧹 Reset Channels", callback_data="settings_reset")],
            [InlineKeyboardButton("📄 Set Log Channel", callback_data="settings_setlog")],
            [InlineKeyboardButton("❌ Close", callback_data="settings_close")],
            [InlineKeyboardButton("💌 Owner", url="https://t.me/technicalSerena")]
        ])
        cq.answer()
        cq.message.edit_text("⚙️ Settings Menu", reply_markup=kb)
    except Exception:
        safe_print_exc("settings menu cb")


@app.on_callback_query(filters.regex(r"settings_close"))
def cb_settings_close(client, cq):
    try:
        cq.answer()
        cq.message.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"settings_reset"))
def cb_settings_reset(client, cq):
    try:
        SOURCE_CHANNELS.clear()
        save_config_to_db()
        cq.answer("Reset done")
        cq.message.edit_text("✅ All source channels removed.")
    except Exception:
        safe_print_exc("settings_reset cb")


@app.on_callback_query(filters.regex(r"settings_add"))
def cb_settings_add(client, cq):
    try:
        cq.answer()
        # instruct owner to send /addchannel in private or here
        cq.message.edit_text("Send /addchannel <id|@username> to add a source channel (owner only).")
    except Exception:
        safe_print_exc("settings_add cb")


@app.on_callback_query(filters.regex(r"settings_setlog"))
def cb_settings_setlog(client, cq):
    try:
        cq.answer()
        cq.message.edit_text("Send /setlog <id|@username> to set the log channel (owner only).")
    except Exception:
        safe_print_exc("settings_setlog cb")


# -------------------------- SOURCE CHANNEL HANDLER --------------------------
@app.on_message(filters.channel)
def on_source_channel_message(client, message):
    try:
        # if SOURCE_CHANNELS configured, skip other channels
        if SOURCE_CHANNELS and (message.chat.id not in SOURCE_CHANNELS):
            return

        # copy to LOG_CHANNEL if set
        if LOG_CHANNEL:
            copied = client.copy_message(LOG_CHANNEL, from_chat_id=message.chat.id, message_id=message.id)
            # copied is a Message object; get its id
            log_msg_id = copied.message_id if hasattr(copied, "message_id") else (copied.id if hasattr(copied, "id") else None)
            caption = message.caption or ""
            filename = ""
            if message.document and getattr(message.document, "file_name", None):
                filename = message.document.file_name
            elif message.video and getattr(message.video, "file_name", None):
                filename = message.video.file_name
            # store metadata in DB
            if log_msg_id:
                db_store_file(log_msg_id, caption, filename, message.chat.id, message.id)
            # optional short announcement in log (reply to the copied message)
            try:
                client.send_message(LOG_CHANNEL, "✔ File saved to logs.", reply_to_message_id=log_msg_id)
            except Exception:
                pass

        # delay for bulk protection (sleep in thread to not block)
        def delayed_pause():
            time.sleep(10)
        threading.Thread(target=delayed_pause, daemon=True).start()

    except Exception:
        safe_print_exc("on_source_channel_message error")
        # optionally notify admin in LOG_CHANNEL
        if LOG_CHANNEL:
            try:
                client.send_message(LOG_CHANNEL, "❌ Error while saving source message.")
            except:
                pass


# -------------------------- USER PRIVATE SEARCH (matching contains) --------------------------
@app.on_message(filters.private & filters.text & ~filters.command(["start", "help", "setlog", "addchannel", "resetchannel", "clear", "broadcast", "ban", "unban", "premium"]))
def on_user_search(client, message):
    try:
        user_id = message.from_user.id
        # check banned
        if bans_col.find_one({"user_id": user_id}):
            return client.send_message(message.chat.id, "You are banned.")

        # simple spam check
        now = time.time()
        cnt = spam_counters.get(user_id, [])
        # purge entries older than SPAM_RESET_SECONDS
        cnt = [t for t in cnt if now - t < SPAM_RESET_SECONDS]
        cnt.append(now)
        spam_counters[user_id] = cnt
        if len(cnt) > SPAM_LIMIT:
            return client.send_message(message.chat.id, "Too many requests — slow down baby ❤️")

        query = message.text.strip()
        if not query:
            return client.send_message(message.chat.id, "Send part of the file name or caption to search.")

        # search DB files collection (case-insensitive contains)
        regex = re.compile(re.escape(query), re.IGNORECASE)
        docs = list(files_col.find({"$or": [{"caption": {"$regex": regex}}, {"filename": {"$regex": regex}}]}).sort("ts", -1).limit(6))

        if not docs:
            return client.send_message(message.chat.id, "😔 No matches found, try different keywords.")

        client.send_message(message.chat.id, f"🔎 Found {len(docs)} result(s) — sending top results…")
        sent = 0
        # copy messages from LOG_CHANNEL to user (removes forward header)
        for d in docs:
            try:
                log_msg_id = int(d.get("log_msg_id"))
                client.copy_message(message.chat.id, LOG_CHANNEL, log_msg_id)
                sent += 1
                time.sleep(0.6)
            except Exception:
                pass

        client.send_message(message.chat.id, f"✅ Sent {sent} files. {romantic_confirmation()} \n— @technicalSerena")
    except Exception:
        safe_print_exc("on_user_search error")
        try:
            if LOG_CHANNEL:
                client.send_message(LOG_CHANNEL, "❌ Error in user search handler.")
        except:
            pass


# -------------------------- RUN --------------------------
if __name__ == "__main__":
    print("Starting bot... Flask healthcheck thread started, now starting Pyrogram client.")
    app.run()
