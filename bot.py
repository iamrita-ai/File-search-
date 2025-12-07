import os, logging, asyncio, time, aiofiles
import zipfile, pyzipper, psutil, requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# --- ENVIRONMENT ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GPT_API_KEY = os.environ.get("GPT_API_KEY", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "1598576202"))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003286415377"))

# MULTI-FORCE CHANNEL as comma-separated IDs/usernames
_FORCE_ENV = os.environ.get("FORCE_SUB_CHANNELS", "-1003392099253,serenaunzipbot")
FORCE_CHANNELS = []
FORCE_LINKS = []
for ch in [x.strip() for x in _FORCE_ENV.split(",")]:
    if ch.lstrip("-").isdigit():
        FORCE_CHANNELS.append(int(ch))
    else:
        ch = ch.lstrip("@")
        FORCE_CHANNELS.append(ch)
        FORCE_LINKS.append(ch)
# Add main Serena channel always
if "serenaunzipbot" not in FORCE_LINKS:
    FORCE_LINKS.append("serenaunzipbot")
# Button set
JOIN_BTNS = [
    [InlineKeyboardButton("❤️ Join @" + user, url=f"https://t.me/{user}")]
    for user in FORCE_LINKS
]

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unzip-bot")

# --- FLASK for Render Deploy/Ping
flask_app = Flask(__name__)

# --- BOT INSTANCE
app = Client("serena_unzip_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- GPT Romantic Hinglish Replier ---
async def romantic_gpt(user_msg):
    if not GPT_API_KEY or not user_msg: return ""
    url = "https://api.openai.com/v1/chat/completions"
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role":"system",
                "content": "Be flirtatious, sweet, short, romantic, talk in Hindi+English and always reply in a positive mood for a Telegram Bot. User may be your lover. Avoid English-only."},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 40,
        "n": 1, "temperature": 1.2
    }
    headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=8)
        if r.ok:
            msg = r.json()['choices'][0]['message']['content'].strip().replace("Serena", "Babu")
            return f"\n\n💌 *{msg}*"
    except: pass
    return ""

# --- FORCE SUBSCRIBE CHECK ---
async def check_force_sub(user_id: int) -> bool:
    """
    Returns True if user is member of ALL force channels. Handles id/username.
    """
    for ch in FORCE_CHANNELS:
        try:
            res = await app.get_chat_member(ch, user_id)
            if getattr(res, 'status', None) in [enums.ChatMemberStatus.BANNED]:
                return False
        except Exception:
            return False
    return True

# --- ATTACH FORCE JOIN IF NEEDED ---
async def gated_reply(m, txt, btns=None):
    if not await check_force_sub(m.from_user.id):
        return await m.reply("Update channel join karo pyare! Tabhi kaam chalega :)",
                             reply_markup=InlineKeyboardMarkup(JOIN_BTNS))
    romantic = await romantic_gpt(txt)
    return await m.reply(txt + romantic, reply_markup=btns)

# --- /START ---
@app.on_message(filters.command("start"))
async def start_handler(c, m):
    txt = "Haye! Main Serena romantic Unzip bot hoon 🥰. Koi bhi zip/rar/doc send karo, unlock ho jayega."
    await gated_reply(m, txt)
    await c.send_message(LOG_CHANNEL, f"#START By {m.from_user.mention} ({m.from_user.id})")

# --- /HELP ---
@app.on_message(filters.command("help"))
async def help_handler(c, m):
    txt = (
        "**Help**:\n"
        "- Koi bhi archive, encrypted zip bhi bhejo.\n"
        "- Document ke niche Unzip & Password ke button milenge.\n"
        "- Password protected file pe /pass <password> as reply karo.\n"
        "- Saare reply ke baad GPT romantic message bhi!\n"
        "- Logs: <code>{LOG_CHANNEL}</code>"
    )
    await gated_reply(m, txt)
    await c.send_message(LOG_CHANNEL, f"#HELP By {m.from_user.mention} ({m.from_user.id})")

# --- /BROADCAST Owner only ---
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(c, m):
    msg = m.reply_to_message or m
    user_msg = msg.text or msg.caption
    sent, fail = 0, 0
    async for dialog in c.get_dialogs():
        if dialog.chat.type == enums.ChatType.PRIVATE:
            try: await c.send_message(dialog.chat.id, user_msg)
            except: fail += 1
            else: sent += 1
    romantic = await romantic_gpt("Broadcast ho gaya baby!")
    await m.reply(f"Done! {sent} users ko bheja. {romantic}")
    await c.send_message(LOG_CHANNEL, f"#BROADCAST by {m.from_user.mention} ({m.from_user.id}) - total {sent}")

# --- /STATUS ---
@app.on_message(filters.command("status"))
async def status_handler(c, m):
    userc = 0
    async for dialog in app.get_dialogs():
        if dialog.chat.type == enums.ChatType.PRIVATE: userc += 1
    up = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    ping = time.perf_counter(); await c.get_me(); ping = (time.perf_counter()-ping)*1000
    stats = (
        f"**Bot Status:**\n"
        f"Active Users: `{userc}`\n"
        f"Ping: `{ping:.2f}` ms\n"
        f"Uptime: `{up}`\n"
        f"RAM: `{psutil.virtual_memory().percent}%`\n"
        f"CPU: `{psutil.cpu_percent()}%`"
    )
    await gated_reply(m, stats)
    await c.send_message(LOG_CHANNEL, f"#STATUS {stats}")

# ------- FILE RECEIVE & INLINE BUTTONS ---------
@app.on_message(filters.document & filters.private)
async def doc_handler(c, m):
    f = m.document; fname = f.file_name
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{f.file_id}|")],
        [InlineKeyboardButton("🔑 Password", callback_data=f"pass|{f.file_id}|")]
    ])
    await gated_reply(m, f"`{fname}`\nExtract karna hai ya password lagana hai?", kb)
    await c.send_message(LOG_CHANNEL, f"#DOC {m.from_user.mention}: {fname}")

# ------- CALLBACK BUTTON HANDLER FOR UNZIP/PASS -------
@app.on_callback_query()
async def cbq_handler(c, q):
    data = q.data.split('|')
    if data[0] == "unzip":
        file_id = data[1]
        passwd = data[2] if len(data)>2 else ""
        await q.answer("Processing...", show_alert=True)
        await unzip_flow(c, q, file_id, passwd)
    elif data[0] == "pass":
        await q.message.reply("Babu, reply me `/pass <password>` bhejein.")

# --- PASSWORD /pass <pswd> --- 
@app.on_message(filters.command("pass") & filters.reply)
async def pass_handler(c, m):
    passwd = m.text.split(None,1)[-1] if len(m.text.split())>1 else None
    r = m.reply_to_message
    if not passwd: return await m.reply("Kuch password to likho!")
    # Find original file ID
    if r and r.reply_markup:
        for row in r.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("unzip|"):
                    file_id = btn.callback_data.split("|")[1]
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗂 Unzip", callback_data=f"unzip|{file_id}|{passwd}")]
                    ])
                    romantic = await romantic_gpt("Password set! Extract karu?")
                    await r.edit_reply_markup(reply_markup=kb)
                    await m.reply(f"Password mil gaya! Ab Unzip dabao. {romantic}")

# -- Progress Bar Helper --
def progress_bar(cur, total, size=20):
    percent = cur / total if total else 0
    fill = int(size * percent)
    bar = "█"*fill + "░"*(size-fill)
    return f"`[{bar}] {percent*100:5.1f}%`"

async def progress_for_pyro(current, total, msg, stage):
    if total==0: return
    await msg.edit_text(f"{stage}\n" + progress_bar(current, total))

# --- Unzip Logic with Progress ---
async def aio_save(zipped, name, outp):
    data = zipped.read(name)
    async with aiofiles.open(outp, "wb") as f: await f.write(data)

async def unzip_flow(c, cbq, file_id, passwd):
    uid = cbq.from_user.id
    workdir = "/tmp"
    os.makedirs(workdir + "/unzipped", exist_ok=True)
    tfile = os.path.join(workdir, f"{uid}_in.zip")
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
                        out_path = os.path.join(workdir, "unzipped", f"{uid}_{os.path.basename(name)}")
                        await aio_save(zp, name, out_path)
                        extracted_files.append(out_path)
            else:
                with zipfile.ZipFile(tfile) as zp:
                    for name in zp.namelist():
                        out_path = os.path.join(workdir, "unzipped", f"{uid}_{os.path.basename(name)}")
                        with zp.open(name) as src, open(out_path, "wb") as dst: dst.write(src.read())
                        extracted_files.append(out_path)
        except Exception as ex:
            await cbq.message.reply(f"❌ Extraction failed! {ex}")
            return

        for ix, f in enumerate(extracted_files):
            show = await cbq.message.reply_document(f, caption=f"⬆️ Uploading [{ix+1}/{len(extracted_files)}]", progress=progress_for_pyro, progress_args=(msg2, f"⬆️ Uploading `{os.path.basename(f)}`..."))
        romantic = await romantic_gpt("Sab file upload ho gayi! Kuch romantic kahun?")
        await cbq.message.reply(f"Unzipped & uploaded {len(extracted_files)} file(s)! {romantic}")
        await c.send_message(LOG_CHANNEL, f"#UNZIP: {uid} files:{len(extracted_files)}")
    except Exception as e:
        logger.error(str(e))

# ----- FLASK for Render healthcheck ------
@flask_app.route("/", methods=["GET", "POST"])
def ping():
    return "Serena Unzip Bot is running!", 200

# ---- START BOTH SERVERS RENDER READY ----
def run():
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    app.run()

if __name__ == "__main__":
    run()
