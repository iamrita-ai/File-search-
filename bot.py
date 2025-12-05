import os
import time
import shutil
import patoolib
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL_ID"))
FORCE_CHANNEL = int(os.getenv("FORCE_SUB_CHANNEL"))


# ---------- FORCE SUB CHECK ----------
async def check_force_sub(update: Update):
    user = update.effective_user
    chat_member = await update.effective_chat.get_member(user.id)
    return chat_member


async def force_sub(update: Update):
    keyboard = [
        [InlineKeyboardButton("Join Channel", url=f"https://t.me/{abs(FORCE_CHANNEL)}")]
    ]
    await update.message.reply_text("You must join channel to use the bot",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return False


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # logging
    await context.bot.send_message(LOG_CHANNEL, f"User started: {user.id}")

    await update.message.reply_text(
        f"Hello {user.first_name}, send any ZIP/RAR/7z file.\n"
        f"I will extract it for you ✨"
    )


# ---------- HELP ----------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = """
📌 Commands:

/start - Restart bot
/help - Help menu

👉 Just send ZIP/RAR/7z file
"""
    await update.message.reply_text(txt)


# ---------- FILE HANDLER ----------
async def file_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user = update.effective_user

    if not doc:
        return

    file_name = doc.file_name

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 Extract", callback_data=f"extract|{file_name}"),
                InlineKeyboardButton("🔑 Password", callback_data=f"password|{file_name}")
            ]
        ]
    )

    await context.bot.send_document(
        LOG_CHANNEL,
        document=doc.file_id,
        caption=f"Received: {file_name} from {user.id}"
    )

    await update.message.reply_text(
        f"File: `{file_name}`\nChoose an option:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ---------- CALLBACK ----------
async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    action = data[0]
    filename = data[1]

    file_id = None
    msg = await query.message.reply_text("Downloading...")

    # find document
    doc = query.message.reply_to_message.document
    file = await doc.get_file()
    await file.download_to_drive(filename)

    if action == "extract":
        try:
            folder = filename + "_extract"
            os.makedirs(folder, exist_ok=True)
            patoolib.extract_archive(filename, outdir=folder)

            # send files
            for root, dirs, files in os.walk(folder):
                for f in files:
                    await context.bot.send_document(
                        query.message.chat_id,
                        open(os.path.join(root, f), "rb")
                    )

            await msg.edit_text("Extract Done ✔️")
        except Exception as e:
            await msg.edit_text(f"Error: {e}")
        finally:
            shutil.rmtree(folder, ignore_errors=True)
            os.remove(filename)

    if action == "password":
        await msg.edit_text("Password Feature Coming in Next Update 🔐")


# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, file_received))
    app.add_handler(CallbackQueryHandler(callback_query))

    app.run_polling()


if __name__ == "__main__":
    main()
