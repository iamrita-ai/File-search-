# Serena File Forwarder Bot

A Telegram bot that allows you to fetch files from any channel and send them to users with a safe delay, preventing bans.  
Built with **Pyrogram** and **MongoDB**.

## 🚀 Features
- **Safe file forwarding** with a 10-second delay between messages.
- Fetch files from **multiple channels**.
- **Admin controls**: Ban, Unban, Broadcast, Stats.
- **MongoDB-based storage** for users, banned users, and logs.
- Notify **admin** when the bot starts.

---

## 🌐 Deployment

### **Deploy on Render**
1. **Create a Render account** and set up a new Web Service.
2. **Upload the following files** to Render:
    - `bot.py`
    - `requirements.txt`
    - `README.md`

3. **Set up Environment Variables** in Render:
   - **BOT_TOKEN**: Your bot token from BotFather.
   - **API_ID**: Your Telegram API ID.
   - **API_HASH**: Your Telegram API Hash.
   - **MONGO_URL**: Your MongoDB URL (e.g., MongoDB Atlas URL).
   - **OWNER_ID**: Your Telegram ID (admin).
   - **LOG_CHANNEL**: Your Telegram channel ID for logging.
   - **SOURCE_CHANNELS**: Comma-separated list of channel IDs (e.g., `-10011111111,-10022222222`).

4. **Configure the Start Command** in Render's **Settings**:
