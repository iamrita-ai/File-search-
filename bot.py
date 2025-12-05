import os
import zipfile
import time
from io import BytesIO

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOG_CHANNEL = os.getenv("LOG_CHANNEL")
FORCE_SUB = os.getenv("FORCE_SUB")


# ----------------- Force Subscribe -----------------
async def check_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = await context.bot.get_chat_member(FORCE_SUB, user_id)
    if chat.status in ["left", "kicked"]:
        btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join Channel", url=f"https://t.me/c/{FORCE_SUB[4:]}")]]
        )
        await update.message.reply_text(
            "⚠️ Join channel first to use the bot.",
            reply_markup=btn
        )
        return False
    return True


# ----------------- Start -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_force_sub(update, context):
        return

    txt = (
        "💌 **Zip Extractor Bot**\n\n"
        "Send me a zip file and I will extract it.\n\n"
        "/help — instructions\n"
        "/status — bot info"
    )
    await update.message.reply_text(txt)


# ----------------- Help -----------------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "📌 Send any **.zip** file.\n"
        "You can use password protected zip also.\n\n"
        "Inline buttons:\n"
        "🔓 Unzip\n"
        "🔑 Password unzip\n"
    )
    await update.message.reply_text(txt)


# ----------------- Status -----------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("🟢 Bot Running")


# ----------------- Broadcast -----------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        text = update.message.text.split(" ",1)[1]
    except:
        await update.message.reply_text("Use: /broadcast text")
        return

    await context.bot.send_message(LOG_CHANNEL, f"📣 Broadcast:\n{text}")
    await update.message.reply_text("Done")


# ----------------- Receive ZIP -----------------
async def zip_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_force_sub(update, context):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".zip"):
        await update.message.reply_text("❌ Send .zip file.")
        return

    file = await context.bot.get_file(doc.file_id)
    f = BytesIO()
    await file.download(out=f)
    f.seek(0)

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔓 Unzip", callback_data="unzip_nopass"),
                InlineKeyboardButton("🔑 Password", callback_data="unzip_pass")
            ]
        ]
    )

    context.user_data["zip_file"] = f
    await update.message.reply_text(
        "Choose extraction mode:",
        reply_markup=kb
    )


# ----------------- Inline Callback -----------------
async def unzip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "unzip_nopass":
        await extract_zip(update, context)
    else:
        await query.message.reply_text("Send password:")
        context.user_data["waiting_pass"] = True


# ----------------- Password Handler -----------------
async def password_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_pass"):
        return
    pwd = update.message.text
    context.user_data["waiting_pass"] = False
    await extract_zip(update, context, pwd)


# ----------------- Extraction with Progress -----------------
async def extract_zip(update: Update, context: ContextTypes.DEFAULT_TYPE, password=None):
    f = context.user_data.get("zip_file")
    if not f:
        await update.message.reply_text("File not found.")
        return

    z = zipfile.ZipFile(f)
    names = z.namelist()

    # total size
    total = 0
    for n in names:
        info = z.getinfo(n)
        total += info.file_size

    done = 0
    start_time = time.time()

    msg = await update.message.reply_text("📥 Extracting...")

    for n in names:
        info = z.getinfo(n)
        size = info.file_size

        # read file
        data = z.read(n, pwd=password.encode() if password else None)

        # send file
        await context.bot.send_document(
            chat_id=update.effective_user.id,
            document=BytesIO(data),
            filename=n
        )
        done += size

        # progress
        percent = done / total * 100
        elapsed = time.time() - start_time
        speed = done / elapsed  # bytes/sec
        remain = total - done
        eta = remain / speed if speed > 0 else 0

        def mb(x):
            return round(x / (1024 * 1024), 2)

        txt = (
            f"📥 Extracting...\n"
            f"{mb(done)} MB / {mb(total)} MB ({percent:.1f}%)\n"
            f"Speed: {mb(speed)}/s\n"
            f"ETA: {int(eta)}s"
        )
        await msg.edit_text(txt)

    await msg.edit_text("✔ Done")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(MessageHandler(filters.Document.ALL, zip_receive))
    app.add_handler(CallbackQueryHandler(unzip_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, password_msg))

    app.run_polling()


if __name__ == "__main__":
    main()
