# Serena Unzip Romantic Telegram Bot

- Auto force join multiple channels (env `FORCE_SUB_CHANNELS` - comma separated)
- Har command, unzip, interact pe GPT-based romantic reply (OpenAI API)
- ALL doc formats, password-protected archive support, logs to LOG_CHANNEL
- Download/extract/upload progress bar
- `/broadcast`, `/help`, `/status` implemented

**Env vars (Render dashboard):**
- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `GPT_API_KEY`
- `OWNER_ID`
- `LOG_CHANNEL`
- `FORCE_SUB_CHANNELS` (example: `-10012345,channelusername,serenaunzipbot`)

**Deploy (Render):**
- Python 3.11, web service

**Note:** 
- Password zips: doc bhejne ke baad `/pass <password>` file ke reply me likho!
- Public channel only for correct force join button
