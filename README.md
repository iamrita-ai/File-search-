# Telegram Unzip Bot

Unzips any document sent to bot (support all formats). Password archive handled, logs to channel, Render-ready Flask web hook.

## Deploy

1. Fork this repo.
2. Setup environment vars on Render:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `OWNER_ID`
   - `LOG_CHANNEL`
   - `FORCE_SUB_CHANNEL`
3. Deploy as web service (Python 3.11).
4. Use `/start` to check.

## Features

- Force join channel
- Zip/rar/7z, encrypted supported (via password)
- All logs in channel
- Inline unzip & password btns
- Render ready

## Notes

- Password-protected zip: Send `/pass mysecret` as reply to button message.
- Owner: `/broadcast`, `/status`
- 
