import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# =========================
# CONSTANTS
# =========================
OWNER_ID = 1598576202
SOURCE_CHANNEL = None
LOGS_CHANNEL = None

# =========================
# ENV VARIABLES (Render)
# =========================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN"))
MONGO_DB_URI = os.getenv("MONGO_DB_URI"))

# =========================
# MONGO SETUP
# =========================
mongo = MongoClient(MONGO_DB_URI)
db = mongo["sweetheart_love_bot"]
config_col = db["bot_config"]

saved = config_col.find_one({"_id": "config"})
if saved:
    SOURCE_CHANNEL = saved.get("source")
    LOGS_CHANNEL = saved.get("logs")

def save_config():
    config_col.update_one(
        {"_id": "config"},
        {"$set": {"source": SOURCE_CHANNEL, "logs": LOGS_CHANNEL}},
        upsert=True
    )

# =========================
# FLASK APP (Render Alive)
# =========================
app = Flask("sweetheart_web_bot")

@app.route("/")
def index():
    return "Sweetheart Bot Running Successfully 💗"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# =========================
# BOT CLIENT
# =========================
bot = Client("sweetheart_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# =========================
# START COMMAND
# =========================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact Owner", url="https://t.me/technicalSerena")],
        [InlineKeyboardButton("Settings", callback_data="open_settings")]
    ])
    await message.reply_text(
        "Hello sweetheart! 👀\nI'm active and ready.",
        reply_markup=keyboard
    )

# =========================
# HELP COMMAND
# =========================
@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "✨ How this bot works:\n\n"
        "• Add me to Source Channel\n"
        "• Set it using /setsource\n"
        "• Set Logs using /setlogs\n"
        "• DM any filename → I will search & send\n\n"
        f"Owner: @technicalSerena"
    )
    await message.reply_text(text)

# =========================
# SETTINGS UI
# =========================
async def send_settings(message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Set Source", callback_data="set_source"),
            InlineKeyboardButton("Set Logs", callback_data="set_logs")
        ],
        [
            InlineKeyboardButton("Clear DB", callback_data="clear_db"),
            InlineKeyboardButton("Owner", url="https://t.me/technicalSerena")
        ]
    ])
    await message.reply_text("Settings Panel:", reply_markup=keyboard)

@bot.on_message(filters.command("settings"))
async def settings_cmd(client, message):
    await send_settings(message)

# =========================
# CALLBACK HANDLER
# =========================
@bot.on_callback_query()
async def callback_handler(client, query):
    global SOURCE_CHANNEL, LOGS_CHANNEL
    data = query.data

    if data == "open_settings":
        await send_settings(query.message)
        return

    if data == "set_source":
        await query.message.reply("Send Source Channel ID (-100)")
        return

    if data == "set_logs":
        await query.message.reply("Send Logs Channel ID (-100)")
        return

    if data == "clear_db":
        config_col.delete_many({})
        SOURCE_CHANNEL = None
        LOGS_CHANNEL = None
        await query.answer("Database Cleared", show_alert=True)
        return

# =========================
# PRIVATE DM FILE SEARCH FIXED
# =========================
@bot.on_message(filters.private & filters.text)
async def private_text_handler(client, message):    
    global SOURCE_CHANNEL, LOGS_CHANNEL
    text = message.text.strip().lower()

    # Set Source/Logs
    if text.startswith("-100"):
        if SOURCE_CHANNEL is None:
            SOURCE_CHANNEL = int(text)
            save_config()
            await message.reply("Source Channel Saved.")
            return
        elif LOGS_CHANNEL is None:
            LOGS_CHANNEL = int(text)
            save_config()
            await message.reply("Logs Channel Saved.")
            return
        else:
            await message.reply("Both channels are already set.")
            return

    # FILE SEARCH (SUPER FIXED)
    if not SOURCE_CHANNEL:
        return await message.reply("Source channel not set.")

    found = False

    async for msg in bot.get_chat_history(SOURCE_CHANNEL, limit=300):

        msg_text = (msg.caption or "").lower() + " " + (msg.text or "").lower()

        if text in msg_text:
            try:
                await msg.copy(message.chat.id)
                found = True
            except:
                pass

    if not found:
        await message.reply("No matching files found.")

# =========================
# FORWARD SOURCE → LOGS
# =========================
@bot.on_message(filters.channel)
async def handle_channel_posts(client, message):
    if message.chat.id == SOURCE_CHANNEL:
        try:
            await message.copy(LOGS_CHANNEL)
        except Exception as e:
            await bot.send_message(OWNER_ID, f"Forward Error: {e}")

# =========================
# RUN BOT + FLASK
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run()
