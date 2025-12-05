import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey 👋 I am alive on Render!")


async def echo_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

    # download document
    file = await document.get_file()
    await file.download_to_drive(file_name)

    await update.message.reply_text(f"Received `{file_name}`", parse_mode="Markdown")

    # send back
    await update.message.reply_document(
        open(file_name, "rb"),
        caption="Here is your file back 🔁"
    )

    os.remove(file_name)


async def not_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any ZIP, PDF or Document 🙂")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, echo_file))
    app.add_handler(MessageHandler(filters.TEXT, not_file))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
