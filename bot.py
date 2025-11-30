import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running ✅"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Example handler
@bot.on_message(filters.private & filters.text)
async def reply_handler(c, m):
    await m.reply_text(f"❤️ Hello {m.from_user.first_name}! Bot is alive!")

async def main():
    # Start Flask in thread
    Thread(target=run_flask).start()
    # Start Bot
    await bot.start()
    print("Bot started ✅")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
