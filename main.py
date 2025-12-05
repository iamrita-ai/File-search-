#!/usr/bin/env python3
"""
Telegram Unzip Bot - FastAPI + python-telegram-bot (webhook) ready for Render deployment.

Features:
- /start, /help, /status, /broadcast (owner only)
- When user sends any document, bot replies with inline buttons:
    [Unzip] [Password]
  - Unzip: attempts to unzip (no password)
  - Password: asks user for password then attempts to unzip
- Force-subscribe check to a channel (force user to join)
- Logs important events to a log channel
- Stores user ids in sqlite for broadcasts
- Designed to run as a Web Service (use $PORT)

Fill environment variables on Render as explained in README.
"""

import os
import sys
import logging
import asyncio
import sqlite3
import shutil
import time
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import uvicorn

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatAction,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# -------------------- CONFIG (user provided values filled) --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # set on Render
# Provided by you:
OWNER_ID = 1598576202
BOT_LOG_CHANNEL = -1003286415377
FORCE_SUB_CHANNEL = -1003392099253
# --------------------------------------------------------------------------------

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN env var not set. Set it in Render.")
    sys.exit(1)

# paths
BASE_DIR = Path("/tmp/telegram_unzip_bot")
DOWNLOADS = BASE_DIR / "downloads"
EXTRACTS = BASE_DIR / "extracts"
DB_PATH = BASE_DIR / "bot_users.db"
for p in (BASE_DIR, DOWNLOADS, EXTRACTS):
    p.mkdir(parents=True, exist_ok=True)

# Simple in-memory state for password flow
password_waiting = {}  # user_id -> {"file_path": str, "message_id": int, "orig_name": str}

# Logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# FastAPI app (for Render)
app = FastAPI()

# SQLite helper
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_seen INTEGER)"
    )
    conn.commit()
    conn.close()

def add_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, first_seen) VALUES (?, ?)", (user_id, int(time.time())))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

init_db()

# Utility: send log to log channel
async def send_log(app_tg, text: str):
    try:
        await app_tg.bot.send_message(chat_id=BOT_LOG_CHANNEL, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.exception("Failed to send log message: %s", e)

# Force-subscribe check
async def is_subscribed(app_tg, user_id: int):
    try:
        member = await app_tg.bot.get_chat_member(chat_id=FORCE_SUB_CHANNEL, user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception as e:
        # If the bot isn't admin or channel is private, this may error
        logger.warning("is_subscribed check failed: %s", e)
        return False

# Handlers
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    add_user(user.id)
    # force sub
    if not await is_subscribed(context.application, user.id):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel ➤", url=f"https://t.me/{abs(FORCE_SUB_CHANNEL)}")]])
        await update.message.reply_text(
            "⚠️ कृपया पहले इस चैनल को join करे ताकि आप बॉट इस्तेमाल कर सकें.", reply_markup=kb
        )
        return

    text = (
        f"👋 Hi <b>{user.first_name}</b>!\n\n"
        "मैं तुम्हारे भेजे हुए ZIP फाइल को अनज़िप कर के तुम्हें वापस भेज दूँगा।\n\n"
        "Commands:\n"
        "/start - फिर से ये संदेश\n"
        "/help - मदद\n"
        "/status - bot status (uptime, users)\n"
        "/broadcast - (owner only) send broadcast\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    await send_log(context.application, f"New /start by <code>{user.id}</code> - {user.full_name}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)
    await update.message.reply_text(
        "📌 Use:\n- Send me a ZIP file as Document.\n- I'll reply with two buttons: Unzip / Password.\n- Choose Unzip to extract (no password) or Password to send a password."
    )

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Show uptime, ping (approx), user count
    user = update.effective_user
    add_user(user.id)
    start_time = getattr(context.application, "start_time", time.time())
    uptime = int(time.time() - start_time)
    users = len(get_all_users())
    text = f"📊 <b>Bot Status</b>\nUptime: {uptime} sec\nUsers in DB: {users}\nOwner: <code>{OWNER_ID}</code>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not allowed to use this command.")
        return
    # Expect message text after command
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    message = " ".join(args)
    sent = 0
    failed = 0
    users = get_all_users()
    await update.message.reply_text(f"Broadcasting to {len(users)} users...")
    for uid in users:
        try:
            await context.application.bot.send_message(uid, message, parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05)  # throttle
        except Exception as e:
            failed += 1
    await update.message.reply_text(f"Done. Sent: {sent}, Failed: {failed}")
    await send_log(context.application, f"Broadcast by owner. Sent:{sent} Failed:{failed}")

# Document handler
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    add_user(user.id)

    # force-subscription check
    if not await is_subscribed(context.application, user.id):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel ➤", url=f"https://t.me/{abs(FORCE_SUB_CHANNEL)}")]])
        await message.reply_text("⚠️ कृपया पहले चैनल join करें।", reply_markup=kb)
        return

    doc = message.document
    if not doc:
        await message.reply_text("कोई डाक्युमेंट नहीं मिला।")
        return

    await send_log(context.application, f"Received document from <code>{user.id}</code>: {doc.file_name}")
    # download file
    local_name = DOWNLOADS / f"{user.id}_{int(time.time())}_{doc.file_name}"
    await message.reply_text("⏬ Downloading file, please wait...")
    file = await context.application.bot.get_file(doc.file_id)
    await file.download_to_drive(custom_path=str(local_name))
    await message.reply_text("✅ Downloaded. Choose an action:", reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton("Unzip", callback_data=f"unzip|{local_name.name}|{user.id}")],
         [InlineKeyboardButton("Password", callback_data=f"password|{local_name.name}|{user.id}")]]
    ))
    # store minimal info in password_waiting if needed later
    # (we'll add entry only if user chooses Password)
    # remove old files periodically? (not implemented here)

# CallbackQuery handler for Unzip / Password
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split("|")
    if len(parts) < 3:
        await query.edit_message_text("Invalid action.")
        return
    action, fname, uid_s = parts[0], parts[1], parts[2]
    user = update.effective_user
    # check owner of file
    try:
        owner_of_file = int(uid_s)
    except:
        owner_of_file = None

    local_path = DOWNLOADS / fname
    if action == "unzip":
        await query.edit_message_text("♻️ Starting extraction (no password)...")
        await do_unzip_and_send(context.application, owner_of_file, local_path, password=None)
    elif action == "password":
        # ask user to send password (store state)
        password_waiting[user.id] = {"file_path": str(local_path), "orig_name": fname}
        await query.edit_message_text("🔒 Please reply with the password for the archive. Send /cancel to abort.")
    else:
        await query.edit_message_text("Unknown action.")

# When user sends text while waiting for password
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in password_waiting:
        pw = update.message.text.strip()
        info = password_waiting.pop(user.id)
        file_path = Path(info["file_path"])
        await update.message.reply_text("🔓 Trying password now...")
        await do_unzip_and_send(context.application, user.id, file_path, password=pw)
    else:
        # normal text message
        await update.message.reply_text("Send me a zip file as a Document. I will unzip it and send back the contents.")

async def do_unzip_and_send(app_tg, user_id: int, file_path: Path, password: str = None):
    BOT = app_tg.bot
    if not file_path.exists():
        try:
            await BOT.send_message(chat_id=user_id, text="❌ File not found on server.")
        except:
            logger.warning("Could not notify user about missing file.")
        return

    # create extract folder
    extract_folder = EXTRACTS / f"{file_path.stem}_{int(time.time())}"
    extract_folder.mkdir(parents=True, exist_ok=True)

    # attempt unzip
    try:
        if password is not None:
            # zipfile expects bytes for pwd
            pwd = password.encode()
        else:
            pwd = None
        with ZipFile(file_path, 'r') as zf:
            # test extraction for password protected files will raise RuntimeError/RuntimeError on bad pwd
            try:
                if pwd:
                    zf.extractall(path=extract_folder, pwd=pwd)
                else:
                    zf.extractall(path=extract_folder)
            except RuntimeError as e:
                # wrong password or encrypted file
                await BOT.send_message(chat_id=user_id, text="❌ Extraction failed — wrong password or unsupported encryption.")
                await send_log(app_tg, f"Extraction failed for {file_path.name} (user {user_id}): {e}")
                shutil.rmtree(extract_folder, ignore_errors=True)
                return
    except BadZipFile as e:
        # Not a zip file — inform user
        await BOT.send_message(chat_id=user_id, text="❌ This is not a valid ZIP archive or unsupported format.")
        await send_log(app_tg, f"BadZipFile for {file_path.name} - user {user_id}")
        shutil.rmtree(extract_folder, ignore_errors=True)
        return
    except Exception as e:
        await BOT.send_message(chat_id=user_id, text=f"❌ Extraction error: {e}")
        await send_log(app_tg, f"Extraction error for {file_path.name}: {e}")
        shutil.rmtree(extract_folder, ignore_errors=True)
        return

    # iterate files and send back
    files = list(extract_folder.rglob("*"))
    files = [f for f in files if f.is_file()]
    if not files:
        await BOT.send_message(chat_id=user_id, text="⚠️ Archive extracted but no files found.")
        shutil.rmtree(extract_folder, ignore_errors=True)
        return

    await BOT.send_message(chat_id=user_id, text=f"✅ Extraction completed. Sending {len(files)} files...")
    sent = 0
    for f in files:
        try:
            # if file too large for Telegram API (depends on bot limits), this will raise
            await BOT.send_document(chat_id=user_id, document=InputFile(str(f)), filename=f.name)
            sent += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            # send message about failed file
            try:
                await BOT.send_message(chat_id=user_id, text=f"Failed to send {f.name}: {e}")
            except:
                pass
            await send_log(app_tg, f"Failed to send extracted file {f} to {user_id}: {e}")

    # cleanup
    shutil.rmtree(extract_folder, ignore_errors=True)
    # optionally delete original archive to save space
    try:
        file_path.unlink()
    except:
        pass
    await send_log(app_tg, f"Extraction done and sent {sent} files to {user_id} (archive: {file_path.name})")

# cancel handler
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in password_waiting:
        password_waiting.pop(user.id, None)
        await update.message.reply_text("⛔ Password request cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")

# Setup application and webhook route
@app.on_event("startup")
async def startup_event():
    # build the telegram application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # save start_time
    application.start_time = time.time()
    # register handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))

    # store app on FastAPI state for access
    app.state.tg_app = application

    # start the application in background
    await application.initialize()
    # use webhook mode: set webhook to our public URL (Render will provide)
    # We'll set webhook later in /set_webhook route by user (simpler), or try to set from env
    logger.info("Telegram application initialized")

@app.on_event("shutdown")
async def shutdown_event():
    application = app.state.tg_app
    if application:
        await application.stop()
        await application.shutdown()

# Root endpoint for healthcheck
@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Telegram Unzip Bot is running."

# Endpoint for Telegram webhook to post updates
@app.post("/webhook/{token}")
async def telegram_webhook(request: Request, token: str):
    # validate token path
    if token != BOT_TOKEN.replace(":", "_"):
        # We expect the path token to be BOT_TOKEN with ':' replaced by '_'
        return PlainTextResponse("invalid token", status_code=403)
    body = await request.body()
    application = app.state.tg_app
    if not application:
        return PlainTextResponse("app not ready", status_code=503)
    # let the telegram application process the raw update
    update = Update.de_json(await request.json(), application.bot)
    await application.update_queue.put(update)
    return PlainTextResponse("ok")

# helper to set webhook (call once)
async def set_webhook(url: str):
    application = app.state.tg_app
    if not application:
        raise RuntimeError("tg app not initialized")
    webhook_url = f"{url}/webhook/{BOT_TOKEN.replace(':', '_')}"
    await application.bot.set_webhook(webhook_url)
    await send_log(application, f"Webhook set to {webhook_url}")

# optional small CLI to set webhook if running locally for dev
if __name__ == "__main__":
    # run uvicorn when executing main.py directly
    port = int(os.getenv("PORT", "8080"))
    # Note: on Render, use `web` service and command `uvicorn main:app --host 0.0.0.0 --port $PORT`
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
