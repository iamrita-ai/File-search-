import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import logging

logging.basicConfig(level=logging.INFO)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# ---------------- MongoDB Setup ----------------
db = MongoClient(MONGO_URL)["RomanticBot"]
premium_db = db["premium_users"]
settings_db = db["settings"]

# ---------------- Bot Client ----------------
bot = Client(
    "RomanticLoveBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------- Helper ----------------
def is_premium(user_id):
    return premium_db.find_one({"id": user_id}) is not None

# ---------------- /start ----------------
@bot.on_message(filters.command("start"))
async def start(_, m):
    await m.reply_text(
        f"Hello My *Jaan* ❤️\nMain Tumhari Romantic Bot Hoon.\n\n/start → Romantic Welcome",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❤️ Owner", url="https://telegram.me/technicalserena")],
            [InlineKeyboardButton("Help 💕", callback_data="help")]
        ])
    )

# ---------------- /help ----------------
@bot.on_callback_query(filters.regex("help"))
async def help_cb(_, q):
    text = """
*Sweetheart 💕 Commands:*

❤️ /addpremium [id]  
🖤 /removepremium [id]  
💗 /status – Bot status  
💕 /clear – MongoDB clear  
💖 /settings – Advanced Settings  
💋 File Matching → Agar kisi file ke name me 3 words match aaye to user ko DM.

Example:
`/addpremium 6518065496`
"""
    await q.message.edit_text(text)

# ---------------- Add Premium ----------------
@bot.on_message(filters.command("addpremium"))
async def add_premium(_, m):
    if len(m.command) < 2:
        return await m.reply("Janu ID dedo 🥺")

    uid = int(m.command[1])
    premium_db.insert_one({"id": uid})
    await m.reply(f"Janu ❤️ User {uid} premium me add ho gaya 💋")

# ---------------- Remove Premium ----------------
@bot.on_message(filters.command("rem"))
async def rempremium(_, m):
    if len(m.command) < 2:
        return await m.reply("Sweetheart User ID do 🥺")

    uid = int(m.command[1])
    premium_db.delete_one({"id": uid})
    await m.reply(f"My Love ❤️ User {uid} premium se remove 💔")

# ---------------- Status ----------------
@bot.on_message(filters.command("status"))
async def status(_, m):
    await m.reply("Baby Bot Perfectly Online Hai 💕🔥")

# ---------------- Clear DB ----------------
@bot.on_message(filters.command("clear"))
async def clear(_, m):
    premium_db.delete_many({})
    settings_db.delete_many({})
    await m.reply("Janu ❤️ Database Saaf Ho Gaya 💦")

# ---------------- Settings ----------------
@bot.on_message(filters.command("settings"))
async def settings(_, m):
    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Set Source Channel", callback_data="set_sc"),
            InlineKeyboardButton("Remove Log Channel", callback_data="rm_log")
        ],
        [
            InlineKeyboardButton("Replace Words", callback_data="rep_words"),
            InlineKeyboardButton("Set Caption", callback_data="set_cap")
        ]
    ])
    await m.reply("Sweetheart ❤️ Choose a setting:", reply_markup=btn)

# ------------------------------------------------------------
# 🔥 MAIN — NO THREAD — 100% FIXED FOR RENDER
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Bot Running On Render Without Thread Error ❤️")
    bot.run()
