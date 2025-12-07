import os, time, logging, aiofiles, zipfile, pyzipper, secrets, psutil, shutil, requests, random, math, asyncio, re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from pymongo import MongoClient

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "-1003286415377")
OWNER_ID = int(os.environ.get("OWNER_ID"))
MONGO_URL = os.environ.get("MONGO_URL")
GPT_API_KEY = os.environ.get("GPT_API_KEY")
FORCE_CHANNEL = "serenaunzipbot"

mdb = MongoClient(MONGO_URL)["unzipbot"]
users_db = mdb["users"]
sessions_db = mdb["sessions"]
blocked_db = mdb["blocked"]
settings_db = mdb["settings"]

EMOJIS = ["😉","🥹","✨","🚀","🪄","🦄","🥰","😚","🎵","🛝","💃","🌈"]

ANIMATED = [
    "😉","🥰","🤗","✨","🚀","🦋","🌈","🦄","😚","🥹"
]

def animated_emoji(stage, time_stamp):
    # Rotate emoji every 1s by stage/time
    idx = int(time_stamp*2) % len(ANIMATED)
    return ANIMATED[idx]

logging.basicConfig(level=logging.INFO)
app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

def emoji(): return random.choice(EMOJIS)
def make_token(n=6): return secrets.token_hex(n)

CANCELLED_SESSIONS = set()

def get_force_btns():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Join Update Channel", url="https://t.me/serenaunzipbot")],
        [InlineKeyboardButton("👤 Contact Owner", url="https://t.me/TechnicalSerena")]
    ])

async def check_force_join(uid):
    try:
        member = await app.get_chat_member(FORCE_CHANNEL, uid)
        return member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except Exception:
        return False

async def gated_reply(m, txt, btns=None):
    # Force join
    if not await check_force_join(m.from_user.id):
        await m.reply("Pehle update channel join karo baby! Tab kaam chalega " + emoji(), reply_markup=get_force_btns())
        return "no_join"
    users_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id, "last_active": int(time.time())}}, upsert=True)
    return await m.reply(txt, reply_markup=btns)

def circle_progress_bar(cur, total, stage, start_time):
    percent = 0 if total == 0 else cur / total
    size = 20
    pos = int(size * percent)
    line = ""
    bar_emoji = animated_emoji(stage, time.time() - start_time)
    for i in range(size):
        if i < pos:
            line += "●"
        else:
            line += "○"
    return f"[{line}] {bar_emoji}"

def format_time(secs):
    m, s = divmod(int(secs), 60)
    if m == 0:
        return f"{s}s"
    else:
        return f"{m}m, {s}s"

def pretty_progress(stage, fname, cur, total, start):
    percent = 0 if total == 0 else cur / total
    speed_val = (cur/max(time.time()-start,1))
    speed_mb = speed_val/1024/1024
    done_mb = cur/1024/1024
    total_mb = total/1024/1024
    rem = (total - cur)/(speed_val if speed_val>0 else 1)
    return (
        f"{stage}\n"
        f"{fname} to my server\n"
        f"{circle_progress_bar(cur, total, stage, start)}\n"
        f"◌Progress{animated_emoji(stage, time.time() - start)}:〘 {percent*100:.2f}% 〙\n"
        f"Done: 〘{done_mb:.1f} MB of  {total_mb:.2f} MB〙\n"
        f"◌Speed🚀:〘 {speed_mb:.2f} MB/s 〙\n"
        f"◌Time Left⏳:〘 {format_time(rem)} 〙"
    )

async def progress_for_pyro(current, total, msg, stage_data):
    (stage, start_time, token, fname) = stage_data
    text = pretty_progress(stage, fname, current, total, start_time)
    inline = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]])
    await msg.edit_text(text, reply_markup=inline)
    if token in CANCELLED_SESSIONS:
        raise asyncio.CancelledError("User cancelled")

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await gated_reply(m, "Hi baby! Mujhe ZIP/RAR ya DOC file bhejne ke baad main tumko har file ka extract option dungi. /help dekho details ke liye.")
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("help"))
async def help_cmd(c, m):
    txt = (
"🦋 *How it works:* 🦋\n\n"
"1️⃣  File (zip/rar) bhejo. Pehle sab files analyse hongi\n"
"2️⃣  Tumhe sab files ka naam milega — Extract ka button saath — ek-ek ya sabhi return\n"
"3️⃣  Progress hamesha emoji, speed, MB, time ke sath\n"
"4️⃣  Owner+tum dono ko file milegi, aap cancel bhi kar sakte ho\n"
"\n"
"━━━━━━━━━━━━━━━━━━━━━━━\n"
"/start  – Intro\n"
"/help   – Guide\n"
"/cancel – Cancel jobs\n"
"━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await gated_reply(m, txt, btns=get_force_btns())
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    user_id = m.from_user.id
    fname = m.document.file_name
    token = make_token()
    # Download and parse file list in temp
    tmp_dir = f"/tmp/{user_id}_{int(time.time())}"
    os.makedirs(tmp_dir+"/unzipped", exist_ok=True)
    tfile = os.path.join(tmp_dir, fname)
    msg = await gated_reply(m, f"Downloading started for `{fname}`\n\n{emoji()} Wait...", None)
    start_time = time.time()
    await c.download_media(
        m.document.file_id,
        file_name=tfile,
        progress=progress_for_pyro,
        progress_args=(msg, ("Downloading", start_time, token, fname))
    )
    # Parse files in archive
    try:
        filelist = []
        try:
            with zipfile.ZipFile(tfile) as zp:
                filelist = [f for f in zp.namelist() if not f.endswith("/")]
        except Exception:
            try:
                with pyzipper.AESZipFile(tfile) as zp:
                    filelist = [f for f in zp.namelist() if not f.endswith("/")]
            except Exception as ex:
                return await m.reply(f"File read error — is this a valid zip/rar?\n{ex}")
        files_map = {}
        for ix, fn in enumerate(filelist):
            btn_text = f"📂 {os.path.basename(fn)}"
            files_map[f"extract_{ix}"] = fn
        sessions_db.insert_one({
            "token": token,
            "file_id": m.document.file_id,
            "user_id": user_id,
            "tfile": tfile,
            "filelist": filelist,
            "files_map": files_map,
            "tmp_dir": tmp_dir
        })
        # === Inline list: extract file, extract all, cancel
        btn_rows = []
        emojilist = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟","🅰","🅱","🅾"]
        for ix, (key, fpath) in enumerate(files_map.items()):
            btn_rows.append(
                [InlineKeyboardButton(f"{emojilist[ix%len(emojilist)]} {os.path.basename(fpath)}",
                        callback_data=f"{key}|{token}")]
            )
        # ALL/CANCEL row
        btn_rows.append([
            InlineKeyboardButton("⬇️ Extract ALL", callback_data=f"extract_all|{token}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")
        ])
        await m.reply(
            f"Select file(s) to extract from `{fname}`\nहर file का नाम, button me hai — sabse pehle jo folder ka starting point hai uske above dikhega.",
            reply_markup=InlineKeyboardMarkup(btn_rows)
        )
        await c.send_message(LOG_CHANNEL, f"#ARCHIVELIST {m.from_user.mention} {fname} files: {len(filelist)}")
    except Exception as e:
        await m.reply("List nahi bana paaye, galat file ho sakti hai " + emoji())
        await c.send_message(LOG_CHANNEL, f"ERR archive parse: {e}")
        return

@app.on_callback_query()
async def extract_one_cbq(c, q):
    data = q.data.split("|")
    cmd, token = data[0], data[1]
    ses = sessions_db.find_one({"token": token})
    if not ses: 
        await q.message.reply("Session expired. Nayi file send karo baby!")
        return
    tmp_dir, tfile, filelist, files_map = ses["tmp_dir"], ses["tfile"], ses["filelist"], ses["files_map"]
    user_id = ses["user_id"]
    if cmd == "cancel":
        CANCELLED_SESSIONS.add(token)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await q.message.reply("Cancelled. Koi file extract nahi hogi. " + emoji())
        return
    # Extract ALL
    if cmd == "extract_all":
        for ix, fn in enumerate(filelist):
            await do_extract_file(c, q, tfile, fn, tmp_dir, token, user_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await q.message.reply("Sab files extract ho gayi " + emoji())
        return
    # Extract just one
    if cmd.startswith("extract_"):
        fn = files_map[cmd]
        await do_extract_file(c, q, tfile, fn, tmp_dir, token, user_id)
        await q.answer(f"{os.path.basename(fn)} extracted!", show_alert=True)

async def do_extract_file(c, cbq, tfile, filename, tmp_dir, token, uid):
    # Extraction progress bar
    exfile = os.path.join(tmp_dir, "unzipped", os.path.basename(filename))
    msg = await cbq.message.reply(f"Extracting: `{os.path.basename(filename)}` {emoji()}")
    start_time = time.time()
    # Extraction logic handle zip/pyzipper/password
    try:
        try:
            with zipfile.ZipFile(tfile) as zp:
                with zp.open(filename) as src, open(exfile, "wb") as dst:
                    total = zp.getinfo(filename).file_size
                    chunk, done = 1024*100, 0
                    while True:
                        data = src.read(chunk)
                        if not data: break
                        dst.write(data)
                        done += len(data)
                        await progress_for_pyro(done, total, msg, ("Extract", start_time, token, os.path.basename(filename)))
        except Exception:
            with pyzipper.AESZipFile(tfile) as zp:
                with zp.open(filename) as src, open(exfile, "wb") as dst:
                    total = zp.getinfo(filename).file_size
                    chunk, done = 1024*100, 0
                    while True:
                        data = src.read(chunk)
                        if not data: break
                        dst.write(data)
                        done += len(data)
                        await progress_for_pyro(done, total, msg, ("Extract", start_time, token, os.path.basename(filename)))
    except Exception as e:
        await cbq.message.reply(f"Extraction failed on {filename}: {e}")
        return
    # After extraction, upload to user + log channel
    await cbq.message.reply_document(exfile, caption=f"`{os.path.basename(filename)}`\nExtracted!", reply_to_message_id=cbq.message.id)
    await c.send_document(LOG_CHANNEL, exfile, caption=f"Extracted by {uid}: {os.path.basename(filename)}")
    os.remove(exfile)

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    for s in sessions_db.find({"user_id": m.from_user.id}):
        CANCELLED_SESSIONS.add(s["token"])
    await m.reply("Sab kaam cancel! Tum fir try karo, main yahin hoon " + emoji())
    await c.send_message(LOG_CHANNEL, f"#CANCEL {m.from_user.mention} {m.from_user.id}")

@flask_app.route("/", methods=["GET", "POST"])
def ping(): return "Serena multi-extract unzip bot up"

def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(
        host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
