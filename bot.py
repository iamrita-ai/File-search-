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

EMOJIS = ["💖","💃","💕","😍","🫰","🌹","🔥","🎉","🎀","😻","✨","😚","😇","🦄","😘","🍬","🫂","🎵","🦋","🥰","💌","✌️"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unzip-bot")
app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

def emoji(): return random.choice(EMOJIS)
def make_token(n=6): return secrets.token_hex(n)

# USER SETTINGS
def get_user_settings(uid):
    s = settings_db.find_one({"user_id": uid}) or {}
    return {
        "ai_mode": s.get("ai_mode", True),
        "unzip_mode": s.get("unzip_mode", "normal"),
        "replace_word": s.get("replace_word", [None, None])
    }

def set_user_setting(uid, k, v):
    settings_db.update_one({"user_id": uid}, {"$set":{k: v}}, upsert=True)

def reset_user_settings(uid):
    settings_db.delete_one({"user_id": uid})

async def romantic_gpt(user_input, user_id=None, ai_mode=True):
    if not GPT_API_KEY or not user_input or not ai_mode:
        return ""
    prompt = (
        "Reply as a real AI girlfriend in Hinglish, sweet, romantic, fun, emotional, natural, with random emoji. "
        "No repetition, short tone, real chatgpt-style."
    )
    url = "https://api.openai.com/v1/chat/completions"
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system","content": prompt},
            {"role": "user", "content": user_input}
        ],
        "max_tokens": 80, "n": 1, "temperature": 1.35
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

async def check_force_join(user_id):
    try:
        member = await app.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except Exception:
        return False

def get_force_btns(show_contact=True):
    btns = [[InlineKeyboardButton("🚀 Join Update Channel", url="https://t.me/serenaunzipbot")]]
    if show_contact:
        btns.append([InlineKeyboardButton("👤 Contact Owner", url="https://t.me/TechnicalSerena")])
    return InlineKeyboardMarkup(btns)

CANCELLED_SESSIONS = set()

async def gated_reply(m, txt, btns=None, save_user=True, ai=True):
    if not await check_force_join(m.from_user.id):
        await m.reply("Pehle update channel join karo! Tabhi magic chalega " + emoji(), reply_markup=get_force_btns())
        return "no_join"
    if save_user:
        users_db.update_one({"user_id": m.from_user.id}, {
            "$set": {"user_id": m.from_user.id, "last_active": int(time.time())}}, upsert=True)
    ai_mode = get_user_settings(m.from_user.id)["ai_mode"] if ai else False
    ai_reply = await romantic_gpt(txt, m.from_user.id, ai_mode=ai_mode)
    return await m.reply(txt + ("\n\n" + ai_reply if ai_reply else ""), reply_markup=btns)

# ------------  SQUARE PROGRESS BAR  ------------
def progress_box(cur, total, start_time, stage, token):
    percent = cur / total if total else 0
    mb_done = cur/1024/1024
    speed = mb_done / max(1, time.time() - start_time)
    remaining = int((total-cur)/1024/1024 / speed) if speed>0 else 0
    boxsize = 9
    fill = int(percent*boxsize*boxsize)
    bar = "⬜"*boxsize
    sq=[]
    for i in range(boxsize):
        row = []
        for j in range(boxsize):
            idx = i*boxsize + j
            if idx < fill: row.append("🟩")
            else: row.append("⬜")
        sq.append("".join(row))
    box = "\n".join(sq)
    data = (
        f"{stage} {emoji()}\n"
        f"{box}\n"
        f"📦 {mb_done:.1f}MB / {total/1024/1024:.1f}MB\n"
        f"⚡ Speed: {speed:.2f}MB/s\n"
        f"⏳ ETA: {remaining}s\n"
        f"🔢 {percent*100:.1f}%"
    )
    inline = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]])
    return data, inline

async def progress_for_pyro(current, total, msg, stage_data):
    (stage, start_time, token) = stage_data
    text, inline = progress_box(current, total, start_time, stage, token)
    await msg.edit_text(text, reply_markup=inline)
    if token in CANCELLED_SESSIONS:
        raise asyncio.CancelledError("User cancelled")

# ------------ USER SETTINGS INLINES ------------
def get_settings_btns(s):
    col1 = [
        InlineKeyboardButton(f"Unzip Mode: {s['unzip_mode']}", callback_data=f"set_unzip|{s['unzip_mode']}"),
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
    await m.reply("👑 *Your Bot Settings:*\n- Unzip Mode: normal/fast\n- Ai Mode: romantic reply ON/OFF\n- Replace word for file rename\n- Reset to default\n", reply_markup=get_settings_btns(s))
    await c.send_message(LOG_CHANNEL, f"#SETTINGS {m.from_user.mention}")

@app.on_callback_query()
async def setting_cbq(c, q):
    data = q.data.split("|")
    if data[0] == "set_unzip":
        # Toggle
        val = "fast" if data[1]=="normal" else "normal"
        set_user_setting(q.from_user.id, "unzip_mode", val)
    elif data[0] == "set_ai":
        set_user_setting(q.from_user.id, "ai_mode", bool(int(data[1])))
    elif data[0] == "replace_word":
        await q.message.reply("Send new words like:\n`hello serena`\nFrom -> To\nThis will rename any extracted file named 'hello...' to 'serena...'.")
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
    await m.reply(f"Saved! Every extracted file named '{fromw}' will rename to '{tow}'.")

# ------------ BOT PRIMARY COMMANDS ------------
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await gated_reply(m,
    "Hello sweetheart! 😍\n"
    "Main ek romantic AI archive bot hoon. Send kar koi document ya archive ZIP/RAR/DOCX mujhe, main sab kuch extract/rename kar dungi. Buttons milenge. Storage safe hai, files tumhe aur owner dono ko milengi.\n\n"
    "Use /help for full guide.", btns=get_force_btns(), ai=True)
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("help"))
async def help_cmd(c, m):
    txt = (
f"{emoji()} *Welcome to Serena Romantic UnzipBot!* {emoji()}\n\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
"📎   *How to use:*\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
"1️⃣  File bhejein (zip/rar/7z/doc/pdf)\n"
"2️⃣  Bot reply karegi — buttons milenge: Unzip/Password\n"
"    • Password ho, 'Password' dabao fir `/pass yourpassword` reply karo\n"
"    • Simple file hai to direct Unzip dabao\n"
"3️⃣  Extracted files aapko & owner ko milenge (storage safe!)\n"
"4️⃣  Ko bhi galat bhejo, romantic error reply\n"
"\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
"📚   *Commands:*\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
"/start  – Intro & welcome\n"
"/help   – Full guide\n"
"/settings – Customize bot ✨\n"
"/cancel  – Stop job\n"
"/status  – Bot stats (owner only)\n"
"/broadcast – Owner broadcast\n"
"/pass <password> – Use password on ‘Password’ button\n"
"/replace <from> <to> – Word replace in extracted files\n"
"\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
"📣 [Update Channel](https://t.me/serenaunzipbot)   |   👤 [Owner](https://t.me/TechnicalSerena)\n"
"━━━━━━━━━━━━━━━━━━━━━━\n"
)
    btns = get_force_btns()
    await gated_reply(m, txt, btns=btns, ai=False)
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    for s in sessions_db.find({"user_id": m.from_user.id}):
        CANCELLED_SESSIONS.add(s["token"])
    await gated_reply(m, "Sab kaam cancel! Tum fir try karo, main yahin hoon " + emoji(), ai=True)
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
    await gated_reply(m, stats, ai=False)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

# ------------- File/Unzip ---------------
@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    fname = m.document.file_name
    token = make_token()
    sessions_db.insert_one({"token": token, "file_id": m.document.file_id, "user_id": m.from_user.id, "start": int(time.time())})
    await c.forward_messages(LOG_CHANNEL, m.chat.id, m.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}"),
         InlineKeyboardButton("🔑 Password", callback_data=f"pass|{token}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]
    ])
    await gated_reply(m, f"File `{fname}` mil gayi baby! Unzip ya password set karo:", kb)
    await c.send_message(LOG_CHANNEL, f"#DOC {m.from_user.mention}: {fname}")

@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split("|")
    token = data[1]
    session = sessions_db.find_one({"token": token})
    if not session: return await q.message.reply("Session expired. Nayi file send karo baby!")
    if data[0] == "cancel":
        CANCELLED_SESSIONS.add(token)
        return await q.message.reply("Job cancelled! " + emoji())
    file_id = session["file_id"]
    passwd = session.get("passwd", "")
    if data[0] == "unzip":
        await q.answer("Extraction ready...", show_alert=True)
        await do_unzip(c, q, file_id, passwd, token)
    elif data[0] == "pass":
        sessions_db.update_one({"token": token}, {"$set": {"wait_pass": True}})
        await q.message.reply("Reply karo `/pass Password` as reply baby!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]]))

@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None, 1)[-1] if len(m.text.split()) > 1 else None
    r = m.reply_to_message
    token = None
    if r and r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and ("unzip|" in btn.callback_data or "pass|" in btn.callback_data):
                    token = btn.callback_data.split("|")[1]
    if not passwd or not token: return await m.reply("Use `/pass hello123` reply on file button.")
    sessions_db.update_one({"token": token}, {"$set": {"passwd": passwd}})
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]
    ])
    await r.edit_reply_markup(reply_markup=kb)
    await m.reply("Password set ho gaya, ab Unzip karo! " + emoji())

def apply_replace(file_name, uid):
    rw = get_user_settings(uid).get("replace_word", [None, None])
    if rw and rw[0] and rw[1]:
        return re.sub(rw[0], rw[1], file_name, flags=re.I)
    return file_name

async def progress_for_pyro(current, total, msg, stage_data):
    (stage, start_time, token) = stage_data
    text, inline = progress_box(current, total, start_time, stage, token)
    await msg.edit_text(text, reply_markup=inline)
    if token in CANCELLED_SESSIONS:
        raise asyncio.CancelledError("User cancelled")

async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

async def do_unzip(c, cbq, file_id, passwd, token):
    uid = cbq.from_user.id
    tmp_dir = f"/tmp/{uid}_{int(time.time())}"
    os.makedirs(tmp_dir + "/unzipped", exist_ok=True)
    tfile = os.path.join(tmp_dir, "t.zip")
    start_time = time.time()
    try:
        msg = await cbq.message.reply("⬇️ Downloading...")
        await c.download_media(file_id, file_name=tfile,
                               progress=progress_for_pyro,
                               progress_args=(msg, ("⬇️ Downloading...", start_time, token)))
        msg2 = await cbq.message.reply("🗃 Extracting...")
        extracted_files = []
        try:
            unzip_mode = get_user_settings(uid)["unzip_mode"]
            if passwd:
                with pyzipper.AESZipFile(tfile) as zp:
                    zp.pwd = passwd.encode()
                    for name in zp.namelist():
                        out_name = apply_replace(os.path.basename(name), uid)
                        out_path = os.path.join(tmp_dir, "unzipped", out_name)
                        await aio_save(zp, name, out_path)
                        extracted_files.append(out_path)
            else:
                with zipfile.ZipFile(tfile) as zp:
                    # normal/fast mode: (for demo, both same)
                    for name in zp.namelist():
                        out_name = apply_replace(os.path.basename(name), uid)
                        out_path = os.path.join(tmp_dir, "unzipped", out_name)
                        with zp.open(name) as src, open(out_path, "wb") as dst:
                            dst.write(src.read())
                        extracted_files.append(out_path)
        except Exception as ex:
            await cbq.message.reply(f"❌ Extract nahi ho paayi: {ex}\n{emoji()}")
            await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {ex}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return
        files_uploaded = 0
        for ix, f in enumerate(extracted_files):
            await c.send_document(LOG_CHANNEL, f, caption=f"Tumhari unzip file [{ix+1}/{len(extracted_files)}] by {uid}",
                                  progress=progress_for_pyro,
                                  progress_args=(msg2, (f"⬆️ Uploading `{os.path.basename(f)}`...", start_time, token)))
            await cbq.message.reply_document(f, caption=f"⬆️ Uploaded {os.path.basename(f)}", progress=progress_for_pyro, progress_args=(msg2, (f"⬆️ User Upload `{os.path.basename(f)}`...", start_time, token)))
            files_uploaded += 1
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await cbq.message.reply(f"Unzipped & uploaded {files_uploaded} file(s) to you + log channel! {emoji()}")
        await app.send_message(LOG_CHANNEL, f"#UNZIP: {uid} {files_uploaded} files.")
    except asyncio.CancelledError:
        await cbq.message.reply("Job cancelled by you! " + emoji())
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        logger.error(str(e))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await cbq.message.reply("🤦‍♀️ Extract or upload me gadbad ho gayi! File valid ZIP hai na baby?")
        await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {str(e)}")

@app.on_message(filters.private & ~filters.command(
    ["start", "help", "cancel", "broadcast", "status", "pass", "settings", "replace"]) & ~filters.document)
async def fallback_ai(c, m):
    text = m.text or "User message"
    ai_mode = get_user_settings(m.from_user.id)["ai_mode"]
    rep = await romantic_gpt(text, m.from_user.id, ai_mode=ai_mode)
    await m.reply(rep or "Bas document bhejo ya /help likho na jaanu " + emoji())

@flask_app.route("/", methods=["GET", "POST"])
def ping(): return "Serena romantic unzipbot up"

def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
