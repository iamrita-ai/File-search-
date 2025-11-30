import os
import threading
import asyncio
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ---------------------------------------
# ENVIRONMENT VARIABLES
# ---------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# DEFAULTS
GF_NAME = "Serena"
WELCOME_TEXT = "Hello Jaanu ❤️\nMain tumhari Serena GF Bot hoon 😘"

# ---------------------------------------
# FLASK KEEP-ALIVE (RENDER)
# ---------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Serena GF Bot is Running!"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------------------------------
# PYROGRAM BOT
# ---------------------------------------
bot = Client("SerenaGF", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------------------------------
# CHATGPT AI FUNCTION
# ---------------------------------------
def ask_gpt(text):
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a romantic girlfriend. Talk sweet, flirty, emotional, caring, in Hindi with words like Jaanu, Baby, Sweetheart."
                },
                {"role": "user", "content": text}
            ]
        }

        r = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Janu... AI reply me thodi problem aa rahi hai 😔\nError: {e}"

# ---------------------------------------
# HELP COMMAND
# ---------------------------------------
@bot.on_message(filters.command("help"))
async def help_cmd(_, msg):
    txt = f"""
❤️ **Commands Menu — {GF_NAME} GF Bot**

**/start** – Romantic welcome  
**/help** – Commands list  
**/settings** – Open Settings Panel  
**/alive** – Check bot status  
**/owner** – Show bot owner  

🎀 **Owner Commands**
**/broadcast** <msg> – Send message to all users  
**/setname** <name> – Change GF Name  
**/setwelcome** <text> – Change Welcome Message  
"""

    await msg.reply_text(txt)

# ---------------------------------------
# OWNER INFO
# ---------------------------------------
@bot.on_message(filters.command("owner"))
async def owner(_, msg):
    await msg.reply_text(f"👑 **Owner:** `{OWNER_ID}`")

# ---------------------------------------
# ALIVE CHECK
# ---------------------------------------
@bot.on_message(filters.command("alive"))
async def alive(_, msg):
    await msg.reply_text("🔥 **Baby I am Fully Alive & Running For You** 😘")

# ---------------------------------------
# BROADCAST
# ---------------------------------------
@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def bc(_, msg):
    text = msg.text.split(" ", 1)
    if len(text) < 2:
        return await msg.reply("Baby broadcast text do 😘")

    bc_text = text[1]
    await msg.reply("Broadcast Started… ❤️")

    # LOGS CHANNEL = All users storage (for now)
    await bot.send_message(LOGS_CHANNEL, f"📢 Broadcast:\n\n{bc_text}")

# ---------------------------------------
# SET GF NAME
# ---------------------------------------
@bot.on_message(filters.command("setname") & filters.user(OWNER_ID))
async def set_name(_, msg):
    global GF_NAME
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        return await msg.reply("Baby new GF name do 😘")

    GF_NAME = parts[1]
    await msg.reply(f"GF Name Changed to **{GF_NAME}** 💞")

# ---------------------------------------
# SET WELCOME MESSAGE
# ---------------------------------------
@bot.on_message(filters.command("setwelcome") & filters.user(OWNER_ID))
async def set_welcome(_, msg):
    global WELCOME_TEXT
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        return await msg.reply("Janu welcome message bhi do na 😘")

    WELCOME_TEXT = parts[1]
    await msg.reply("New Welcome Message Set! ❤️")

# ---------------------------------------
# SETTINGS PANEL (INLINE BUTTONS)
# ---------------------------------------
@bot.on_message(filters.command("settings"))
async def settings(_, msg):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️ Change GF Name", callback_data="chg_name"),
            InlineKeyboardButton("💌 Change Welcome", callback_data="chg_wel")
        ],
        [
            InlineKeyboardButton("👑 Owner", callback_data="ownr"),
            InlineKeyboardButton("🔥 Alive", callback_data="alv")
        ]
    ])

    await msg.reply_text("⚙️ **Settings Panel**", reply_markup=buttons)

# ---------------------------------------
# CALLBACK HANDLER
# ---------------------------------------
@bot.on_callback_query()
async def cb_handler(_, q):
    global GF_NAME, WELCOME_TEXT

    if q.data == "chg_name":
        await q.message.reply("Use command: /setname <new name> ❤️")
    elif q.data == "chg_wel":
        await q.message.reply("Use command: /setwelcome <text> 💌")
    elif q.data == "ownr":
        await q.message.reply(f"👑 Owner: `{OWNER_ID}`")
    elif q.data == "alv":
        await q.message.reply("🔥 I am alive baby 😘")

    await q.answer()

# ---------------------------------------
# START COMMAND
# ---------------------------------------
@bot.on_message(filters.command("start"))
async def start(_, msg):
    text = f"""
🥰 **Hello {msg.from_user.first_name} Jaanu**

{WELCOME_TEXT}

Mujhse baat karo… flirt karo…  
Main tumhari **{GF_NAME} GF Bot** hoon 💋💞
"""

    await msg.reply_text(text)

# ---------------------------------------
# AUTO AI REPLY
# ---------------------------------------
@bot.on_message(filters.text & ~filters.command(["start", "help", "settings", "alive", "owner", "broadcast", "setname", "setwelcome"]))
async def ai_reply(_, msg):
    user_msg = msg.text

    await bot.send_message(LOGS_CHANNEL, f"👤 {msg.from_user.id}:\n{user_msg}")

    reply = ask_gpt(user_msg)

    await msg.reply_text(reply)

# ---------------------------------------
# RUN BOT + FLASK
# ---------------------------------------
def start_bot():
    print("🔥 Serena GF Bot Started!")
    bot.run()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    threading.Thread(target=start_bot).start()
