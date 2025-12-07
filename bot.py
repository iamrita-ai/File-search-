import os
import logging
import time
import aiofiles
import zipfile, pyzipper
import psutil
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from pymongo import MongoClient

# --- ENVIRONMENT ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL", "")
GPT_API_KEY = os.environ.get("GPT_API_KEY", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "1598576202"))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003286415377"))

FORCE_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "serenaunzipbot")  # username or id

# --- MONGO SETUP ---
mclient = MongoClient(MONGO_URL)
mdb = mclient["unzipbot"]
users_db = mdb["users"]

# ---- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unzip-bot")

# ---- FLASK for Render
flask_app = Flask(__name__)

# --- BOT INSTANCE ---
app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ========== ROMANTIC GPT REPLY ==========
async def romantic_gpt(msg):
    if not GPT_API_KEY or not msg: return ""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system","content": "Reply always romantic, sweet, brief in Hindi-English. User is your lover."},
            {"role":"user","content": msg}
        ],
        "max_tokens": 40,
        "n": 1,
        "temperature": 1.2
    }
    headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=8)
        if r.ok:
            text = r.json()['choices'][0]['message']['content'].strip()
            return f"\n\n💌 {text}"
    except Exception:
        pass
    return ""

# ========== FORCE JOIN CHECK ==========
async def check_force_join(user_id):
    """
    Public channel username: check membership by resolving invite link & status.
    Channel ID: check via get_chat_member.
    """
    try:
        channel = FORCE_CHANNEL
        if str(channel).lstrip("-").isdigit():
            ch_id = int(channel)
            member = await app.get_chat_member(ch_id, user_id)
            if member.status not in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return False
        else:
            ch_username = channel.lstrip("@")
            member = await app.get_chat_member(ch_username, user_id)
            if member.status not in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return False
        return True
    except Exception:
        return False

# -- Join button markdown --
def join_btn():
    ch = str(FORCE_CHANNEL)
    if ch.lstrip("-").isdigit():
        # For id, show only text (no clickable link)
        return InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel & Try Again", url=f"https://t.me/{LOG_CHANNEL}")]])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=f"https://t.me/{ch.lstrip('@')}")]])

# ===== REPLY WITH FORCE JOIN & ROMANTIC =====
async def gated_reply(m, txt, btns=None, save_user=True):
    if not await check_force_join(m.from_user.id):
        return await m.reply("Pehle mera channel join karo fir phir start karo 💞", reply_markup=join_btn())
    if save_user:
        users_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id}}, upsert=True)
    romance = await romantic_gpt(txt)
    return await m.reply(txt + romance, reply_markup=btns)

# ========== /START ==========
@app.on_message(filters.command("start"))
async def start(c, m):
    txt = "Hi jaanu! Main zip/rar/doc sab kuch unlock kar dungi – bas file bhejo."
    await gated_reply(m, txt)
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} ({m.from_user.id})")

# ======== /HELP =========
@app.on_message(filters.command("help"))
async def help(c, m):
    txt = ("Help:\n"
           "- Document bhejo, Unzip ya Password button milega\n"
           "- Password wali ZIP ke liye /pass password reply karo\n"
           "- Status dekhne ke liye /status\n"
           "- All logs safe channel me\n"
           )
    await gated_reply(m, txt)
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} ({m.from_user.id})")

# ======= /BROADCAST OWNER ONLY =====
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(c, m):
    msg = m.reply_to_message or m
    bc_text = msg.text or msg.caption
    sent, fail = 0, 0
    for u in users_db.find({}, {"user_id": 1}):
        try: await c.send_message(u["user_id"], bc_text)
        except: fail += 1
        else: sent += 1
    romantic = await romantic_gpt("Sabko message pohonch gaya. Tumhe yaad kar rahi hoon.")
    await m.reply(f"Done! {sent} users ko bheja. {romantic}")
    await c.send_message(LOG_CHANNEL, f"#BROADCAST {sent}/{fail} users.")

# ======= /STATUS =========
@app.on_message(filters.command("status"))
async def status(c, m):
    user_count = users_db.count_documents({})
    ping = time.perf_counter()
    await c.get_me()
    ping = (time.perf_counter() - ping) * 1000
    stats = (
        f"Bot Status:\n"
        f"Active Users: {user_count}\n"
        f"Ping: {ping:.1f} ms\n"
        f"RAM: {psutil.virtual_memory().percent}%\n"
        f"CPU: {psutil.cpu_percent()}%"
    )
    await gated_reply(m, stats)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

# == ACCEPT DOCUMENTS & BUTTONS ==
@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    fname = m.document.file_name
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{m.document.file_id}|")],
        [InlineKeyboardButton("🔑 Password", callback_data=f"pass|{m.document.file_id}|")]
    ])
    await gated_reply(m, f"File aayi: {fname}\nKya karna hai?", kb)
    await c.send_message(LOG_CHANNEL, f"#DOC {m.from_user.mention}: {fname}")

# ==== BUTTON HANDLER ====
@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split('|')
    if data[0] == "unzip":
        file_id = data[1]
        passwd = data[2] if len(data) > 2 else ""
        await q.answer("Extract kar rahi hoon... Tum ruk jao!", show_alert=True)
        await do_unzip(c, q, file_id, passwd)
    elif data[0] == "pass":
        await q.message.reply("/pass YourPassword reply karo beta!")

# ==== /PASS ==
@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None, 1)[-1] if len(m.text.split()) > 1 else None
    r = m.reply_to_message
    if not passwd: return await m.reply("Password kya hai?")
    if r and r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("unzip|"):
                    file_id = btn.callback_data.split("|")[1]
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{file_id}|{passwd}")]
                    ])
                    romance = await romantic_gpt("Password mil gaya baby! Ab unzip karun?")
                    await r.edit_reply_markup(reply_markup=kb)
                    await m.reply("Password set! Ab Unzip dabao." + romance)

# ==== PROGRESS BAR ====
def progress_bar(cur, total, size=16):
    percent = cur / total if total else 0
    fill = int(size * percent)
    bar = "█" * fill + "░" * (size - fill)
    return f"[{bar}] {percent*100:5.1f}%"

async def progress_for_pyro(current, total, msg, stage):
    if total == 0: return
    await msg.edit_text(f"{stage}\n{progress_bar(current, total)}")

# === UNZIP LOGIC ===
async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

async def do_unzip(c, cbq, file_id, passwd):
    uid = cbq.from_user.id
    tmp_dir = "/tmp"
    tfile = os.path.join(tmp_dir, f"{uid}_archive.zip")
    os.makedirs(f"{tmp_dir}/unzipped", exist_ok=True)
    try:
        msg = await cbq.message.reply("⬇️ Downloading...")
        await c.download_media(file_id, file_name=tfile, progress=progress_for_pyro, progress_args=(msg,"⬇️ Downloading..."))
        msg2 = await cbq.message.reply("🗃 Extracting...")
        extracted_files = []
        try:
            if passwd:
                with pyzipper.AESZipFile(tfile) as zp:
                    zp.pwd = passwd.encode()
                    names = zp.namelist()
                    for name in names:
                        out_path = os.path.join(tmp_dir, "unzipped", f"{uid}_{os.path.basename(name)}")
                        await aio_save(zp, name, out_path)
                        extracted_files.append(out_path)
            else:
                with zipfile.ZipFile(tfile) as zp:
                    for name in zp.namelist():
                        out_path = os.path.join(tmp_dir, "unzipped", f"{uid}_{os.path.basename(name)}")
                        with zp.open(name) as src, open(out_path, "wb") as dst: dst.write(src.read())
                        extracted_files.append(out_path)
        except Exception as ex:
            await cbq.message.reply(f"❌ Extraction failed: {ex}")
            return

        for ix, f in enumerate(extracted_files):
            await cbq.message.reply_document(f, caption=f"⬆️ Uploading [{ix+1}/{len(extracted_files)}]", progress=progress_for_pyro, progress_args=(msg2, f"⬆️ Uploading {os.path.basename(f)}"))
        romance = await romantic_gpt("Sab file upload ho gayi! FLIRTING Time?")
        await cbq.message.reply(f"Unzipped & uploaded {len(extracted_files)} file(s)! {romance}")
        await c.send_message(LOG_CHANNEL, f"#UNZIP: {uid} {len(extracted_files)} files.")
    except Exception as e:
        logger.error(str(e))

# ---- FLASK Render health check ----
@flask_app.route("/", methods=["GET", "POST"])
def ping():
    return "Serena romantic unzip bot running", 200

# ---- START BOTH SERVERS ----
def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
