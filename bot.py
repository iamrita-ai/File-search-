import os
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===================================================
# FIXED VARIABLES (Code me hi rahenge)
# ===================================================
OWNER_ID = 1598576202

# Auto-loaded later from MongoDB
SOURCE_CHANNEL = None
LOGS_CHANNEL = None

# ===================================================
# ENV VARIABLES (Render me fill karoge)
# ===================================================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")   # <— FIXED NAME

# ===================================================
# MONGO SETUP
# ===================================================
mongo = MongoClient(MONGO_DB_URI)
db = mongo["sweetheart_love_bot"]
config_col = db["bot_config"]

saved = config_col.find_one({"_id": "config"})
if saved:
    SOURCE_CHANNEL = saved.get("source")
    LOGS_CHANNEL = saved.get("logs")

# ===================================================
# CLIENT
# ===================================================
bot = Client(
    "sweetheart_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ===================================================
# SAVE CONFIG
# ===================================================
def save_config():
    config_col.update_one(
        {"_id": "config"},
        {"$set": {"source": SOURCE_CHANNEL, "logs": LOGS_CHANNEL}},
        upsert=True
    )


# ===================================================
# /start
# ===================================================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💞 Contact My Owner", url="https://t.me/technicalSerena")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")
        ]
    ])

    await message.reply_text(
        "Hello My Sweetheart ❤️\n\n"
        "I'm awake just for you… Tell me what you want baby 😘",
        reply_markup=keyboard
    )


# ===================================================
# /help
# ===================================================
@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "✨ **How to Use Me, Sweetheart**\n\n"
        "➤ Add me to your *Source Channel*\n"
        "➤ Use /setsource to save it\n"
        "➤ Use /setlogs to save logs channel\n"
        "➤ I will auto-forward everything\n\n"
        "🔥 Features:\n"
        "• Romantic girlfriend-like replies ❤️\n"
        "• Fast file search system\n"
        "• Auto logging\n"
        "• Owner control panel\n\n"
        "👑 Owner: @technicalSerena"
    )
    await message.reply_text(text)


# ===================================================
# SETTINGS (2 Column)
# ===================================================
async def send_settings(message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📡 Set Source", callback_data="set_source"),
            InlineKeyboardButton("📁 Set Logs", callback_data="set_logs")
        ],
        [
            InlineKeyboardButton("🗑 Clear DB", callback_data="clear_db"),
            InlineKeyboardButton("👑 Contact Owner", url="https://t.me/technicalSerena")
        ]
    ])

    await message.reply_text(
        "⚙️ **Settings Panel** (Beautiful 2-Column View):",
        reply_markup=keyboard
    )


@bot.on_message(filters.command("settings"))
async def settings_cmd(client, message):
    await send_settings(message)


# ===================================================
# CALLBACK HANDLER
# ===================================================
@bot.on_callback_query()
async def callback_handler(client, query):
    global SOURCE_CHANNEL, LOGS_CHANNEL
    data = query.data

    if data == "open_settings":
        await send_settings(query.message)
        return

    if data == "set_source":
        await query.message.reply("📡 Send me the Source Channel ID (with -100)")
        return

    if data == "set_logs":
        await query.message.reply("📁 Send Logs Channel ID (with -100)")
        return

    if data == "clear_db":
        config_col.delete_many({})
        SOURCE_CHANNEL = None
        LOGS_CHANNEL = None
        await query.answer("Database cleared successfully 💖", show_alert=True)
        return


# ===================================================
# PRIVATE TEXT → SET CHANNEL IDs
# ===================================================
@bot.on_message(filters.private & filters.text)
async def private_text_handler(client, message):
    global SOURCE_CHANNEL, LOGS_CHANNEL
    text = message.text.strip()

    if text.startswith("-100"):

        if SOURCE_CHANNEL is None:
            SOURCE_CHANNEL = int(text)
            save_config()
            return await message.reply("💞 Source Channel Saved Successfully, Sweetheart!")

        elif LOGS_CHANNEL is None:
            LOGS_CHANNEL = int(text)
            save_config()
            return await message.reply("💗 Logs Channel Saved Successfully, Janu!")

        else:
            return await message.reply("Baby… both channels are already set 😘")

    await message.reply("Aww baby… tell me more ❤️✨")


# ===================================================
# SOURCE → LOGS FORWARDING
# ===================================================
@bot.on_message(filters.channel)
async def handle_channel_posts(client, message):
    global SOURCE_CHANNEL, LOGS_CHANNEL

    if message.chat.id == SOURCE_CHANNEL:
        try:
            await message.copy(LOGS_CHANNEL)
        except Exception as e:
            await bot.send_message(OWNER_ID, f"Error copying message:\n{e}")


# ===================================================
# RUN BOT (NO PORT REQUIRED)
# ===================================================
print("💗 Sweetheart Bot is running on Render… No port issues.")
bot.run()
