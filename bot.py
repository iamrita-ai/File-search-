import os
import asyncio
import logging
import aiofiles
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import zipfile
import pyzipper

# ENV
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 1598576202))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -1003286415377))
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", -1003392099253))

# Bot
app = Client("UnzipBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Webhook for Render deploy
flask_app = Flask(__name__)

# FORCE SUB CHECK FUNCTION
async def check_sub(chat_id):
    try:
        user = await app.get_chat_member(FORCE_SUB_CHANNEL, chat_id)
        if user.status in [enums.ChatMemberStatus.BANNED]: return False
        return True
    except Exception as e:
        return False

# /start
@app.on_message(filters.command("start"))
async def start_handler(c, m):
    if not await check_sub(m.from_user.id):
        btns = InlineKeyboardMarkup([[InlineKeyboardButton("Join Update Channel", url=f"https://t.me/c/{str(FORCE_SUB_CHANNEL)[4:]}")]])
        await m.reply("Join update channel to use!", reply_markup=btns)
        return
    await m.reply("👋 Hi! Send me any archive file and I will unzip it and DM you the files.\n/help for commands/details.")
    await c.send_message(LOG_CHANNEL, f"#START By {m.from_user.mention}({m.from_user.id})")

# /help
@app.on_message(filters.command("help"))
async def help_handler(c, m):
    helptext = (
        "**🟢 Unzip Bot Help:**\n"
        "- Send me ZIP/RAR/7z files.\n"
        "- After sending, use inline buttons:\n"
        "   • `Unzip`: unzip archive\n"
        "   • `Password`: for protected zips\n"
        "/broadcast <text>: owner only\n"
        "/status : Bot speed & user count\n"
        "Join: @UnzipextractRobot"
    )
    await m.reply(helptext)
    await c.send_message(LOG_CHANNEL, f"#HELP By {m.from_user.mention}({m.from_user.id})")

# /broadcast
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(c, m):
    if m.reply_to_message:
        txt = m.reply_to_message.text or m.reply_to_message.caption or ""
    else:
        txt = m.text.split(None, 1)[-1] if len(m.text.split()) > 1 else None
    if not txt: await m.reply("No message found!"); return
    users = []; failed = []
    async for dialog in app.get_dialogs():
        if dialog.chat.type == enums.ChatType.PRIVATE:
            try: await c.send_message(dialog.chat.id, txt)
            except: failed.append(dialog.chat.id)
            else: users.append(dialog.chat.id)
    await m.reply(f"Broadcast Done ✅\nSent to {len(users)} users.\nFailed: {len(failed)}")
    await c.send_message(LOG_CHANNEL, f"#BROADCAST By {m.from_user.mention} ({m.from_user.id})")

# /status
@app.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status_handler(c, m):
    import time, psutil
    start = time.perf_counter(); await c.get_me(); ping = time.perf_counter() - start
    users = 0
    async for dialog in app.get_dialogs():
        if dialog.chat.type == enums.ChatType.PRIVATE: users += 1
    info = (
        f"**Bot Status**:\n"
        f"Uptime: N/A\n"
        f"Active Users: {users}\n"
        f"Ping: {ping*1000:.3f} ms\n"
        f"CPU: {psutil.cpu_percent()}%\n"
        f"RAM: {psutil.virtual_memory().percent}%"
    )
    await m.reply(info)
    await c.send_message(LOG_CHANNEL, f"#STATUS By {m.from_user.mention} ({m.from_user.id})")

# Document handler: send unzip buttons
@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    if not await check_sub(m.from_user.id):
        btns = InlineKeyboardMarkup([[InlineKeyboardButton("Join Update Channel", url=f"https://t.me/c/{str(FORCE_SUB_CHANNEL)[4:]}")]])
        await m.reply("Join update channel to use!", reply_markup=btns)
        return
    fname = m.document.file_name
    kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Unzip", callback_data=f"unzip|{m.document.file_id}|"),
            InlineKeyboardButton("Password", callback_data=f"pass|{m.document.file_id}|")
        ]])
    await m.reply("Kya karna hai?", reply_markup=kb)
    await c.send_message(LOG_CHANNEL, f"#DOC By {m.from_user.mention} ({m.from_user.id}) SENT: {fname}")

# Callback query: Unzip/Password
@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split('|')
    if data[0] == "unzip":
        file_id = data[1]
        passwd = data[2]
        await q.answer("Extracting...", show_alert=True)
        await do_unzip(c, q, file_id, passwd)
    elif data[0] == "pass":
        await q.message.reply("Send me password like:\n`/pass your_password`")

# /pass command reply
@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None, 1)[-1]
    if len(passwd) < 1: return await m.reply("Invalid password!")
    r = m.reply_to_message
    # Find original file_id from buttons (from reply attached to doc)
    if r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("unzip|"):
                    file_id = btn.callback_data.split('|')[1]
                    kb = InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("Unzip", callback_data=f"unzip|{file_id}|{passwd}"),
                        ]])
                    await r.edit_reply_markup(reply_markup=kb)
                    await m.reply("Password set. Tap Unzip to proceed.")
                    return

# Unzip logic
async def do_unzip(c, cbq, file_id, passwd):
    uid = cbq.from_user.id
    try:
        f = await c.download_media(file_id, file_name=f"zips/{uid}.zip")
        result, err = [], []
        # Try extract
        try:
            if passwd:
                with pyzipper.AESZipFile(f, 'r') as zipped:
                    zipped.pwd = passwd.encode()
                    names = zipped.namelist()
                    for name in names:
                        outp = f"unzipped/{uid}_{os.path.basename(name)}"
                        await aio_save(zipped, name, outp)
                        await c.send_document(uid, outp)
                        result.append(name)
            else:
                with zipfile.ZipFile(f, 'r') as zipped:
                    for name in zipped.namelist():
                        outp = f"unzipped/{uid}_{os.path.basename(name)}"
                        with zipped.open(name) as src, open(outp, "wb") as dst: dst.write(src.read())
                        await c.send_document(uid, outp)
                        result.append(name)
            await c.send_message(uid, f"✅ Extracted: {len(result)} file(s) done!")
            await c.send_message(LOG_CHANNEL, f"#UNZIP By {cbq.from_user.mention} {file_id}\nExtracted: {result}")
            await cbq.message.reply("Unzipped Done ✅")
        except Exception as e:
            logger.error(e)
            await c.send_message(uid, f"❌ Failed: {e}")
    except Exception as e:
        logger.error(e)
        await cbq.message.reply("Error processing!")

async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

# Flask Render web service route
@flask_app.route("/", methods=["GET", "POST"])
def ping():
    return "Running Telegram Unzip Bot!", 200

# ---- RENDER/WEBHOOK RUN ----
def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == "__main__":
    run()
