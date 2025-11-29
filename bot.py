import os
import logging
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ------------------- ENV + CONFIG ---------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB = os.getenv("MONGO_DB")
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

API_ID = 29723019
API_HASH = "1a877af47fcaa33df78bb7a6734dddbd"

PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)

# ------------------- FLASK KEEP-ALIVE --------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running Successfully ❤️"

# ------------------- MONGO CLIENT -----------------------

mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo["FILES_DB"]
files_col = db["files"]

# ------------------- BOT CLIENT -------------------------

bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
)



# ********************************************************
#                   ROMANTIC AUTO REPLIES
# ********************************************************

@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    buttons = [
        [InlineKeyboardButton("❤️ My Creator", url=f"https://t.me/{MY_USERNAME}")],
        [InlineKeyboardButton("📁 Search Files", switch_inline_query_current_chat="")]
    ]
    await message.reply_text(
        f"Hello *Janu* ❤️\n\n"
        f"Main tumhari Romantic Assistant ho ✨\n"
        f"Aaj kya help chahiye meri Sweetheart? 💋",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ********************************************************
#                  STORE FILES FROM CHANNEL
# ********************************************************

@bot.on_message(filters.channel)
async def save_files(client, message):
    if message.document:
        name = message.document.file_name.lower()

        await files_col.insert_one({
            "file_name": name,
            "file_id": message.document.file_id
        })

        # Send log to logs channel
        try:
            await bot.send_message(
                LOGS_CHANNEL,
                f"📦 *New File Saved*\n\n**Name:** `{name}`"
            )
        except:
            pass


# ********************************************************
#                    FILE SEARCH SYSTEM
# ********************************************************

def min_match(query, filename):
    """Minimum 3-word matching"""
    q = query.lower().split()
    f = filename.lower()
    match_count = sum(1 for w in q if w in f)
    return match_count >= 1  # 1 ya 2 words bhi match hon to send karega (better results)

@bot.on_message(filters.text & ~filters.command(["start", "help"]))
async def search_file(client, message):
    query = message.text.lower()

    results = []
    async for doc in files_col.find():
        if min_match(query, doc["file_name"]):
            results.append(doc)

    if not results:
        await message.reply_text("🌸 *No Results Found* — Try a different keyword Sweetheart 💕")
        return

    for r in results[:20]:
        await message.reply_document(
            r["file_id"],
            caption=f"❤️ File mil gaya Janu!\n\n`{r['file_name']}`"
        )

# ********************************************************
#                    BOT ONLINE LOG
# ********************************************************

@bot.on_message(filters.command("alive"))
async def alive_handler(client, message):
    await message.reply_text("❤️ *Janu, I'm Always With You… Online & Active!*")

# ********************************************************
#                       RUN SERVER
# ********************************************************

if __name__ == "__main__":
    bot.start()
    app.run(host="0.0.0.0", port=PORT)
