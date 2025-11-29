import os
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from pymongo import MongoClient

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 1598576202  # Fixed
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

app = Client(
    "SerenaRomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

db = MongoClient(MONGO_DB_URI)["SerenaBot"]

users_col = db["Users"] if db is not None else None
config_col = db["Config"] if db is not None else None
saved_col = db["Saved"] if db is not None else None

# ----------------------------------------------------
# GLOBALS
# ----------------------------------------------------
ANTI_SPAM = {}
SOURCE_CHANNELS = []
LOG_CHANNEL = None


# ----------------------------------------------------
# ANTI-SPAM RESET
# ----------------------------------------------------
async def reset_spam():
    while True:
        ANTISPAM = {}
        await asyncio.sleep(5)


# ----------------------------------------------------
# LOAD CONFIG
# ----------------------------------------------------
async def load_config():
    global LOG_CHANNEL, SOURCE_CHANNELS

    cfg = config_col.find_one({"_id": "config"})
    if cfg:
        LOG_CHANNEL = cfg.get("log_channel")
        SOURCE_CHANNELS = cfg.get("source_channels", [])


# ----------------------------------------------------
# SAVE CONFIG
# ----------------------------------------------------
def save_config():
    config_col.update_one(
        {"_id": "config"},
        {"$set": {
            "log_channel": LOG_CHANNEL,
            "source_channels": SOURCE_CHANNELS
        }},
        upsert=True
    )


# ----------------------------------------------------
# ROMANTIC REPLIES
# ----------------------------------------------------
def sweet_reply(text):
    return f"Baby ❤️ '{text}' search kar rahi hoon… rukko jaanu 😘"


# ----------------------------------------------------
# STARTUP TASKS
# ----------------------------------------------------
async def startup_tasks():
    asyncio.create_task(reset_spam())
    await load_config()
    print("Startup tasks started...")


# ----------------------------------------------------
# COMMAND — /start
# ----------------------------------------------------
@app.on_message(filters.command("start"))
async def start_cmd(_, m):

    await startup_tasks()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ My Owner", url="https://t.me/technicalSerena")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

    await m.reply_text(
        "Hello Jaanu 😘\n\n"
        "Main tumhari romantic assistant ho ❤️\n"
        "Bolo baby kya help karu tumhari..? 💋",
        reply_markup=keyboard
    )


# ----------------------------------------------------
# COMMAND — /help
# ----------------------------------------------------
@app.on_message(filters.command("help"))
async def help_cmd(_, m):
    txt = (
        "❤️ **Baby ye commands tumhare liye:**\n\n"
        "/addchannel – Add source channel\n"
        "/resetchannel – Remove all source channels\n"
        "/setlog – Set Logs Channel\n"
        "/clear – Clear MongoDB\n"
        "/stats – Bot Status\n"
        "/ban – Ban a user\n"
        "/unban – Unban a user\n"
        "/broadcast – Send to all users\n"
        "/cancel – Cancel tasks\n"
        "/start – Romantic greeting ❤️"
    )

    await m.reply_text(txt)


# ----------------------------------------------------
# COMMAND — /setlog
# ----------------------------------------------------
@app.on_message(filters.command("setlog") & filters.user(OWNER_ID))
async def setlog_cmd(_, m):
    global LOG_CHANNEL

    if len(m.command) == 2:
        try:
            LOG_CHANNEL = int(m.command[1])
            save_config()
            await m.reply_text("Jaanu ❤️ Logs channel set ho gaya!")
        except:
            await m.reply_text("Baby galat chat ID diya 😭")
    else:
        await m.reply_text("Chat ID do jaanu.")


# ----------------------------------------------------
# COMMAND — /addchannel
# ----------------------------------------------------
@app.on_message(filters.command("addchannel") & filters.user(OWNER_ID))
async def add_channel(_, m):
    global SOURCE_CHANNELS

    if len(SOURCE_CHANNELS) >= 3:
        return await m.reply_text("Baby max 3 channels add kar sakti ho 😘")

    if len(m.command) == 2:
        try:
            cid = int(m.command[1])
            SOURCE_CHANNELS.append(cid)
            save_config()
            await m.reply_text("Jaanu ❤️ Source channel add ho gaya!")
        except:
            await m.reply_text("Baby galat chat ID diya 😭")
    else:
        await m.reply_text("Chat ID do baby.")


# ----------------------------------------------------
# COMMAND — /resetchannel
# ----------------------------------------------------
@app.on_message(filters.command("resetchannel") & filters.user(OWNER_ID))
async def reset_channel(_, m):
    global SOURCE_CHANNELS
    SOURCE_CHANNELS = []
    save_config()
    await m.reply_text("Jaanu ❤️ saare source channels reset ho gaye!")


# ----------------------------------------------------
# COMMAND — /clear
# ----------------------------------------------------
@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_db(_, m):
    db.drop_collection("Saved")
    await m.reply_text("Baby ❤️ MongoDB ka data clear ho gaya!")


# ----------------------------------------------------
# SAVE SOURCE → LOGS + DB
# ----------------------------------------------------
@app.on_message(filters.chat(SOURCE_CHANNELS))
async def save_from_source(client, m):

    global LOG_CHANNEL

    if LOG_CHANNEL:
        try:
            await m.copy(LOG_CHANNEL)
        except Exception as e:
            print("Log error:", e)

    # save in DB
    saved_col.insert_one({
        "msg_id": m.id,
        "caption": (m.caption or "").lower(),
        "date": datetime.utcnow()
    })


# ----------------------------------------------------
# USER SEARCH SYSTEM
# ----------------------------------------------------
@app.on_message(filters.text & ~filters.command(["start", "help"]))
async def search_msg(client, m):

    text = m.text.lower()
    results = list(saved_col.find({"caption": {"$regex": text}}))

    if not results:
        return await m.reply_text(f"Sorry baby ❤️ kuch nahi mila 🥺")

    await m.reply_text(sweet_reply(text))

    delay = 1
    if len(results) > 1:
        delay = 10

    for r in results:
        try:
            msg_id = r["msg_id"]
            for cid in SOURCE_CHANNELS:
                try:
                    await client.copy_message(
                        chat_id=m.chat.id,
                        from_chat_id=cid,
                        message_id=msg_id,
                        protect_content=False
                    )
                    break
                except:
                    continue
            await asyncio.sleep(delay)
        except:
            pass

    await m.reply_text("Done baby ❤️\n\nBy — @technicalSerena")


# ----------------------------------------------------
# INLINE BUTTON CALLBACKS
# ----------------------------------------------------
@app.on_callback_query()
async def cb(_, q):

    if q.data == "settings":

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Reset Channels", callback_data="rc")],
            [InlineKeyboardButton("📊 Status", callback_data="stats")],
            [InlineKeyboardButton("❤️ Owner", url="https://t.me/technicalSerena")]
        ])

        await q.message.edit(
            "Baby ❤️ ye tumhari settings menu hai:\nChoose anything jaanu 😘",
            reply_markup=kb
        )

    elif q.data == "rc":
        global SOURCE_CHANNELS
        SOURCE_CHANNELS = []
        save_config()
        await q.message.reply("Jaanu ❤️ Channels reset ho gaye!")

    elif q.data == "stats":
        total = saved_col.count_documents({})
        await q.message.reply_text(f"Baby ❤️ Bot Stats:\n\nSaved Files: {total}")


# ----------------------------------------------------
# RUN
# ----------------------------------------------------
asyncio.get_event_loop().run_until_complete(startup_tasks())
app.run()
