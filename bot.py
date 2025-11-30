import os
import asyncio
import time
from flask import Flask
from pyrogram import Client, filters, idle
from pymongo import MongoClient
import shutil
import openai

# ----------------- ENV -------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
OPENAI_KEY = os.getenv("OPENAI_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "6518065496"))

openai.api_key = OPENAI_KEY

# ----------------- DATABASE -------------------
db = MongoClient(MONGO_URL)["BABITA_BOT_DB"] if MONGO_URL is not None else None
users_col = db["users"] if db is not None else None
premium_col = db["premium"] if db is not None else None
files_col = db["files"] if db is not None else None

# ----------------- FLASK -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "💗 Bot is running!"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ----------------- BOT -------------------
bot = Client(
    "babita_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----------------- ROMANTIC REPLY -------------------
def romantic_reply(text):
    replies = [
        f"Janu ❤️ tum bolti ho na… mera dil tumhari baaton me kho jata hai…",
        f"Baby 🥺 tumhare message aate hi mera mood fresh ho jata hai…",
        f"Meri Jaan 💗 tum kya hi cute lagti ho yrr…",
        f"Sweetheart ❤️ tumhare bina sab kuch adhoora lagta hai…",
    ]
    return replies[hash(text) % len(replies)]

def is_premium(uid):
    return premium_col.find_one({"_id": uid}) is not None if premium_col is not None else False

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

# ----------------- COMMANDS -------------------
@bot.on_message(filters.command("start"))
async def start_cmd(c, m):
    if users_col is not None:
        users_col.update_one({"_id": m.from_user.id}, {"$set": {"name": m.from_user.first_name}}, upsert=True)
    await m.reply_text(
        f"Hello {m.from_user.first_name} ❤️\nMain tumhari baby bot hoon 💗",
        reply_markup={
            "inline_keyboard":[
                [{"text":"💗 Owner","url":"https://t.me/technicalserena"}],
                [{"text":"⚙️ Settings","callback_data":"settings"}]
            ]
        }
    )

@bot.on_message(filters.command("help"))
async def help_cmd(c, m):
    await m.reply_text(
        "/addpremium <user_id>\n"
        "/rem <user_id>\n"
        "/status\n"
        "/clear\n"
        "/setting\n"
        "Romantic chat → Just type ❤️"
    )

@bot.on_message(filters.command("addpremium"))
async def add_premium(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Ye command sirf owner ke liye hai 😘")
    try:
        uid = int(m.text.split()[1])
    except:
        return await m.reply("User ID do baby ❤️")
    if premium_col is not None:
        premium_col.update_one({"_id": uid}, {"$set": {}}, upsert=True)
    await m.reply("User ko premium de diya 💗")

@bot.on_message(filters.command("rem"))
async def remove_premium(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Janu ye sirf owner ka hai ❤️")
    try:
        uid = int(m.text.split()[1])
    except:
        return await m.reply("User ID do baby")
    if premium_col is not None:
        premium_col.delete_one({"_id": uid})
    await m.reply("Premium hata diya 💗")

@bot.on_message(filters.command("status"))
async def status_cmd(c, m):
    total_users = users_col.count_documents({}) if users_col is not None else 0
    total_premium = premium_col.count_documents({}) if premium_col is not None else 0
    storage = shutil.disk_usage("/")
    used = int((storage.used / storage.total) * 100)
    ping = round((time.time() - m.date.timestamp()) * 1000)
    await m.reply_text(
        f"❤️ BOT STATUS ❤️\nUsers: {total_users}\nPremium: {total_premium}\nStorage Used: {used}%\nPing: {ping} ms"
    )

@bot.on_message(filters.command("clear"))
async def clear_db(c, m):
    if m.from_user.id != OWNER_ID:
        return await m.reply("Ye sirf owner ke liye hai 💗")
    if users_col is not None: users_col.delete_many({})
    if premium_col is not None: premium_col.delete_many({})
    if files_col is not None: files_col.delete_many({})
    await m.reply("Janu database saaf kar diya 💗")

# ----------------- FILE SAVE -------------------
@bot.on_message(filters.document | filters.video)
async def save_files(c, m):
    if files_col is None:
        return
    file_id = m.document.file_id if m.document else m.video.file_id
    fname = m.document.file_name if m.document else m.video.file_name
    files_col.insert_one({"file_id": file_id, "name": fname.lower(), "uid": m.from_user.id})
    await m.reply("Sweetheart file save ho gayi 💗")

# ----------------- CALLBACKS -------------------
@bot.on_callback_query()
async def callback(c, q):
    if q.data == "settings":
        await q.message.edit(
            "⚙️ Settings Baby",
            reply_markup={
                "inline_keyboard":[
                    [{"text":"💬 Chat Mode (GPT)","callback_data":"inline_chat"}],
                    [{"text":"📁 File Search Mode","callback_data":"file_search"}],
                ]
            }
        )

# ----------------- CHAT -------------------
@bot.on_message(filters.private & filters.text & ~filters.command(["start","help","addpremium","rem","status","clear","setting"]))
async def chat_handler(c, m):
    if is_premium(m.from_user.id):
        text = await ask_gpt(m.text)
        await m.reply_text(text)
    else:
        await m.reply_text(romantic_reply(m.text))

# ----------------- FILE SEARCH -------------------
@bot.on_message(filters.regex("search ", flags=0))
async def search_files(c, m):
    if files_col is None:
        return
    query = m.text.replace("search ","").strip().lower()
    if len(query.split()) < 3: return await m.reply("Minimum 3 words chahiye baby 💗")
    results = list(files_col.find({"name": {"$regex": query}}))[:10]
    if not results: return await m.reply("Kuch nahi mila sweetheart")
    for file in results:
        try: await m.reply_document(file["file_id"])
        except: pass

# ----------------- RUN -------------------
async def main():
    asyncio.to_thread(run_flask)
    await bot.start()
    print("Bot is running ❤️")
    await idle()  # ✅ Properly imported

if __name__ == "__main__":
    asyncio.run(main())
