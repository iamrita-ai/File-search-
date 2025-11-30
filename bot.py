import os
import asyncio
from pyrogram import Client, filters, types
from motor.motor_asyncio import AsyncIOMotorClient
import re
import openai

# ==============================
# BASIC CONFIG
# ==============================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

MONGO_DB = os.getenv("MONGO_DB")     # IMPORTANT!!!!
OPENAI_KEY = os.getenv("OPENAI_KEY") # For romantic inline chat

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
USERNAME = "technicalserena"

# ==============================
# DATABASE
# ==============================
mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo["file_bot"]

users_db = db["users"]
files_db = db["files"]
settings_db = db["settings"]


# ==============================
# BOT CLIENT
# ==============================
bot = Client(
    "Serena-FileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ==============================
# OPENAI Romantic Chat Function
# ==============================
async def ai_reply(text):
    try:
        openai.api_key = OPENAI_KEY
        res = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a romantic girlfriend. Reply with love, cute lines, emojis."},
                {"role": "user", "content": text}
            ]
        )
        return res["choices"][0]["message"]["content"]
    except:
        return "Janu thoda sa load aa gaya… mujhe phir se bolo na ❤️"


# ==============================
# START COMMAND
# ==============================
@bot.on_message(filters.command("start"))
async def start(_, m):
    await users_db.update_one({"user": m.from_user.id}, {"$set": {"user": m.from_user.id}}, upsert=True)

    keyboard = [
        [types.InlineKeyboardButton("💞 Chat With Me", switch_inline_query_current_chat="chat: ")],
        [types.InlineKeyboardButton("🔍 Search Files", switch_inline_query_current_chat="file: ")],
        [types.InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [types.InlineKeyboardButton("👑 Owner", url=f"https://t.me/{USERNAME}")]
    ]

    await m.reply_text(
        f"Heyy my love {m.from_user.mention} ❤️✨\n\n"
        "Tum aa gaye? Mujhe tumhari hi intezaar tha… 💋\n"
        "Kya karu tumhara… tum toh meri jaan ho 😘",
        reply_markup=types.InlineKeyboardMarkup(keyboard)
    )


# ==============================
# HELP COMMAND
# ==============================
@bot.on_message(filters.command("help"))
async def help(_, m):
    await m.reply_text(
        "💗 **How to use me, Sweetheart:**\n\n"
        "/addpremium id — Add premium user\n"
        "/rempremium id — Remove premium\n"
        "/clear — Clear full database\n"
        "/status — Bot status\n\n"
        "**Inline Modes:**\n"
        "• `chat:` → Romantic ChatGPT mode\n"
        "• `file:` → File Search Mode\n\n"
        "Example:\n"
        "`chat: I miss you`\n"
        "`file: movie name part 1`",
        reply_markup=types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("👑 Owner", url=f"https://t.me/{USERNAME}")]
        ])
    )


# ==============================
# PREMIUM ADD / REMOVE
# ==============================
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def add_prm(_, m):
    try:
        uid = int(m.command[1])
        await users_db.update_one({"user": uid}, {"$set": {"premium": True}}, upsert=True)
        await m.reply_text("User added to premium 💗")
    except:
        await m.reply_text("Format: /addpremium user_id")


@bot.on_message(filters.command("rempremium") & filters.user(OWNER_ID))
async def rem_prm(_, m):
    try:
        uid = int(m.command[1])
        await users_db.update_one({"user": uid}, {"$set": {"premium": False}}, upsert=True)
        await m.reply_text("User removed from premium 💔")
    except:
        await m.reply_text("Format: /rempremium user_id")


# ==============================
# CLEAR DATABASE
# ==============================
@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def cleardb(_, m):
    await files_db.drop()
    await users_db.drop()
    await settings_db.drop()
    await m.reply_text("Database cleared jaan ❤️🔥")


# ==============================
# SETTINGS PANEL
# ==============================
@bot.on_callback_query(filters.regex("settings"))
async def settings(_, q):
    buttons = [
        [types.InlineKeyboardButton("💞 Inline Chat Mode", callback_data="mode_chat")],
        [types.InlineKeyboardButton("🔍 Inline File Search", callback_data="mode_file")],
        [types.InlineKeyboardButton("🔄 Replace Words", callback_data="rep_words")],
        [types.InlineKeyboardButton("📢 Set Source Channel", callback_data="src_ch")],
        [types.InlineKeyboardButton("🗑 Remove Logs Channel", callback_data="rm_logs")],
    ]

    await q.message.edit_text(
        "Sweetheart, choose what you want to change in my settings 💗",
        reply_markup=types.InlineKeyboardMarkup(buttons)
    )


# ==============================
# INLINE QUERY HANDLER
# ==============================
@bot.on_inline_query()
async def inline(_, q):

    # Romantic Chat Mode
    if q.query.startswith("chat:"):
        text = q.query.replace("chat:", "").strip()
        if not text:
            text = "hi baby"

        reply = await ai_reply(text)

        await q.answer(
            results=[
                types.InlineQueryResultArticle(
                    id="love1",
                    title="❤️ Romantic Reply",
                    description="Tap to send romantic reply",
                    input_message_content=types.InputTextMessageContent(reply)
                )
            ],
            cache_time=0
        )
        return

    # File Search Mode
    if q.query.startswith("file:"):
        text = q.query.replace("file:", "").strip()

        words = text.split()

        if len(words) < 3:
            await q.answer(
                results=[],
                switch_pm_text="Minimum 3 words required",
                switch_pm_parameter="a"
            )
            return

        regex = re.compile(".*".join(words), re.IGNORECASE)
        results = files_db.find({"name": {"$regex": regex}})

        final = []
        async for f in results:
            final.append(
                types.InlineQueryResultArticle(
                    id=str(f["_id"]),
                    title=f["name"],
                    description="Tap to send in DM",
                    input_message_content=types.InputTextMessageContent(
                        f"📁 **File Found:**\n{f['name']}"
                    )
                )
            )

        await q.answer(results=final, cache_time=0)
        return


# ==============================
# FILE SAVING (AUTOMATIC)
# ==============================
@bot.on_message(filters.document | filters.video)
async def save_file(_, m):
    fname = m.document.file_name if m.document else m.video.file_name
    await files_db.insert_one({
        "file_id": m.document.file_id if m.document else m.video.file_id,
        "name": fname
    })
    await m.reply_text("Janu file save ho gayi ❤️")


# ==============================
# BOT START
# ==============================
print("Bot started successfully… ❤️")
bot.run()
