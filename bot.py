import os
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===================================================
# ONLY FIXED VARIABLES (CODE ME HI RAHENGE)
# ===================================================
OWNER_ID = 1598576202   # Fixed owner ID

# Automatically set later from bot DM
SOURCE_CHANNEL = None
LOGS_CHANNEL = None

# ===================================================
# ENV (Render me fill karoge)
# ===================================================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# ===================================================
# MONGO SETUP
# ===================================================
mongo = MongoClient(MONGO_URL)
db = mongo["love_bot"]
config_col = db["config"]

# Load saved configs
saved = config_col.find_one({"_id": "config"})
if saved:
    SOURCE_CHANNEL = saved.get("source")
    LOGS_CHANNEL = saved.get("logs")

# ===================================================
# CLIENT
# ===================================================
bot = Client("sweetheart_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
# START
# ===================================================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💞 Contact Owner", url="https://t.me/technicalSerena")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")
        ]
    ])

    await message.reply_text(
        f"Hello My Sweetheart ❤️\nI'm ready to serve you!",
        reply_markup=keyboard
    )


# ===================================================
# HELP
# ===================================================
@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "✨ **How to Use This Bot**\n\n"
        "➤ Add me to a Source Channel (No admin needed)\n"
        "➤ Set that channel using /setsource\n"
        "➤ Set Logs Channel using /setlogs\n"
        "➤ Now whenever someone writes filename, bot sends matching file\n\n"
        "🔥 *Bot Features:*\n"
        "• Romantic replies\n"
        "• File search system\n"
        "• Auto-save messages to logs\n"
        "• Owner control panel\n\n"
        f"👑 Owner: @technicalSerena"
    )
    await message.reply_text(text)


# ===================================================
# SETTINGS MENU (2 COLUMN)
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
        "⚙️ **Settings Panel** (2-Column Layout):",
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
        await query.message.reply("📡 Send me Source Channel ID (with -100)")
        return

    if data == "set_logs":
        await query.message.reply("📁 Send me Logs Channel ID (with -100)")
        return

    if data == "clear_db":
        config_col.delete_many({})
        await query.answer("Database Cleared Successfully!", show_alert=True)
        return


# ===================================================
# TEXT HANDLER FOR SETTING CHANNEL IDs
# ===================================================
@bot.on_message(filters.private & filters.text)
async def private_text_handler(client, message):
    global SOURCE_CHANNEL, LOGS_CHANNEL

    text = message.text.strip()

    if text.startswith("-100"):

        # If source is not set -> set source
        if SOURCE_CHANNEL is None:
            SOURCE_CHANNEL = int(text)
            save_config()
            return await message.reply("💞 Source Channel Saved Successfully, Sweetheart!")

        # If source exists but logs not set -> set logs
        elif LOGS_CHANNEL is None:
            LOGS_CHANNEL = int(text)
            save_config()
            return await message.reply("💞 Logs Channel Saved Successfully, Janu!")

        else:
            return await message.reply("Both channels are already set ❤️")

    # Romantic auto reply
    await message.reply("Aww baby tell me more ❤️✨")


# ===================================================
# FORWARD SOURCE → LOGS
# ===================================================
@bot.on_message(filters.channel)
async def handle_channel_posts(client, message):
    global SOURCE_CHANNEL, LOGS_CHANNEL

    if message.chat.id == SOURCE_CHANNEL:
        try:
            await message.copy(LOGS_CHANNEL)
        except Exception as e:
            await bot.send_message(OWNER_ID, f"Error copying message: {e}")


# ===================================================
# RUN BOT
# ===================================================
print("💞 Sweetheart Bot Ready on Render…")
bot.run()
