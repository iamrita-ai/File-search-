import os
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")


# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey 👋 I am Alive! Send me Any file or ZIP")


# Help Command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Just send any ZIP/doc/file & I will reply back 👍")


# Handle Documents & Zip
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    file_name = document.file_name
    file_size = document.file_size

    # typing animation
    await update.message.chat.send_action(constants.ChatAction.UPLOAD_DOCUMENT)

    await update.message.reply_text(
        f"Received:\n📄 `{file_name}`\nSize: {file_size/1024:.2f} KB",
        parse_mode="Markdown"
    )

    # auto send back
    file = await document.get_file()
    await file.download_to_drive(file_name)

    await update.message.reply_document(
        open(file_name, "rb"),
        caption="Here is your file back 🔁"
    )

    os.remove(file_name)


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any ZIP/Document 🙂")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Zip, Docs, Any files
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))

    # Other text
    app.add_handler(MessageHandler(filters.TEXT, handle_unknown))

    app.run_polling()


if __name__ == "__main__":
    main()
