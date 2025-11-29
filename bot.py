import os, threading, time, re, traceback, asyncio
from flask import Flask
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction
from datetime import datetime

OWNER_ID = 1598576202
LOGS_CHANNEL = -1003039503078
OWNER_USERNAME = "technicalserena"

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

mongo = MongoClient(MONGO_DB_URI)
db = mongo["serena_bot_db"]
users_col = db["users"]
config_col = db["config"]
files_col = db["files"]
premium_col = db["premium"]
bans_col = db["bans"]
config_col.update_one({"_id":"cfg"},{"$setOnInsert":{"sources":[]}},upsert=True)

app = Flask("srv")
@app.route("/")
def _(): return "alive"

def get_sources():
    d = config_col.find_one({"_id":"cfg"})
    return d.get("sources",[]) if d else []

def save_sources(s): config_col.update_one({"_id":"cfg"},{"$set":{"sources":s}},upsert=True)

def save_file(log_msg_id,caption,text,filename,orig_chat,orig_msg):
    try:
        files_col.insert_one({"log_msg_id":int(log_msg_id),"caption":caption or "","text":text or "","filename":filename or "","orig_chat":int(orig_chat),"orig_msg":int(orig_msg),"ts":datetime.utcnow()})
    except: traceback.print_exc()

bot = Client("serena", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start"))
async def start(_,m):
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("💌 Owner",url=f"https://t.me/{OWNER_USERNAME}")],[InlineKeyboardButton("⚙️ Settings",callback_data="open_settings")]])
    await m.reply_text(f"Hello {m.from_user.first_name} 💕\nSend a filename or add source channels.",reply_markup=kb)

@bot.on_message(filters.command("help"))
async def help_cmd(_,m):
    await m.reply_text("Usage:\n• Add bot to source channel(s)\n• /setsource <id>\n• /setlogs <id>\n• DM any keyword to search.\nCommands: /status /broadcast /addpremium /removepremium /plan /settings /clear")

async def send_typing(chat_id,secs=0.6):
    try:
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(secs)
    except: pass

@bot.on_callback_query()
async def cb(_,q):
    data=q.data; uid=q.from_user.id
    if data=="open_settings":
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("📡 Set Source",callback_data="set_source"),InlineKeyboardButton("📁 Set Logs",callback_data="set_logs")],
            [InlineKeyboardButton("🔁 Reset Sources",callback_data="reset_sources"),InlineKeyboardButton("🗑 Clear DB",callback_data="clear_db")],
            [InlineKeyboardButton("📊 Status",callback_data="show_status"),InlineKeyboardButton("💌 Owner",url=f"https://t.me/{OWNER_USERNAME}")]
        ])
        await q.message.edit_text("Settings:",reply_markup=kb)
        return
    if data=="set_source": await q.answer("Send /setsource <id> in private with owner.")
    if data=="set_logs": await q.answer("Send /setlogs <id> in private with owner.")
    if data=="reset_sources":
        if uid!=OWNER_ID: return await q.answer("Owner only",show_alert=True)
        save_sources([]); await q.answer("Reset")
    if data=="clear_db":
        if uid!=OWNER_ID: return await q.answer("Owner only",show_alert=True)
        files_col.delete_many({}); users_col.delete_many({}); premium_col.delete_many({}); await q.answer("Cleared")

@bot.on_message(filters.private & filters.command("setsource"))
async def setsource(_,m):
    if m.from_user.id!=OWNER_ID: return await m.reply_text("Owner only")
    if len(m.command)<2: return await m.reply_text("Usage: /setsource -100...")
    arr=[]
    for a in m.command[1:]:
        try:
            cid = int(a) if not a.startswith("@") else (await bot.get_chat(a)).id
            arr.append(cid)
        except Exception as e:
            await m.reply_text(f"Err {a}: {e}")
    save_sources(arr); await m.reply_text(f"Saved sources: {arr}")

@bot.on_message(filters.private & filters.command("setlogs"))
async def setlogs(_,m):
    if m.from_user.id!=OWNER_ID: return await m.reply_text("Owner only")
    if len(m.command)!=2: return await m.reply_text("Usage: /setlogs <id>")
    try:
        arg=m.command[1]
        cid = int(arg) if not arg.startswith("@") else (await bot.get_chat(arg)).id
        config_col.update_one({"_id":"cfg"},{"$set":{"logs":cid}},upsert=True)
        global LOGS_CHANNEL; LOGS_CHANNEL=cid
        await m.reply_text(f"Logs set to {cid}")
    except Exception as e:
        await m.reply_text(f"Err: {e}")

@bot.on_message(filters.command("addpremium") & filters.user(OWNER_ID))
async def add_premium(_,m):
    if len(m.command)<2: return await m.reply_text("Usage: /addpremium <id>")
    uid=int(m.command[1]); premium_col.update_one({"user_id":uid},{"$set":{"user_id":uid,"premium":True}},upsert=True); await m.reply_text("Added")

@bot.on_message(filters.command("removepremium") & filters.user(OWNER_ID))
async def rem_premium(_,m):
    if len(m.command)<2: return await m.reply_text("Usage: /removepremium <id>")
    uid=int(m.command[1]); premium_col.delete_one({"user_id":uid}); await m.reply_text("Removed")

@bot.on_message(filters.command("plan") & filters.user(OWNER_ID))
async def plan(_,m):
    if len(m.command)<2: return await m.reply_text("Usage: /plan <id>")
    uid=int(m.command[1]); doc=premium_col.find_one({"user_id":uid}); await m.reply_text("Premium" if doc else "Not premium")

@bot.on_message(filters.command("status") & filters.user(OWNER_ID))
async def status(_,m):
    users = users_col.count_documents({}); files = files_col.count_documents({}); sources=get_sources()
    await m.reply_text(f"Users:{users}\nFiles:{files}\nSources:{len(sources)}\nLogs:{LOGS_CHANNEL}\nOwner:@{OWNER_USERNAME}")

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(_,m):
    if not m.reply_to_message: return await m.reply_text("Reply to a message and use /broadcast")
    total=0; fail=0
    for u in users_col.find({},{"user_id":1}):
        try:
            await m.reply_to_message.copy(u["user_id"]); total+=1
        except: fail+=1
    await m.reply_text(f"Done. Success:{total} Fail:{fail}")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_db(_,m):
    files_col.delete_many({}); users_col.delete_many({}); premium_col.delete_many({}); await m.reply_text("Cleared")

@bot.on_message(filters.channel)
async def on_channel(_,message):
    sources=get_sources()
    if not sources: return
    if message.chat.id not in sources: 
        # if bot mentioned reply
        txt = (message.text or message.caption or "")
        if f"@{(await bot.get_me()).username}" in txt:
            try: await message.reply_text("I am here — send me a DM to search files")
            except: pass
        return
    try:
        if LOGS_CHANNEL:
            copied = await message.copy(LOGS_CHANNEL)
            log_id = copied.message_id if hasattr(copied,"message_id") else getattr(copied,"id",None)
            cap = message.caption or ""
            txt = message.text or ""
            fname = (message.document.file_name if message.document else "") or ""
            if log_id:
                save_file(log_id,cap,txt,fname,message.chat.id,message.message_id)
            try: await bot.send_message(LOGS_CHANNEL,"✔ Saved",reply_to_message_id=log_id)
            except: pass
    except Exception as e:
        traceback.print_exc()
        try: await bot.send_message(OWNER_ID,f"Copy error: {e}")
        except: pass

@bot.on_message(filters.private & filters.text)
async def dm_search(_,m):
    q = m.text.strip()
    uid = m.from_user.id
    now = datetime.utcnow()
    users_col.update_one({"user_id":uid},{"$set":{"user_id":uid,"last_seen":now}},upsert=True)
    # assist owner adding source via DM
    if q.startswith("-100") and uid==OWNER_ID:
        try:
            cid=int(q); s=get_sources()
            if cid not in s:
                s.append(cid); save_sources(s); await m.reply_text(f"Source {cid} added")
            else: await m.reply_text("Already exists")
        except: await m.reply_text("Invalid id")
        return
    if not get_sources():
        return await m.reply_text("No source channels configured.")
    regex = re.compile(re.escape(q), re.IGNORECASE)
    cursor = files_col.find({"$or":[{"caption":{"$regex":regex}},{"text":{"$regex":regex}},{"filename":{"$regex":regex}}]}).sort("ts",-1).limit(8)
    results=list(cursor)
    if not results:
        return await m.reply_text("🌸 No Results Found — try different keyword.")
    await send_typing(m.chat.id,0.6)
    sent=0
    for r in results:
        try:
            log_id=int(r["log_msg_id"])
            await bot.copy_message(m.chat.id, LOGS_CHANNEL, log_id)
            sent+=1
            await asyncio.sleep(0.6)
        except: pass
    await m.reply_text(f"✅ Sent {sent} file(s).")

def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)

if __name__=="__main__":
    threading.Thread(target=run_flask,daemon=True).start()
    bot.run()
