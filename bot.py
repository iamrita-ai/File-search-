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

EMOJIS = ["💪","💡","🦋","😎","✨","🚀","🛝","💃","🌈","🦄","😚"]

def emoji(): return random.choice(EMOJIS)
def make_token(n=6): return secrets.token_hex(n)
logging.basicConfig(level=logging.INFO)

app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

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

# ================ USER SETTINGS ================
def get_user_settings(uid):
    s = settings_db.find_one({"user_id": uid}) or {}
    return {
        "ai_mode": s.get("ai_mode", False),
        "unzip_mode": s.get("unzip_mode", True),   # True: Unzip, False: AI chat
        "replace_word": s.get("replace_word", [None, None])
    }

def set_user_setting(uid, k, v):
    settings_db.update_one({"user_id": uid}, {"$set":{k: v}}, upsert=True)

def reset_user_settings(uid):
    settings_db.delete_one({"user_id": uid})

def get_settings_btns(s):
    col1 = [
        InlineKeyboardButton(f"Unzip Mode: {'ON' if s['unzip_mode'] else 'OFF'}", callback_data=f"set_unzip|{int(not s['unzip_mode'])}"),
        InlineKeyboardButton(f"Ai Mode: {'ON' if s['ai_mode'] else 'OFF'}", callback_data=f"set_ai|{int(not s['ai_mode'])}")
    ]
    col2 = [
        InlineKeyboardButton("Replace Word", callback_data="replace_word"),
        InlineKeyboardButton("Reset Settings", callback_data="reset_setting")
    ]
    return InlineKeyboardMarkup([col1, col2])

@app.on_message(filters.command("settings"))
async def settings_cmd(c, m):
    s = get_user_settings(m.from_user.id)
    txt = (
        f"{emoji()} *Bot Settings*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• Unzip Mode: Extract archive files (default ON)\n"
        "• Ai Mode: only reply as AI (no file extraction)\n"
        "• Replace Word: Rename extracted files\n"
        "• Reset: Default settings\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await m.reply(txt, reply_markup=get_settings_btns(s))

@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split("|")
    token = data[1] if len(data)>1 else None

    # File related callbacks
    if data[0] in ("unzip", "pass", "cancel") and token is not None:
        session = sessions_db.find_one({"token": token})
        if not session: return await q.message.reply("Session expired. Nayi file send karo!")
        file_id = session.get("file_id")
        passwd = session.get("passwd", "")
        if data[0] == "unzip":
            userset = get_user_settings(q.from_user.id)
            if userset["unzip_mode"]:  # Unzip mode ON
                await do_unzip(c, q, file_id, passwd, token)
            else:
                await q.message.reply("Unzip mode OFF hai, pehle /settings se mode ON karo!")
        elif data[0] == "pass":
            sessions_db.update_one({"token":token}, {"$set": {"wait_pass":True}})
            await q.message.reply("Reply karo `/pass Password` as reply!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]]))
        elif data[0] == "cancel":
            CANCELLED_SESSIONS.add(token)
            await q.message.reply("Job Cancelled " + emoji())
        return

    # Settings callbacks
    if data[0] == "set_unzip":
        set_user_setting(q.from_user.id, "unzip_mode", bool(int(data[1])))
        s = get_user_settings(q.from_user.id)
        await q.message.edit_reply_markup(reply_markup=get_settings_btns(s))
    elif data[0] == "set_ai":
        set_user_setting(q.from_user.id, "ai_mode", bool(int(data[1])))
        s = get_user_settings(q.from_user.id)
        await q.message.edit_reply_markup(reply_markup=get_settings_btns(s))
    elif data[0] == "replace_word":
        await q.message.reply("Send new words like:\n`hello serena`\nFrom -> To (for file renaming).")
    elif data[0] == "reset_setting":
        reset_user_settings(q.from_user.id)
        await q.message.reply("Settings reset! Default mode now.")
        s = get_user_settings(q.from_user.id)
        await q.message.edit_reply_markup(reply_markup=get_settings_btns(s))

@app.on_message(filters.command("replace") & filters.reply)
async def replace_word_cmd(c, m):
    args = m.text.strip().split(None,2)
    if len(args)<3: return await m.reply("Use: /replace hello serena (reply on settings)")
    fromw, tow = args[1:3]
    set_user_setting(m.from_user.id, "replace_word", [fromw, tow])
    await m.reply(f"Saved! Files named '{fromw}' will rename to '{tow}'.")

CANCELLED_SESSIONS = set()

async def gated_reply(m, txt, btns=None, ai=True):
    if not await check_force_join(m.from_user.id):
        await m.reply("Pehle channel join karo! Tab kaam chalega " + emoji(), reply_markup=get_force_btns())
        return "no_join"
    users_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id, "last_active": int(time.time())}}, upsert=True)
    userset = get_user_settings(m.from_user.id)
    ai_mode = userset["ai_mode"]
    if ai and ai_mode:
        ai_reply = await romantic_gpt(txt, m.from_user.id)
        txt = txt + ("\n\n" + ai_reply if ai_reply else "")
    return await m.reply(txt, reply_markup=btns)

def circle_progress_bar(cur, total, stage, start_time):
    percent = 0 if total == 0 else cur / total
    size = 20
    pos = int(size * percent)
    line = ""
    emj = emoji()
    for i in range(size):
        if i < pos:
            line += "●"
        else:
            line += "○"
    return f"[{line}] {emj}"

def format_time(secs):
    m, s = divmod(int(secs), 60)
    return f"{m}m, {s}s" if m else f"{s}s"

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
        f"◌Progress:〘 {percent*100:.2f}% 〙\n"
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
    await gated_reply(m, 
        "Welcome! ZIP/RAR/DOC files bhejo, buttons milenge extract ke liye. Archive Extract mode default ON hai (change in /settings). /help dekho aur owner/channel ke buttons below.",
        btns=get_force_btns(), ai=False)
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("help"))
async def help_cmd(c, m):
    txt = (
f"{emoji()} *Serena UnzipBot* {emoji()}\n\n"
"━━━━━━━━━━━━━━━━━━━━━━━\n"
"• Send ZIP/RAR files — Get extract/cancel buttons\n"
"• Extract individual files or all at once\n"
"• Progress bar shows %/MB/s/time/emoji\n"
"• Archive mode ON: Bot file extract kare (change mode in /settings)\n"
"• AI mode ON: Only chat, no extraction\n"
"• Reset/replace file word supported\n"
"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
"/start – Welcome\n"
"/help – Guide\n"
"/settings – User panel\n"
"/cancel – Cancel jobs\n"
"/status (owner) – Bot stats\n"
"/broadcast (owner) – Message to all users\n"
"━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await gated_reply(m, txt, btns=get_force_btns(), ai=False)
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    for s in sessions_db.find({"user_id": m.from_user.id}):
        CANCELLED_SESSIONS.add(s["token"])
    await m.reply("Sab kaam cancel! Tum fir try karo, main yahin hoon " + emoji())
    await c.send_message(LOG_CHANNEL, f"#CANCEL {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def bc_cmd(c, m):
    msg = m.reply_to_message or m
    bc_text = msg.text or msg.caption
    sent, fail = 0, 0
    for u in users_db.find({}, {"user_id": 1}):
        try: await c.send_message(u["user_id"], bc_text); sent += 1
        except: fail += 1
    await m.reply(f"Broadcast done to {sent} users.\n{emoji()}")

@app.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status_cmd(c, m):
    users = list(users_db.find({}, {"user_id": 1, "last_active": 1}))
    tot = len(users)
    now = int(time.time())
    active = len([u for u in users if u.get("last_active", 0) > now - 3*24*3600])
    blocked = blocked_db.count_documents({})
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent()
    total, used, free = shutil.disk_usage("/")
    free_mb = int(free/1024**2)
    ping = time.perf_counter(); await c.get_me(); ping = int((time.perf_counter()-ping)*1000)
    stats = (
        f"👤 *Total Users:* {tot}\n"
        f"🟢 *Active (3d):* {active}\n"
        f"🚫 *Blocked:* {blocked}\n"
        f"🧠 *RAM:* {ram.percent}%\n"
        f"🖥 *CPU:* {cpu}%\n"
        f"💾 *Storage Free:* {free_mb}MB\n"
        f"⏳ *Ping:* {ping}ms {emoji()}"
    )
    await m.reply(stats)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

# ============= FILE/UNZIP ==============
@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    user_id = m.from_user.id
    fname = m.document.file_name
    userset = get_user_settings(user_id)
    if userset["ai_mode"]:
        # AI mode active, no extraction
        txt = f"AI mode ON hai — ab file extract nahi hogi, bas romantic chat possible hai. /settings se mode change karo."
        await m.reply(txt)
        return
    token = make_token()
    tmp_dir = f"/tmp/{user_id}_{int(time.time())}"
    os.makedirs(tmp_dir+"/unzipped", exist_ok=True)
    tfile = os.path.join(tmp_dir, fname)
    msg = await m.reply(f"Downloading started for `{fname}`\n\n{emoji()} Wait...")
    start_time = time.time()
    await c.download_media(
        m.document.file_id,
        file_name=tfile,
        progress=progress_for_pyro,
        progress_args=(msg, ("Downloading", start_time, token, fname))
    )
    await msg.delete() # remove progress bar after download
    # List archive files
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
                return await m.reply(f"File read error — valid zip/rar hai kya?\n{ex}")
        files_map = {}
        for ix, fn in enumerate(filelist):
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
        btn_rows, emojilist = [], ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for ix, (key, fpath) in enumerate(files_map.items()):
            btn_rows.append(
                [InlineKeyboardButton(f"{emojilist[ix%len(emojilist)]} {os.path.basename(fpath)}",
                        callback_data=f"{key}|{token}")]
            )
        btn_rows.append([
            InlineKeyboardButton("⬇️ Extract ALL", callback_data=f"extract_all|{token}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")
        ])
        await m.reply(
            f"Select file to extract from `{fname}`",
            reply_markup=InlineKeyboardMarkup(btn_rows)
        )
        await c.send_message(LOG_CHANNEL, f"#ARCHIVELIST {m.from_user.mention} {fname} files: {len(filelist)}")
    except Exception as e:
        await m.reply("List nahi bana paaye, galat file ho sakti hai " + emoji())
        await c.send_message(LOG_CHANNEL, f"ERR archive parse: {e}")

@app.on_callback_query()
async def extract_cbq(c, q):
    data = q.data.split("|")
    cmd, token = data[0], data[1]
    ses = sessions_db.find_one({"token": token})
    if not ses:
        await q.message.reply("Session expired. Nayi file bhejo!")
        return
    tmp_dir, tfile, filelist, files_map = ses["tmp_dir"], ses["tfile"], ses["filelist"], ses["files_map"]
    user_id = ses["user_id"]
    userset = get_user_settings(user_id)
    if (cmd == "cancel"):
        CANCELLED_SESSIONS.add(token)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await q.message.reply("Cancelled. Koi file extract nahi hogi. " + emoji())
        return
    if cmd == "extract_all":
        for ix, fn in enumerate(filelist):
            await do_extract_file(c, q, tfile, fn, tmp_dir, token, user_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await q.message.reply("Sab files extract ho gayi " + emoji())
        return
    if cmd.startswith("extract_"):
        fn = files_map[cmd]
        await do_extract_file(c, q, tfile, fn, tmp_dir, token, user_id)
        await q.answer(f"{os.path.basename(fn)} extracted!", show_alert=True)
        return

async def do_extract_file(c, cbq, tfile, filename, tmp_dir, token, uid):
    exfile = os.path.join(tmp_dir, "unzipped", os.path.basename(filename))
    msg = await cbq.message.reply(f"Extracting: `{os.path.basename(filename)}` {emoji()}")
    start_time = time.time()
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
        await msg.delete()
        return
    await cbq.message.reply_document(exfile, caption=f"`{os.path.basename(filename)}` Extracted!", reply_to_message_id=cbq.message.id)
    await c.send_document(LOG_CHANNEL, exfile, caption=f"Extracted by {uid}: {os.path.basename(filename)}")
    await msg.delete() # remove progress bar after send
    os.remove(exfile)

async def romantic_gpt(user_input, user_id=None):
    if not GPT_API_KEY or not user_input:
        return ""
    prompt = (
        "Reply in Hinglish, sweet, fun, short, with random emoji, only when AI mode is ON. Don't repeat reply."
    )
    url = "https://api.openai.com/v1/chat/completions"
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system","content": prompt},
            {"role": "user", "content": user_input}
        ],
        "max_tokens": 80, "n": 1, "temperature": 1.33
    }
    headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        if r.ok:
            text = r.json()['choices'][0]['message']['content'].strip()
            return text
    except Exception:
        pass
    return ""

@app.on_message(filters.private & ~filters.command(
    ["start", "help", "cancel", "broadcast", "status", "pass", "settings", "replace"]) & ~filters.document)
async def fallback_ai(c, m):
    userset = get_user_settings(m.from_user.id)
    if userset["ai_mode"]:
        rep = await romantic_gpt(m.text or "...")
        await m.reply(rep or "Kuch toh likho, baby! " + emoji())
    else:
        await m.reply("Archive mode hai ON. Baat karni ho toh /settings me Ai mode select karo." + emoji())

@flask_app.route("/", methods=["GET", "POST"])
def ping(): return "Serena bot up"

def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(
        host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
