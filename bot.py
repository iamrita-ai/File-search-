import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask

# ---------------- CONFIG ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_DB = os.getenv("MONGO_DB")
CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY")  # GF Chat
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
PORT = int(os.getenv("PORT", 10000))

# ---------------- FLASK -------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is Running ❤️"

# ---------------- MONGO -------------------
mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo.get_database("FILES_DB")
users_col = db.get_collection("users")
files_col = db.get_collection("files")

# ---------------- BOT ---------------------
bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------------- HELPERS -----------------
async def is_premium(user_id):
    doc = await users_col.find_one({"user_id": user_id})
    return doc and doc.get("premium", False)

def min_match(query, filename):
    words = query.lower().split()
    f = filename.lower()
    return sum(1 for w in words if w in f) >= 3  # minimum 3-word match

# ---------------- COMMANDS -----------------
@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    buttons = [
        [InlineKeyboardButton("Settings ⚙️", callback_data="settings")],
        [InlineKeyboardButton("Help ❓", callback_data="help")]
    ]
    await message.reply_text(
        "Hi Baby 😘\nMain tumhari Romantic GF bot hoon ❤️\nBoloo na Sweetheart 💋",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@bot.on_message(filters.private & filters.command("help"))
async def help_cmd(client, message):
    text = (
        "Commands:\n"
        "/start - Start bot\n"
        "/help - This message\n"
        "/addpremium - Add user premium (Owner only)\n"
        "/removepremium - Remove user premium (Owner only)\n"
        "/ban - Ban user (Owner only)\n"
        "/unban - Unban user (Owner only)\n"
        "/status - Bot status\n"
        "/clear - Clear DB (Owner only)\n\n"
        "Inline Settings:\n"
        "Choose Chat Mode: GF Chat (ChatGPT) or File Search"
    )
    await message.reply_text(text)

# ---------------- OWNER COMMANDS -----------------
@bot.on_message(filters.private & filters.command(["addpremium","removepremium","ban","unban","clear","status"]))
async def owner_cmds(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("❌ You are not the owner.")
        return
    cmd = message.text.split()[0][1:]
    if cmd == "addpremium":
        user_id = int(message.text.split()[1])
        await users_col.update_one({"user_id": user_id}, {"$set":{"premium":True}}, upsert=True)
        await message.reply_text(f"✅ User {user_id} added as premium")
    elif cmd == "removepremium":
        user_id = int(message.text.split()[1])
        await users_col.update_one({"user_id": user_id}, {"$set":{"premium":False}})
        await message.reply_text(f"✅ User {user_id} removed from premium")
    elif cmd == "ban":
        user_id = int(message.text.split()[1])
        await users_col.update_one({"user_id": user_id}, {"$set":{"banned":True}}, upsert=True)
        await message.reply_text(f"🚫 User {user_id} banned")
    elif cmd == "unban":
        user_id = int(message.text.split()[1])
        await users_col.update_one({"user_id": user_id}, {"$set":{"banned":False}})
        await message.reply_text(f"✅ User {user_id} unbanned")
    elif cmd == "clear":
        await users_col.delete_many({})
        await files_col.delete_many({})
        await message.reply_text("🗑️ Database cleared")
    elif cmd == "status":
        await message.reply_text("✅ Bot is running fine!")

# ---------------- SETTINGS PANEL -----------------
@bot.on_callback_query(filters.regex("settings"))
async def settings_cb(client, callback):
    buttons = [
        [InlineKeyboardButton("GF Chat (ChatGPT) 💕", callback_data="mode_gf")],
        [InlineKeyboardButton("File Search 📁", callback_data="mode_search")],
    ]
    await callback.message.edit_text(
        "Choose your preferred mode:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ---------------- MODE SELECTION -----------------
user_mode = {}  # user_id: mode

@bot.on_callback_query(filters.regex("mode_"))
async def mode_select(client, callback):
    mode = callback.data.split("_")[1]
    user_mode[callback.from_user.id] = mode
    await callback.answer(f"Mode set to: {mode}")
    await callback.message.edit_text(f"Mode set successfully to: {mode}")

# ---------------- MESSAGE HANDLER -----------------
@bot.on_message(filters.private & filters.text & ~filters.command(["start","help"]))
async def chat_handler(client, message):
    uid = message.from_user.id
    if uid in user_mode:
        if user_mode[uid] == "gf":
            import openai
            openai.api_key = CHATGPT_API_KEY
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":message.text}]
            )
            answer = resp.choices[0].message.content
            await message.reply_text(f"💖 {answer}")
        elif user_mode[uid] == "search":
            results = []
            async for doc in files_col.find():
                if min_match(message.text, doc["file_name"]):
                    results.append(doc)
            if not results:
                await message.reply_text("🌸 No Results Found")
            else:
                for r in results[:10]:
                    await message.reply_document(r["file_id"], caption=f"❤️ Found: {r['file_name']}")
    else:
        await message.reply_text("⚠️ Please choose a mode first using /start -> Settings ⚙️")

# ---------------- FILE SAVE FROM CHANNEL -----------------
@bot.on_message(filters.channel & filters.document)
async def save_files(client, message):
    await files_col.insert_one({
        "file_name": message.document.file_name.lower(),
        "file_id": message.document.file_id
    })
    try:
        await bot.send_message(LOGS_CHANNEL, f"📦 New file saved: `{message.document.file_name}`")
    except: pass

# ---------------- RUN FLASK + BOT -----------------
async def main():
    # start flask in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, lambda: app.run(host="0.0.0.0", port=PORT))
    await bot.start()
    print("🔥 Bot Launched Successfully!")
    await asyncio.Event().wait()  # keep running

if __name__ == "__main__":
    asyncio.run(main())
