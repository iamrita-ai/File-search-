import os
import re
import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==========================
# 🔐 YOUR DETAILS (Already Filled)
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"

# ==========================
# ❤️ BOT START
# ==========================
app = Client(
    "romantic-bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

romantic_lines = [
    "Janu ❤️", "Baby 😘", "Meri Jaan 💋",
    "Sweetheart 💕", "Miss you ❤️", 
    "Come here baby 😍", "Hug me tight 🤗",
    "Aaj bahut yaad aa rahi ho meri 💞"
]

# ==========================
# 💘 TYPING EFFECT
# ==========================
async def type_reply(msg, text):
    await msg.reply_chat_action("typing")
    await asyncio.sleep(0.7)
    await msg.reply_text(text)

# ==========================
# 🌅 Auto Good Morning / Good Night
# ==========================
async def auto_greet():
    while True:
        t = datetime.now().hour
        if t == 7:
            await app.send_message(OWNER_ID, "Good Morning Sweetheart 🌅❤️")
            await asyncio.sleep(3600)
        elif t == 22:
            await app.send_message(OWNER_ID, "Good Night Baby 🌙💤❤️")
            await asyncio.sleep(3600)
        else:
            await asyncio.sleep(1200)

# ==========================
# ❤️ START
# ==========================
@app.on_message(filters.command("start"))
async def start(_, m):
    await type_reply(
        m,
        f"Hello Sweetheart ❤️\n\nI'm always here for you 😘"
    )
    await m.reply_text(
        "Choose an option baby 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Me", url=f"https://t.me/{MY_USERNAME}")],
            [InlineKeyboardButton("❤️ Help Menu", callback_data="help")]
        ])
    )

# ==========================
# ❤️ HELP
# ==========================
@app.on_callback_query(filters.regex("help"))
async def help_btn(_, q):
    await q.message.edit_text(
        "**❤️ Romantic Bot Commands**\n\n"
        "• /start – Start me 😘\n"
        "• /help – Help Menu ❤️\n"
        "• /broadcast – Send msg to all users\n"
        "• /addpremium – Add a premium user\n"
        "• /rmpremium – Remove a user\n"
        "• /plan – Show plans\n"
        "• /status – Bot stats\n"
        "• /settings – Settings menu\n\n"
        "**Just send any keyword & I’ll find files for you 💋**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 Contact Developer", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, m):
    await help_btn(_, m)

# ==========================
# 📁 SAVE FILES TO LOGS CHANNEL
# ==========================
@app.on_message(filters.document | filters.photo | filters.video | filters.text)
async def save(_, m):
    if m.text and m.text.startswith("/"):
        return  # commands ko ignore
        
    try:
        await m.copy(LOGS_CHANNEL)
        await type_reply(m, f"Saved Meri Jaan ❤️")
    except:
        pass

# ==========================
# 🔍 ADVANCED FILE SEARCH
# ==========================
def match_similar(query, text):
    q = query.lower().split()
    t = text.lower().split()
    hits = sum(1 for w in q if w in t)
    return hits >= 2   # 2 ya 3 word match allowed

@app.on_message(filters.text & ~filters.command(["start","help"]))
async def search(_, m):
    q = m.text.strip()
    results = []

    async for msg in app.search_messages(LOGS_CHANNEL, limit=150):
        content = (msg.caption or msg.text or "").strip()
        if content and match_similar(q, content):
            results.append(msg)

    if not results:
        return await type_reply(m, "🌸 No Results Found — but I'm here, Sweetheart 💕")

    for r in results[:12]:
        try:
            await r.copy(m.chat.id)
            await asyncio.sleep(0.4)
        except:
            pass

# ==========================
# ⭐ OWNER COMMANDS
# ==========================

# 🟢 Broadcast
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def bcast(_, m):
    text = m.text.replace("/broadcast ", "")
    await app.send_message(LOGS_CHANNEL, f"Broadcast: {text}")
    await m.reply("Broadcast sent ❤️")

# 🔵 Add Premium
@app.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def add_premium(_, m):
    await m.reply("User added to Premium 💎")

# 🔴 Remove Premium
@app.on_message(filters.command("rmpremium") & filters.user(OWNER_ID))
async def rm_premium(_, m):
    await m.reply("User removed ❌")

# 📊 Status
@app.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status(_, m):
    await m.reply("Bot Running Smoothly ❤️")

# ⚙️ Settings
@app.on_message(filters.command("settings"))
async def settings(_, m):
    await m.reply(
        "Settings Menu ❤️",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Contact Dev", url=f"https://t.me/{MY_USERNAME}")]
        ])
    )

# ==========================
# 🚀 START BOT
# ==========================
async def main():
    await app.start()
    asyncio.create_task(auto_greet())
    print("Bot Running… ❤️")
    await idle()

from pyrogram import idle
app.run()
