import asyncio
from flask import Flask
from pyrogram import Client

app = Flask("bot")

@app.route("/")
def home():
    return "Bot is alive ❤️"

BOT = Client(
    "serena_bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

async def main():
    # start flask in background
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))))

    # start pyrogram bot
    await BOT.start()
    print("🔥 Bot started")

    # keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
