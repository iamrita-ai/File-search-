import os
import asyncio
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests

# -------------------------
# ENV
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377

# -------------------------
# DATA
# -------------------------
USER_MODE = {}  # gf or search
GF_NAME = "Serena"

WELCOME_TEXT = (
    "Hello Jaanu ❤️ Main tumhari Serena hoon 😘\n\n"
    "Choose mode from /settings"
)

# -------------------------
# FLASK SERVER
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "❤️ Serena GF Bot Running Successfully!"

# -------------------------
# PYROGRAM BOT
# -------------------------
bot = Client(
    "SerenaGF",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
)

# -------------------------
# CHATGPT GF MODE
# -------------------------
def ask_gpt(question):
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a romantic girlfriend. Talk in cute Hindi."
                    },
                    {"role": "user", "content": question}
                ]
            }
        ).json()
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI Error: {e}"

# -------------------------
# FILE SEARCH MODE
# -------------------------
def file_search(q):
    try:
        url = f"https://api.safone.tech/search?query={q}"
        r = requests.get(url).json()
        res = r.get("results", [])

        if not res:
            return "❌ No results found."

        text = "📂 **Search Results:**\n\n"
        for i in res[:10]:
            text += f"📁 **{i['title']}**\n{i['url']}\n\n"

        return text

    except:
        return "Search API error!"

# -------------------------
# SETTINGS PANEL
# -------------------------
@bot.on_message(filters.command("settings"))
async def settings(_, msg):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ GF Chat Mode", callback_data="gf")],
        [InlineKeyboardButton("📂 File Search Mode", callback_data="search")],
        [InlineKeyboardButton("👑 Owner", callback_data="owner")]
    ])
    await msg.reply("⚙️ **Select Mode**", reply_markup=btn)

@bot.on_callback_query()
async def cb(_, q):
    user = q.from_user.id

    if q.data == "gf":
        USER_MODE[user] = "gf"
        await q.message.reply("❤️ GF Chat Mode Activated!")

    elif q.data == "search":
        USER_MODE[user] = "search"
        await q.message.reply("📂 File Search Activated!")

    elif q.data == "owner":
        await q.message.reply(f"👑 Owner ID: `{OWNER_ID}`")

    await q.answer()

# -------------------------
# START
# -------------------------
@bot.on_message(filters.command("start"))
async def start(_, msg):
    USER_MODE[msg.from_user.id] = "gf"
    await msg.reply(f"🌹 **Hello {msg.from_user.first_name}**\n\n{WELCOME_TEXT}")

# -------------------------
# AUTO CHAT HANDLER
# -------------------------
@bot.on_message(filters.text & ~filters.command(["start", "settings"]))
async def reply(_, msg):
    user = msg.from_user.id
    text = msg.text

    # logging
    await bot.send_message(LOGS_CHANNEL, f"👤 {user}:\n{text}")

    mode = USER_MODE.get(user, "gf")

    if mode == "gf":
        reply = ask_gpt(text)
        await msg.reply(reply)
    else:
        reply = file_search(text)
        await msg.reply(reply)

# -------------------------
# RUN BOT + FLASK TOGETHER (NO THREAD NEEDED)
# -------------------------
async def start_services():
    # start pyrogram
    await bot.start()
    print("🔥 Bot Started!")

    # start flask (non-blocking)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    )

    await asyncio.Event().wait()  # keep alive


if __name__ == "__main__":
    asyncio.run(start_services())
