import os
import re
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ----------------------------------------------------
# CONFIG (OWNER ID FIXED)
# ----------------------------------------------------
OWNER_ID = 1598576202                    # HARD-CODED
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")  # EXACT NAME YOU SAID
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "0"))

# ----------------------------------------------------
# DATABASE
# ----------------------------------------------------
mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["AutoBot"]
users_col = db["users"]
channels_col = db["channels"]
premium_col = db["premium"]
spam_col = db["antispam"]

# ----------------------------------------------------
# CLIENT
# ----------------------------------------------------
app = Client(
    "RomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
async def is_spam(user_id):
    data = await spam_col.find_one({"user_id": user_id})
    if not data:
        await spam_col.insert_one({"user_id": user_id, "count": 1})
        return False
    if data["count"] > 5:
        return True
    await spam_col.update_one({"user_id": user_id}, {"$inc": {"count": 1}})
    return False

async def reset_spam():
    while True:
        await asyncio.sleep(30)
        await spam_col.delete_many({})

asyncio.create_task(reset_spam())

async def romantic_reply():
    replies = [
        "Jaanu ❤️ kaam ho gaya… tum bas muskurati raho 🥺✨",
        "Ho gaya Sweetheart 😘",
        "Done meri Jindagi ❤️",
        "Bas tum bolo aur mai kar dun Baby 💋"
    ]
    return replies[datetime.now().second % len(replies)]

# ----------------------------------------------------
# START
# ----------------------------------------------------
@app.on_message(filters.command("start"))
async def start_cmd(_, m):
    await users_col.update_one(
        {"user_id": m.from_user.id},
        {"$set": {"last_seen": datetime.utcnow()}},
        upsert=True
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ My Owner", url="https://t.me/technicalSerena")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

    await m.reply_text(
        "Hello Jaanu 😘\n\n"
        "Mai tumhari Romantic Assistant ho ❤️\n"
        "Bol kya chahiye Baby? 🥺💋",
        reply_markup=keyboard
    )

# ----------------------------------------------------
# HELP
# ----------------------------------------------------
@app.on_message(filters.command("help"))
async def help_cmd(_, m):
    await m.reply_text(
        "**❤️ COMMAND LIST ❤️**\n\n"
        "/start – Romantic welcome\n"
        "/help – Help menu\n"
        "/addchannel – Add source channels (max 3)\n"
        "/reset – Remove added channels\n"
        "/clear – Clear MongoDB database\n"
        "/ban – Ban user\n"
        "/unban – Unban user\n"
        "/broadcast – Broadcast message\n"
        "/premium – Add/remove/check premium\n"
        "/stats – Bot stats\n"
        "/cancel – Cancel all running tasks\n",
        disable_web_page_preview=True
    )

# ----------------------------------------------------
# ADD CHANNEL
# ----------------------------------------------------
@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def add_channel(_, m):
    try:
        cid = int(m.text.split(" ")[1])
    except:
        return await m.reply("Send like:\n`/addchannel -1001234567890`")

    count = await channels_col.count_documents({})
    if count >= 3:
        return await m.reply("Maximum 3 source channels allowed.")

    await channels_col.insert_one({"channel_id": cid})
    await m.reply(await romantic_reply())

# ----------------------------------------------------
# RESET (REMOVE CHANNELS)
# ----------------------------------------------------
@app.on_message(filters.command("reset") & filters.user(OWNER_ID))
async def reset_cmd(_, m):
    await channels_col.delete_many({})
    await m.reply(await romantic_reply())

# ----------------------------------------------------
# CLEAR DATABASE
# ----------------------------------------------------
@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_db(_, m):
    await db.drop_collection("users")
    await db.drop_collection("channels")
    await db.drop_collection("premium")
    await db.drop_collection("antispam")
    await m.reply("Database cleared Jaanu ❤️")

# ----------------------------------------------------
# BAN / UNBAN
# ----------------------------------------------------
@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_user(_, m):
    try:
        uid = int(m.text.split(" ")[1])
    except:
        return await m.reply("Usage: /ban user_id")

    await premium_col.update_one({"user": uid}, {"$set": {"ban": True}}, upsert=True)
    await m.reply(await romantic_reply())

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_user(_, m):
    try:
        uid = int(m.text.split(" ")[1])
    except:
        return await m.reply("Usage: /unban user_id")

    await premium_col.update_one({"user": uid}, {"$set": {"ban": False}}, upsert=True)
    await m.reply(await romantic_reply())

# ----------------------------------------------------
# BROADCAST
# ----------------------------------------------------
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(_, m):
    msg = m.reply_to_message
    if not msg:
        return await m.reply("Reply to a message")

    async for user in users_col.find({}):
        try:
            await msg.copy(user["user_id"])
        except:
            pass

    await m.reply("Broadcast done ❤️")

# ----------------------------------------------------
# FILE NAME MATCH SEARCH
# ----------------------------------------------------
@app.on_message(filters.text & ~filters.command(["start", "help"]))
async def match_file(_, m):
    if await is_spam(m.from_user.id):
        return await m.reply("Too many requests Jaanu 😘 Slow down…")

    name = m.text.lower()

    # Logs se file fetch
    try:
        async for ch in channels_col.find({}):
            async for message in app.search_messages(ch["channel_id"], query=name):
                try:
                    await message.copy(m.chat.id, protect_content=True)
                    await m.reply(await romantic_reply())
                    return
                except:
                    pass
    except Exception as e:
        return await m.reply(f"Error: {e}")

    await m.reply("Kuch nahi mila Baby 🥺")

# ----------------------------------------------------
# INLINE SETTINGS
# ----------------------------------------------------
@app.on_callback_query(filters.regex("settings"))
async def settings(_, q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Reset", callback_data="reset")],
        [InlineKeyboardButton("📨 Contact Owner", url="https://t.me/technicalSerena")]
    ])
    await q.message.edit("⚙️ **Settings Menu**", reply_markup=kb)

# ----------------------------------------------------
# RUN
# ----------------------------------------------------
app.run()
