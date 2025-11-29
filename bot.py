import os
import pymongo
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# ===========================
# 🔥 ENV VARIABLES
# ===========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_URL = os.getenv("MONGO_URL")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))

# ===========================
# 🔥 DATABASE
# ===========================
mongo = pymongo.MongoClient(MONGO_URL)
db = mongo["BotDB"]
users = db["users"]

# ===========================
# 🔥 BOT CLIENT
# ===========================
bot = Client(
    "SerenaBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ===========================
# 🔥 Automatically Save Users
# ===========================
@bot.on_message(filters.private & ~filters.command(["start", "help"]))
async def save_user(_, message):
    users.update_one({"_id": message.from_user.id}, {"$set": {"id": message.from_user.id}}, upsert=True)


# ===========================
# 🔥 /start
# ===========================
@bot.on_message(filters.command("start"))
async def start_cmd(_, message):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💝 Owner", url=f"https://t.me/{(await bot.get_users(OWNER_ID)).username}")]
    ])

    await message.reply_text(
        "**Welcome Baby! 💗\nI am your Romantic Telegram Bot.**",
        reply_markup=btn
    )


# ===========================
# 🔥 /addchannel
# ===========================
@bot.on_message(filters.command("addchannel"))
async def add_channel(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    if not message.reply_to_message:
        return await message.reply("Reply to a channel ID!")

    channel_id = message.reply_to_message.text.strip()
    db["channels"].update_one({"_id": 1}, {"$addToSet": {"channels": channel_id}}, upsert=True)

    await message.reply("Channel added successfully.")


# ===========================
# 🔥 /stats
# ===========================
@bot.on_message(filters.command("stats"))
async def stats(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    total = users.count_documents({})
    await message.reply(f"📊 **Bot Stats**\n\nUsers: `{total}`")


# ===========================
# 🔥 /ban
# ===========================
@bot.on_message(filters.command("ban"))
async def ban(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    if not message.reply_to_message:
        return await message.reply("Reply to user to ban!")

    uid = message.reply_to_message.from_user.id
    users.update_one({"_id": uid}, {"$set": {"banned": True}}, upsert=True)
    await message.reply("User banned!")


# ===========================
# 🔥 /unban
# ===========================
@bot.on_message(filters.command("unban"))
async def unban(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    if not message.reply_to_message:
        return await message.reply("Reply to user to unban!")

    uid = message.reply_to_message.from_user.id
    users.update_one({"_id": uid}, {"$set": {"banned": False}}, upsert=True)
    await message.reply("User unbanned!")


# ===========================
# 🔥 /broadcast
# ===========================
@bot.on_message(filters.command("broadcast"))
async def broadcast(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast!")

    b_msg = message.reply_to_message
    total = 0

    for user in users.find():
        try:
            await b_msg.copy(user["id"])
            total += 1
        except:
            pass

    await message.reply(f"Broadcast sent to **{total}** users.")


# ===========================
# 🔥 /clear (Clear MongoDB)
# ===========================
@bot.on_message(filters.command("clear"))
async def clear_db(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only owner allowed!")

    mongo.drop_database("BotDB")
    await message.reply("🔥 MongoDB Database Cleared Successfully!")


# ===========================
# 🔥 Remove Forward Tag
# ===========================
@bot.on_message(filters.forwarded)
async def remove_forward_tag(_, message):
    if message.from_user.id == OWNER_ID:
        msg_id = message.id  # FIXED HERE
        await bot.copy_message(LOG_CHANNEL, message.chat.id, msg_id)


# ===========================
# 🔥 TEXT MATCH BUTTONS
# ===========================
@bot.on_message(filters.text & filters.private)
async def text_match(_, message):
    text = message.text.lower()

    responses = {
        "hi": "Hello Janu 💗",
        "hello": "Hi Baby 💞",
        "love": "I love you too Sweetheart ❤️"
    }

    for key in responses:
        if key in text:
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("💝 Message Owner", url=f"https://t.me/{(await bot.get_users(OWNER_ID)).username}")]
            ])
            return await message.reply_text(responses[key], reply_markup=btn)


# ===========================
# 🔥 Run Bot
# ===========================
print("Bot Running...")
bot.run()
