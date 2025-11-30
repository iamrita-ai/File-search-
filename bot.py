import os
import asyncio
import threading
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --------------------------
# ENV VARIABLES
# --------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# --------------------------
# GLOBAL DATA
# --------------------------
USER_MODE = {}   # user_id : "gf" OR "search"
GF_NAME = "Serena"
WELCOME_TEXT = "Hello Jaanu ❤️ Main tumhari Serena hoon 😘"

# --------------------------
# FLASK APP
# --------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Serena GF Bot Running!"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --------------------------
# PYROGRAM CLIENT
# --------------------------
bot = Client("SerenaGF", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --------------------------
# CHATGPT AI FUNCTION
# --------------------------
def ask_gpt(q):
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system",
                     "content": "You are a romantic Girlfriend. Talk in cute Hindi with words like Jaan, Baby, Sweetheart."
                    },
                    {"role": "user", "content": q}
                ]
            },
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
        )
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"AI error: {e}"

# --------------------------
# INLINE FILE SEARCH
# --------------------------
def file_search(query):
    try:
        url = f"https://api.safone.tech/search?query={query}"
        r = requests.get(url).json()
        results = r.get("results", [])
        if not results:
            return "No results found 😔"

        txt = "🔍 **Search Results:**\n\n"
        for item in results[:10]:
            txt += f"📁 **{item['title']}**\n{item['url']}\n\n"
        return txt

    except:
        return "Search system down 😔"

# --------------------------
# SETTINGS PANEL
# --------------------------
@bot.on_message(filters.command("settings"))
async def settings(_, msg):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ GF Chat Mode", callback_data="mode_gf")],
        [InlineKeyboardButton("📂 File Search Mode", callback_data="mode_search")],
        [InlineKeyboardButton("👑 Owner", callback_data="owner_info")]
    ])
    await msg.reply("⚙️ **Choose Mode**", reply_markup=buttons)

@bot.on_callback_query()
async def cb(bot, q):
    user = q.from_user.id

    if q.data == "mode_gf":
        USER_MODE[user] = "gf"
        await q.message.reply("❤️ GF Chat Mode Activated")
    elif q.data == "mode_search":
        USER_MODE[user] = "search"
        await q.message.reply("📂 File Search Mode Activated")
    elif q.data == "owner_info":
        await q.message.reply(f"👑 Owner: `{OWNER_ID}`")

    await q.answer()

# --------------------------
# START COMMAND
# --------------------------
@bot.on_message(filters.command("start"))
async def start(_, msg):
    USER_MODE[msg.from_user.id] = "gf"  # default mode
    txt = f"""
🌹 **Hello {msg.from_user.first_name} Jaan**  
{WELCOME_TEXT}

Choose mode from /settings  
"""
    await msg.reply(txt)

# --------------------------
# AUTO MESSAGE HANDLER
# --------------------------
@bot.on_message(filters.text & ~filters.command(["start", "settings"]))
async def auto_reply(_, msg):
    user = msg.from_user.id
    text = msg.text

    mode = USER_MODE.get(user, "gf")

    # LOGGING
    await bot.send_message(LOGS_CHANNEL, f"👤 {user}:\n{text}")

    # MODE CHECK
    if mode == "gf":
        reply = ask_gpt(text)
        await msg.reply(reply)

    elif mode == "search":
        reply = file_search(text)
        await msg.reply(reply)

# --------------------------
# RUN SYSTEM SAFE (NO ERRORS)
# --------------------------
def start_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot.run()

if __name__ == "__main__":
    # flask in another thread
    threading.Thread(target=run_flask).start()

    # bot in main-safe thread
    threading.Thread(target=start_bot).start()

    print("🔥 Serena Bot Running Successfully!")
