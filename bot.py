import os, logging, asyncio, random, datetime
from flask import Flask
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------- CONFIG -----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB = os.getenv("MONGO_DB")
OWNER_ID = 1598576202
LOGS_CHANNEL = -1003286415377
MY_USERNAME = "technicalserena"
PORT = int(os.environ.get("PORT", 10000))

# ---------------- LOGGING -----------------
logging.basicConfig(level=logging.INFO)

# ---------------- KEEP ALIVE --------------
app = Flask(__name__)
@app.route("/")
def home(): return "❤️ Romantic Bot Running Smoothly!"

# ---------------- MONGO -------------------
mongo = AsyncIOMotorClient(MONGO_DB)
db = mongo["BOT_DB"]
files_col = db["files"]
premium_col = db["premium"]

# ---------------- BOT CLIENT --------------
bot = Client("romantic_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- UTILS -------------------
async def typing_effect(msg, text):
    for c in text:
        await msg.edit(msg.text + c)
        await asyncio.sleep(0.02)

# ---------------- START -------------------
@bot.on_message(filters.command("start"))
async def start(_, m):
    btn = [[InlineKeyboardButton("👑 Owner", url=f"https://t.me/{MY_USERNAME}")],
           [InlineKeyboardButton("💞 Search Files", switch_inline_query_current_chat="")]]
    await m.reply_text(
        f"Hello *{m.from_user.first_name}* 💋\nMain tumhari Romantic Assistant ho ❤️\n\n"
        f"Aaj kya help chahiye meri *Sweetheart*? 😘",
        reply_markup=InlineKeyboardMarkup(btn)
    )

# ---------------- ADD / REMOVE PREMIUM ----
@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def add_premium(_, m):
    if not m.reply_to_message: return await m.reply_text("Reply to user to add premium 💞")
    uid = m.reply_to_message.from_user.id
    await premium_col.update_one({"_id": uid}, {"$set": {"is_premium": True}}, upsert=True)
    await m.reply_text("✨ Added to Premium List!")

@bot.on_message(filters.command("rem") & filters.user(OWNER_ID))
async def rem_premium(_, m):
    if not m.reply_to_message: return await m.reply_text("Reply to user to remove 💔")
    uid = m.reply_to_message.from_user.id
    await premium_col.delete_one({"_id": uid})
    await m.reply_text("💔 Removed from Premium Users")

# ---------------- STATUS ------------------
@bot.on_message(filters.command("status"))
async def status(_, m):
    t = datetime.datetime.now().strftime("%I:%M %p")
    await m.reply_text(f"🤖 Bot Alive!\n⏰ Time: {t}\n💾 DB: {await files_col.count_documents({})} files")

# ---------------- HELP --------------------
@bot.on_message(filters.command("help"))
async def help_cmd(_, m):
    txt = ("💘 *Romantic Bot Commands*\n\n"
           "/addpremium – Add user to Premium 👑\n"
           "/rem – Remove Premium ❌\n"
           "/status – Check bot status ⚡\n"
           "/clear – Clear MongoDB 🧹\n"
           "/setting – Manage bot settings ⚙️\n"
           "\nJust type any filename or keyword to search 💞")
    btn = [[InlineKeyboardButton("📬 Contact Owner", url=f"https://t.me/{MY_USERNAME}")]]
    await m.reply_text(txt, reply_markup=InlineKeyboardMarkup(btn))

# ---------------- CLEAR DATABASE ----------
@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_db(_, m):
    await files_col.delete_many({})
    await m.reply_text("🧹 All files cleared successfully!")

# ---------------- SETTINGS ----------------
@bot.on_message(filters.command("setting") & filters.user(OWNER_ID))
async def settings(_, m):
    btn = [
        [InlineKeyboardButton("➕ Set Source Channel", callback_data="set_src"),
         InlineKeyboardButton("➖ Remove Log Channel", callback_data="rem_log")],
        [InlineKeyboardButton("📝 Replace Words", callback_data="replace_words"),
         InlineKeyboardButton("💬 Set Caption", callback_data="set_caption")]
    ]
    await m.reply_text("⚙️ *Bot Settings Panel*", reply_markup=InlineKeyboardMarkup(btn))

# ---------------- SAVE FILES --------------
@bot.on_message(filters.channel)
async def save_files(_, m):
    if m.document:
        name = m.document.file_name.lower()
        await files_col.insert_one({"file_name": name, "file_id": m.document.file_id})
        try:
            await bot.send_message(LOGS_CHANNEL, f"📦 *Saved:* `{name}`")
        except: pass

# ---------------- FILE SEARCH -------------
def match(q, f): return sum(1 for w in q.lower().split() if w in f.lower()) >= 1

@bot.on_message(filters.text & ~filters.command(["start", "help", "status", "setting"]))
async def search(_, m):
    q = m.text
    res = []
    async for d in files_col.find():
        if match(q, d["file_name"]): res.append(d)
    if not res:
        return await m.reply_text("🌸 No Results Found Sweetheart 💔")
    for r in res[:10]:
        await m.reply_document(r["file_id"], caption=f"❤️ File mil gaya *Janu*:\n`{r['file_name']}`")

# ---------------- RUN ---------------------
if __name__ == "__main__":
    bot.start()
    app.run(host="0.0.0.0", port=PORT)
