import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
import threading

# ------------ FLASK SERVER (RENDER PORT FIX) ------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Telegram Bot is Running on Render Web Service!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# Start Flask in background thread
threading.Thread(target=run_flask).start()

# ------------ STATIC CONFIG ------------
OWNER_ID = 1598576202
LOG_CHANNEL = -1003286415377
BOT_USERNAME = "@Netflix_webseriesbot"
BOT_CREDIT = "@technicalserena"

SOURCE_CHANNELS = [-1003392099253, -1002222222222]

# ------------ ENV LOADING ------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# ------------ MONGO ------------
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["TelegramBotDB"]
users_col = db["Users"]
config_col = db["Config"]

# ------------ BOT CLIENT ------------
app = Client(
    "SerenaRomanticBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ------------ SAFE MESSAGE SENDER ------------
async def safe_send(client, chat_id, text):
    await asyncio.sleep(1)
    await client.send_message(chat_id, text)
    await asyncio.sleep(10)

# ------------ LOAD CHANNEL LIST ------------
async def load_source_channels():
    global SOURCE_CHANNELS
    cfg = await config_col.find_one({"_id": "source_channels"})
    if cfg:
        SOURCE_CHANNELS = cfg["channels"]

# ------------ SAVE CHANNEL LIST ------------
async def save_source_channels():
    await config_col.update_one(
        {"_id": "source_channels"},
        {"$set": {"channels": SOURCE_CHANNELS}},
        upsert=True
    )

# ------------ START CMD ------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id

    await safe_send(client, message.chat.id,
        f"👋 Bot is active and running.\nCredit: {BOT_CREDIT}"
    )

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"last_active": datetime.now()}},
        upsert=True,
    )

    await client.send_message(LOG_CHANNEL, f"🟢 User Started: `{user_id}`")

# ------------ ADD CHANNEL ------------
@app.on_message(filters.command("add_channel") & filters.user(OWNER_ID))
async def add_channel_cmd(client, message):
    global SOURCE_CHANNELS
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Send Channel ID also.\nExample:\n`/add_channel -1001234567890`")

        new_channel = int(parts[1])
        SOURCE_CHANNELS.append(new_channel)
        await save_source_channels()

        await message.reply(f"✔ Channel Added: `{new_channel}`")
        await client.send_message(LOG_CHANNEL, f"➕ New Source Channel Added: `{new_channel}`")

    except Exception as e:
        await message.reply(f"Error: {e}")

# ------------ FORWARD LOGIC ------------
@app.on_message(filters.channel)
async def channel_forward(client, message):
    global SOURCE_CHANNELS

    if message.chat.id not in SOURCE_CHANNELS:
        return

    try:
        await message.copy(LOG_CHANNEL)
        await safe_send(client, LOG_CHANNEL, "✔ File saved successfully.")
    except Exception as e:
        await safe_send(client, LOG_CHANNEL, f"❌ Error: {e}")

# ------------ BROADCAST ------------
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(client, message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await message.reply("Please provide text to send.")

    count = 0
    async for user in users_col.find({}):
        try:
            await safe_send(client, user["user_id"], text)
            count += 1
        except:
            pass

    await message.reply(f"Broadcast sent to {count} users.")

# ------------ ALIVE CHECK ------------
@app.on_message(filters.command("alive"))
async def alive_cmd(client, message):
    await message.reply("🟢 Bot is running normally.")

# ------------ RUN ------------
print("Booting bot... loading DB Channels...")
asyncio.get_event_loop().run_until_complete(load_source_channels())
print("Source Channels Loaded:", SOURCE_CHANNELS)
print("Bot Started Successfully.")

app.run()
