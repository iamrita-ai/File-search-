import os
import zipfile
import asyncio
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
    filters,
    ContextTypes,
)


TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOG_CHANNEL = os.getenv("LOG_CHANNEL")
FORCE_SUB = os.getenv("FORCE_SUB")


# ---------- Force Subscribe ----------
async def force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_member = await context.bot.get_chat_member(FORCE_SUB, user_id)

    if chat_member.status in ["left", "kicked"]:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Join Channel", url=f"https://t.me/c/{FORCE_SUB[4:]}")]]
        )
        await update.message.reply_text(
            "⚠️ Please join our channel first to use this bot.",
            reply_markup=kb
        )
        return False
    return True


# ---------- Start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_sub(update, context):
        return

    await update.message.reply_text(
        "💌 **Zip Extractor Bot**\n\n"
        "Send me any zip file, I will unzip and send files to your DM.\n\n"
        "/help — For help"
        "\n/status — Check bot status"
    )

    await context.bot.send_message(
        chat_id=LOG_CHANNEL,
        text=f"👤 New User: {update.effective_user.id}"
    )


# ---------- Help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Send me any zip file.\n"
        "/broadcast — Owner only\n"
        "/status — Bot info"
    )


# ---------- Status ----------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    users = "Unknown"
    ping = "OK"

    await update.message.reply_text(
        f"⚙️ **Bot Status**\n\n"
        f"Ping: `{ping}`\n"
        f"Users: `{users}`"
    )


# ---------- Broadcast ----------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        text = update.message.text.split(" ", 1)[1]
    except:
        await update.message.reply_text("Use: /broadcast text")
        return

    await context.bot.send_message(LOG_CHANNEL, f"📣 Broadcast:\n{text}")
    await update.message.reply_text("Broadcast sent!")


# ---------- Receive ZIP ----------
async def handle_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_sub(update, context):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".zip"):
        await update.message.reply_text("❌ Send only .zip files.")
        return

    file = await context.bot.get_file(doc.file_id)
    file_bytes = BytesIO()
    await file.download(out=file_bytes)
    file_bytes.seek(0)

    # inline keyboard
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔓 Unzip", callback_data=f"unzip|nopass"),
                InlineKeyboardButton("🔑 Password", callback_data=f"unzip|pass")
            ]
        ]
    )

    context.user_data["zip_file"] = file_bytes
    await update.message.reply_text(
        "Choose extract option:",
        reply_markup=kb
    )

    await context.bot.send_message(
        chat_id=LOG_CHANNEL,
        text=f"📦 Received ZIP From: {update.effective_user.id}"
    )


# ---------- Inline Callback ----------
async def unzip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    file_bytes = context.user_data.get("zip_file")
    if not file_bytes:
        await query.message.reply_text("File not found.")
        return

    # No password
    if choice == "unzip|nopass":
        await extract_and_send(update, context, file_bytes)
        return

    # Ask for password
    await query.message.reply_text("Send password:")
    context.user_data["waiting_password"] = True


# ---------- Password Message ----------
async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_password"):
        return

    password = update.message.text
    file_bytes = context.user_data.get("zip_file")

    context.user_data["waiting_password"] = False
    await extract_and_send(update, context, file_bytes, password)


# ---------- Extract Files ----------
async def extract_and_send(update, context, file_bytes, password=None):
    try:
        with zipfile.ZipFile(file_bytes) as z:
            for name in z.namelist():
                data = z.read(name, pwd=password.encode() if password else None)
                await context.bot.send_document(
                    chat_id=update.effective_user.id,
                    document=BytesIO(data),
                    filename=name
                )
        await update.message.reply_text("✔ Done.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_zip))
    app.add_handler(CallbackQueryHandler(unzip_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, password_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
