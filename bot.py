import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------------------
# ENVIRONMENT VARIABLES
# ---------------------------
BOT_TOKEN   = os.getenv("BOT_TOKEN")         # Your Bot Token
API_ID      = int(os.getenv("API_ID"))      # Your API ID
API_HASH    = os.getenv("API_HASH")         # Your API HASH
MONGO_URL   = os.getenv("MONGO_URL")        # MongoDB URL

# ---------------------------
# Pre-configured Settings
# ---------------------------
OWNER_ID    = 1598576202                     # Your Telegram ID (Admin)
LOG_CHANNEL = -1003286415377                 # Log channel ID (where all logs will go)
SOURCE_CHANNELS = -1003392099253, -1002222222222  # List of source channel IDs from where bot will fetch files

# ---------------------------
# Pyrogram Client Setup
# ---------------------------
app = Client(
    "Serena_FileBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# ---------------------------
# MongoDB Setup
# ---------------------------
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["SERENA_FILEBOT"]
users_col = db["users"]
ban_col = db["banned"]

# ---------------------------
# Log Function
# ---------------------------
async def log(text):
    try:
        await app.send_message(LOG_CHANNEL, text)
    except Exception as e:
        pass

# ---------------------------
# Ban Check Function
# ---------------------------
async def is_banned(uid):
    return await ban_col.find_one({"user": uid}) is not None

# ---------------------------
# Send File with 10-second Delay
# ---------------------------
async def safe_send_file(msg, user_id):
    try:
        await msg.copy(user_id)
        await asyncio.sleep(10)  # Delay between files
    except Exception as e:
        await log(f"Error: {e}")

# ---------------------------
# Search + Send Function
# ---------------------------
async def search_and_send(channel_id, user_id):
    try:
        await log(f"Searching in {channel_id} for {user_id}")

        count = 0
        async for msg in app.search_messages(channel_id, limit=50):
            if msg.document or msg.video or msg.audio:
                await safe_send_file(msg, user_id)
                await safe_send_file(msg, LOG_CHANNEL)  # Save log in LOG channel
                count += 1

        if count == 0:
            await app.send_message(user_id, "No matching files found. 😔")

    except Exception as e:
        await app.send_message(user_id, f"Error: {str(e)}")
        await log(str(e))

# ---------------------------
# /alive Command (Bot is Active)
# ---------------------------
@app.on_message(filters.command("alive") & filters.user(OWNER_ID))
async def alive(_, msg):
    await msg.reply("🟢 Bot is Active! ✓")

# ---------------------------
# /start Command (Initial message)
# ---------------------------
@app.on_message(filters.command("start"))
async def start(_, msg: Message):
    if await is_banned(msg.from_user.id):
        return await msg.reply("⚠️ You are banned from using this bot.")

    await users_col.update_one({"user": msg.from_user.id}, {"$set": {"user": msg.from_user.id}}, upsert=True)

    await msg.reply(
        "🤖 Hello! I am Serena File Bot.\n"
        "Send me any channel ID (starting with -100) and I will fetch similar files for you.\n\n"
        "Bot by: @technicalserena\n\n"
        "Commands:\n"
        "/alive - Check if the bot is online\n"
        "/ban <user_id> - Ban a user\n"
        "/unban <user_id> - Unban a user\n"
        "/broadcast <message> - Send a broadcast to all users\n"
        "/stats - Get bot stats"
    )

# ---------------------------
# Handle Channel ID (Fetch Files)
# ---------------------------
@app.on_message(filters.text & ~filters.command([]))
async def handle(_, msg: Message):
    uid = msg.from_user.id
    if await is_banned(uid):
        return await msg.reply("⚠️ You are banned.")

    text = msg.text.strip()

    if not text.startswith("-100"):
        return await msg.reply("❌ Invalid channel ID format. Make sure it starts with -100.")

    await msg.reply("🔍 Searching for files…")
    await search_and_send(int(text), uid)

# ---------------------------
# Admin: Ban Command
# ---------------------------
@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban(_, msg):
    if len(msg.command) < 2:
        return await msg.reply("⚠️ Usage: /ban <user_id>")
    uid = int(msg.command[1])
    await ban_col.insert_one({"user": uid})
    await msg.reply(f"⚠️ Banned {uid}.")

# ---------------------------
# Admin: Unban Command
# ---------------------------
@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban(_, msg):
    if len(msg.command) < 2:
        return await msg.reply("⚠️ Usage: /unban <user_id>")
    uid = int(msg.command[1])
    await ban_col.delete_one({"user": uid})
    await msg.reply(f"✅ Unbanned {uid}.")

# ---------------------------
# Admin: Broadcast Command
# ---------------------------
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(_, msg):
    if len(msg.command) < 2:
        return await msg.reply("⚠️ Usage: /broadcast <message>")

    text = msg.text.split(" ", 1)[1]
    sent = 0

    async for user in users_col.find({}):
        try:
            await app.send_message(user["user"], text)
            sent += 1
            await asyncio.sleep(0.3)
        except:
            pass

    await msg.reply(f"📣 Broadcast sent to {sent} users.")

# ---------------------------
# Admin: Stats Command
# ---------------------------
@app.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats(_, msg):
    users = await users_col.count_documents({})
    banned = await ban_col.count_documents({})
    await msg.reply(f"👥 Total Users: {users}\n🚫 Banned Users: {banned}")

# ---------------------------
# Notify Owner When Bot Starts
# ---------------------------
@app.on_ready()
async def notify_start():
    try:
        await app.send_message(OWNER_ID, "🚀 Bot is Active Now! 💥")
    except:
        pass

# ---------------------------
# Run the Bot
# ---------------------------
app.run()
