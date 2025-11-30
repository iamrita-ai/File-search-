import os
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle

# ------------------- ENV ----------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# ------------------- FLASK --------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ------------------- PYROGRAM -----------------
bot = Client(
    "romantic_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.private & filters.text)
async def reply_handler(client, message):
    await message.reply_text(f"❤️ Hello {message.from_user.first_name}! Bot is alive!")

async def main():
    # Start Flask in separate thread so Render detects port
    Thread(target=run_flask).start()
    
    # Start Pyrogram bot
    await bot.start()
    print("Bot started ✅")
    
    # Keep bot running
    await idle()
    
    # Stop bot on shutdown
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
