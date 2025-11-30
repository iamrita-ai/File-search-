import os
import asyncio
import time
from flask import Flask
from pyrogram import Client, filters
from pymongo import MongoClient
from datetime import datetime
import shutil
import openai

# --------------------------------------------------------
# 🔐 ENVIRONMENT VARIABLES (Render Dashboard me fill karo)
# --------------------------------------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
OPENAI_KEY = os.getenv("OPENAI_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "6518065496"))

openai.api_key = OPENAI_KEY

# --------------------------------------------------------
# 🌸 DATABASE INIT
# --------------------------------------------------------
db = None
users_col = None
premium_col = None
files_col = None

if MONGO_URL:
    mongo = MongoClient(MONGO_URL)
    db = mongo["BABITA_BOT_DB"]
    users_col = db["users"]
    premium_col = db["premium"]
    files_col = db["files"]

# --------------------------------------------------------
# 🌸 FLASK SERVER (Render wants a port)
# --------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "💗 Bot is running babe! — Render Web Service OK."

def run_flask():
    port = int(os.getenv("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# --------------------------------------------------------
# 🌸 BOT INIT
# --------------------------------------------------------
bot = Client(
    "babita_gf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# --------------------------------------------------------
# 🌸 ROMANTIC REPLY GENERATOR
# --------------------------------------------------------
def romantic_reply(text):
    replies = [
        f"Janu ❤️ tum bolti ho na… mera dil seedha tumhari baaton me kho jata hai…",
        f"Baby 🥺 tumhare message aate hi mera mood fresh ho jata hai…",
        f"Meri Jaan 💗 tum kya hi cute lagti ho yrr…",
        f"Sweetheart ❤️ tumhare bina sab kuch adhoora lagta hai…",
    ]
    return replies[hash(text) % len(replies)]

# --------------------------------------------------------
# 🌸 CHECK PREMIUM
# --------------------------------------------------------
def is_premium(uid):
    return premium_col.find_one({"_id": uid}) is not None

# --------------------------------------------------------
# 🌸 CHATGPT COMMUNICATION
# --------------------------------------------------------
async def ask_gpt(message):
    try:
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Act like romantic girlfriend."},
                {"role": "user", "content": message}
            ]
        )
        return completion.choices[0].message["content"]
    except:
        return romantic_reply(message)

# --------------------------------------------------------
# 🌸 COMMAND: /start
# --------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start_cmd(c, m):
    users_col.update_one({"_id": m.from_user.id}, {"$set": {"name": m.from_user.first_name}}, upsert=True)

    await m.reply_text(
        f"Hello {m.from_user.first_name} ❤️\n"
        "Main tumhari baby bot hoon… romantic replies, file search, chatgpt sab kar sakti hoon 💗",
        reply_markup={
            "inline_keyboard": [
                [{"text": "💗 Owner", "url": "https://t.me/technicalserena"}],
                [{"text": "⚙️ Settings", "callback_data": "settings"}],
            ]
        }
    )

# --------------------------------------------------------
# 🌸 COMMAND: /help
# --------------------------------------------------------
@bot.on_message(filters.command("help"))
async def help_cmd(c, m):
    await m.reply_text(
        "Baby ye commands use karo 💗:\n\n"
        "/addpremium <user_id>\n"
        "/rem <user_id>\n"
        "/status\n"
        "/clear\n"
        "/setting\n"
        "Romantic chat → Just send me message ❤️"
    )

# --------------------------------------------------------
# 🌸 PREMIUM ADD
# --------------------------------------------------------
@bot.on_message(filters.command("addpremium"))
async def add_premium(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Jaan ye command sirf owner use karega 😘")

    try:
        uid = int(m.text.split()[1])
    except:
        return await m.reply("User ID do baby ❤️")

    premium_col.update_one({"_id": uid}, {"$set": {}}, upsert=True)
    await m.reply("User ko premium de diya baby 💗")

# --------------------------------------------------------
# 🌸 PREMIUM REMOVE
# --------------------------------------------------------
@bot.on_message(filters.command("rem"))
async def remove_premium(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Janu ye command sirf owner ka hai ❤️")

    try:
        uid = int(m.text.split()[1])
    except:
        return await m.reply("User ID do baby")

    premium_col.delete_one({"_id": uid})
    await m.reply("Premium hata diya sweetheart 💗")

# --------------------------------------------------------
# 🌸 STATUS COMMAND
# --------------------------------------------------------
@bot.on_message(filters.command("status"))
async def status_cmd(c, m):

    total_users = users_col.count_documents({})
    total_premium = premium_col.count_documents({})

    storage = shutil.disk_usage("/")
    used = int((storage.used / storage.total) * 100)

    ping = round((time.time() - m.date.timestamp()) * 1000)

    await m.reply_text(
        f"❤️ **BOT STATUS** ❤️\n\n"
        f"Users: {total_users}\n"
        f"Premium: {total_premium}\n"
        f"Storage Used: {used}%\n"
        f"Ping: {ping} ms\n"
    )

# ----------------------------------------------------------
# 🌸 CLEAR DATABASE
# ----------------------------------------------------------
@bot.on_message(filters.command("clear"))
async def clear_db(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Love ye sirf owner ke liye hai ❤️")

    users_col.delete_many({})
    premium_col.delete_many({})
    files_col.delete_many({})
    await m.reply("Janu database saaf kar diya 💗")

# ----------------------------------------------------------
# 🌸 SAVE FILES (for search system)
# ----------------------------------------------------------
@bot.on_message(filters.document | filters.video)
async def save_files(c, m):
    if m.document:
        fname = m.document.file_name or ""
    else:
        fname = m.video.file_name or ""

    files_col.insert_one({
        "file_id": m.document.file_id if m.document else m.video.file_id,
        "name": fname.lower(),
        "uid": m.from_user.id
    })

    await m.reply("Sweetheart file save ho gayi 💗")

# ----------------------------------------------------------
# 🌸 SETTINGS BUTTON
# ----------------------------------------------------------
@bot.on_callback_query()
async def callback(c, q):
    if q.data == "settings":
        await q.message.edit(
            "⚙️ **Settings Baby**\nChoose one:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "💬 Chat Mode (GPT)", "callback_data": "inline_chat"}],
                    [{"text": "📁 File Search Mode", "callback_data": "file_search"}],
                ]
            }
        )

# ----------------------------------------------------------
# 🌸 NORMAL CHAT HANDLER (ROMANTIC + GPT)
# ----------------------------------------------------------
@bot.on_message(
    filters.private &
    filters.text &
    ~filters.command(["start", "help", "addpremium", "rem", "status", "clear", "setting"])
)
async def chat_handler(c, m):

    if is_premium(m.from_user.id):
        text = await ask_gpt(m.text)
        return await m.reply_text(text)

    else:
        return await m.reply_text(romantic_reply(m.text))

# ----------------------------------------------------------
# 🌸 FILE SEARCH
# ----------------------------------------------------------
@bot.on_message(filters.regex("search ", flags=0))
async def search_files(c, m):
    query = m.text.replace("search ", "").strip().lower()
    if len(query.split()) < 3:
        return await m.reply("Minimum 3 words chahiye baby 💗")

    results = list(files_col.find({"name": {"$regex": query}}))

    if not results:
        return await m.reply("Kuch nahi mila sweetheart")

    for file in results[:10]:
        try:
            await m.reply_document(file["file_id"])
        except:
            pass

# ----------------------------------------------------------
# 🌸 RUN EVERYTHING
# ----------------------------------------------------------
async def start_all():
    print("Starting Flask keepalive…")
    asyncio.to_thread(run_flask)

    print("Starting Bot…")
    await bot.start()
    print("Bot Running…")
    await idle()

if __name__ == "__main__":
    asyncio.run(start_all())
