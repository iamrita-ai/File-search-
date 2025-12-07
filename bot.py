import os, time, logging, aiofiles, zipfile, pyzipper, secrets, psutil, requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from pymongo import MongoClient

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "-1003286415377")
OWNER_ID = int(os.environ.get("OWNER_ID", "1598576202"))
MONGO_URL = os.environ.get("MONGO_URL")
GPT_API_KEY = os.environ.get("GPT_API_KEY", "")
FORCE_CHANNEL = "serenaunzipbot"

mdb = MongoClient(MONGO_URL)["unzipbot"]
users_db = mdb["users"]
sessions_db = mdb["sessions"]      # For short token mapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unzip-bot")
app = Client("serenaunzipbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

def emoji(): return "💖💘💃💕💞🫂🫰😍😚😘🌹🍬🔥🎉🎶🎵🎀✌️🥹🦋🥰😻✨🦄💌"

def make_token(n=6): return secrets.token_hex(n)

async def romantic_gpt(msg):
    if not GPT_API_KEY or not msg: return ""
    prompt = "Reply as a romantic Telegram bot girlfriend in Hinglish. Use a new emoji and never repeat previous replies."
    url = "https://api.openai.com/v1/chat/completions"
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system","content": prompt},
            {"role": "user", "content": msg}
        ],
        "max_tokens": 60, "n": 1, "temperature": 1.40
    }
    headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        if r.ok:
            text = r.json()['choices'][0]['message']['content'].strip()
            return "\n\n" + text
    except: pass
    return ""

async def check_force_join(user_id):
    try:
        member = await app.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except Exception: return False

def force_btns():
    btns = [[
        InlineKeyboardButton("🚀 Join Update Channel", url="https://t.me/serenaunzipbot"),
        InlineKeyboardButton("👤 Contact Owner", url="https://t.me/TechnicalSerena")
    ]]
    return InlineKeyboardMarkup(btns)

async def gated_reply(m, txt, btns=None, save_user=True):
    if not await check_force_join(m.from_user.id):
        return await m.reply("Pehle update channel join karo baby! Tabhi magic chalega " + random.choice(emoji()), reply_markup=force_btns())
    if save_user:
        users_db.update_one({"user_id": m.from_user.id}, {"$set": {"user_id": m.from_user.id}}, upsert=True)
    rtxt = await romantic_gpt(txt)
    return await m.reply(txt + rtxt, reply_markup=btns)

@app.on_message(filters.command("start"))
async def start(c, m):
    await gated_reply(m, f"Hello love! 🥰 Main tumhari har zip/unzip ya password file turant extract kar dungi, saath me romantic baat bhi. Bas file bhejo ya /help dekho!")
    await c.send_message(LOG_CHANNEL, f"#START {m.from_user.mention} ({m.from_user.id})")

@app.on_message(filters.command("help"))
async def help_cmd(c, m):
    helptext = (
        f"{random.choice(emoji())} **Serena Romantic Archive Bot** {random.choice(emoji())}\n\n"
        "Mera kaam hai tumhari ZIP/RAR/7z/doc files ko unlock karna, password-protected bhi! Har command pe romantic reply milti hai.\n\n"
        "**How to Use:**\n"
        "1. Bas mujhe ZIP ya document bhejo.\n"
        "2. Niche 'Unzip' aur 'Password' buttons milenge.\n"
        "    - Password wali file pe 'Password' dabao fir `/pass tumhara_password` reply karo.\n"
        "    - Simple file pe direct 'Unzip' dabao.\n"
        "3. Saari extracted files progress bar ke sath milengi.\n"
        "4. Kuch bhi galat bheje toh romantic error reply aayega.\n"
        f"\nOwner: @TechnicalSerena   |   Channel: @serenaunzipbot\n"
    )
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("📣 Update Channel", url="https://t.me/serenaunzipbot")],
        [InlineKeyboardButton("👤 Owner (DM)", url="https://t.me/TechnicalSerena")]
    ])
    await gated_reply(m, helptext, btns)
    await c.send_message(LOG_CHANNEL, f"#HELP {m.from_user.mention} ({m.from_user.id})")

@app.on_message(filters.command("cancel"))
async def cancel_cmd(c, m):
    await gated_reply(m, "Okay baby, cancel kar diya. Main hamesha ready hoon! " + random.choice(emoji()))
    await c.send_message(LOG_CHANNEL, f"#CANCEL {m.from_user.mention} ({m.from_user.id})")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_cmd(c, m):
    msg = m.reply_to_message or m
    bc_text = msg.text or msg.caption
    sent, fail = 0, 0
    for u in users_db.find({}, {"user_id": 1}):
        try: await c.send_message(u["user_id"], bc_text)
        except: fail +=1
        else: sent +=1
    romantic = await romantic_gpt("Sab tak pyar pohcha diya maine! Ab kya karoon baby?")
    await m.reply(f"Broadcast done, {sent} users. {romantic}")
    await c.send_message(LOG_CHANNEL, f"#BROADCAST {sent}/{fail} users.")

@app.on_message(filters.command("status"))
async def status_cmd(c, m):
    user_count = users_db.count_documents({})
    ping = time.perf_counter(); await c.get_me(); ping = (time.perf_counter()-ping)*1000
    stats = (
        f"{random.choice(emoji())} **Bot Status** {random.choice(emoji())}\n"
        f"Users: {user_count}\nPing: {ping:.2f} ms\nRAM: {psutil.virtual_memory().percent}%\nCPU: {psutil.cpu_percent()}%"
    )
    await gated_reply(m, stats)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    fname = m.document.file_name
    token = make_token()
    sessions_db.insert_one({"token":token, "file_id": m.document.file_id, "user_id": m.from_user.id})
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}")],
        [InlineKeyboardButton("🔑 Password", callback_data=f"pass|{token}")]
    ])
    await gated_reply(m, f"File `{fname}` mili hai baby! Kya karna hai? Unzip ya password ke saath extract?", kb)
    await c.send_message(LOG_CHANNEL, f"#DOC {m.from_user.mention}: {fname}")

@app.on_callback_query()
async def cbq(c, q):
    data = q.data.split('|')
    token = data[1]
    session = sessions_db.find_one({"token": token})
    if not session: return await q.message.reply("Session expired. Dobara file bhejo baby!")
    file_id = session['file_id']
    passwd = session.get('passwd', '')
    if data[0] == "unzip":
        await q.answer("Extract kar rahi hoon...😚", show_alert=True)
        await do_unzip(c, q, file_id, passwd)
    elif data[0] == "pass":
        sessions_db.update_one({"token":token}, {"$set": {"wait_pass":True}})
        await q.message.reply("Reply karo `/pass TumharaPassword` se baby!")

@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None, 1)[-1] if len(m.text.split()) > 1 else None
    r = m.reply_to_message
    # Find token from reply's buttons
    if not passwd: return await m.reply("Password type karo baby! " + random.choice(emoji()))
    token = None
    if r and r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and ("unzip|" in btn.callback_data or "pass|" in btn.callback_data):
                    token = btn.callback_data.split("|")[1]
    if not token: return await m.reply("Old session. Please send file again.")
    sessions_db.update_one({"token":token}, {"$set": {"passwd":passwd}})
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{token}")]])
    romance = await romantic_gpt("Password mil gaya, ab main extract karun? " + random.choice(emoji()))
    await r.edit_reply_markup(reply_markup=kb)
    await m.reply("Password set ho gaya, ab Unzip dabayein! " + romance)

def progress_bar(cur, total, size=18):
    percent = cur / total if total else 0
    fill = int(size * percent)
    bar = "█" * fill + "░" * (size-fill)
    return f"[{bar}] {percent*100:5.1f}%"

async def progress_for_pyro(current, total, msg, stage):
    if total==0: return
    await msg.edit_text(f"{stage}\n{progress_bar(current, total)}")

async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

async def do_unzip(c, cbq, file_id, passwd):
    uid = cbq.from_user.id
    tmp_dir = "/tmp"
    os.makedirs(f"{tmp_dir}/unzipped", exist_ok=True)
    tfile = os.path.join(tmp_dir, f"{uid}_file.zip")
    try:
        msg = await cbq.message.reply("⬇️ Downloading...⌛")
        await c.download_media(file_id, file_name=tfile, progress=progress_for_pyro, progress_args=(msg,"⬇️ Downloading..."))
        msg2 = await cbq.message.reply("🗃 Extracting...⏳")
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
            await cbq.message.reply(f"❌ Extract nahi ho paayi: {ex} {random.choice(emoji())}")
            await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {ex}")
            return
        files_uploaded = 0
        for ix, f in enumerate(extracted_files):
            await cbq.message.reply_document(f, caption=f"⬆️ Uploading [{ix+1}/{len(extracted_files)}]", progress=progress_for_pyro, progress_args=(msg2, f"⬆️ {os.path.basename(f)}"))
            files_uploaded += 1
        romance = await romantic_gpt("Sab file upload ho gayi baby! Kuch romantic sunoge?")
        await cbq.message.reply(f"Unzipped & uploaded {files_uploaded} file(s)! {romance}")
        await app.send_message(LOG_CHANNEL, f"#UNZIP: {uid} {files_uploaded} files.")
    except Exception as e:
        logger.error(str(e))
        await cbq.message.reply("🤦‍♀️ Extract aur upload me gadbad ho gayi! File valid ZIP hai na baby?")
        await app.send_message(LOG_CHANNEL, f"#UNZIP_FAIL {uid} {str(e)}")

@app.on_message(filters.private & ~filters.command(["start","help","cancel","broadcast","status","pass"]) & ~filters.document)
async def wrong_type(c, m):
    await gated_reply(m, "Oops baby! Main sirf documents, zip, rar, 7z ya docx hi extract kar sakti hoon. Koi galat cheez mat bhejo naa! " + random.choice(emoji()))
    await c.send_message(LOG_CHANNEL, f"#INVALID {m.from_user.mention}: {str(m.text)[:64]}")

@flask_app.route("/", methods=["GET", "POST"])
def ping():
    return "Serena romantic unzip bot is running", 200

def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == '__main__':
    run()
