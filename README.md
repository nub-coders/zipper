
# File Zipper Bot 📦

A powerful Telegram bot that helps users compress, manage, and uncompress files — with support for password protection, large file handling, and direct link downloads.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/zipper)

[![Deploy to Halvo](https://halvo.nubcoders.com/deploy/button.svg)](https://app.nubcoders.com/deploy?template=https://github.com/nub-coders/zipper)

---

## Features ⚡

- 📁 Compress multiple files into ZIP archives
- 🗜️ Uncompress archives (zip, 7z, tar, rar, etc.)
- 🔐 Password-protected ZIP creation & encrypted archive support
- 📥 Download files from direct links
- 📦 File previews before uncompressing
- 💾 Per-user storage management
- 🔄 Queue system for managing multiple requests
- 📊 User statistics tracking
- 🛑 Cancel individual or all tasks mid-operation

---

## Commands 🤖

| Command | Description |
|---|---|
| `/start` | Start the bot |
| `/help` | Show help guide |
| `/my_files` | List all your files |
| `/fzip` | Compress your files into a ZIP |
| `/unzip` | Uncompress a compressed file |
| `/del` | Delete a file by number |
| `/clear` | Clear all your files |
| `/status` | View stats and active tasks |

---

## Deploy with Docker 🐳

```bash
git clone https://github.com/nub-coders/zipper.git
cd zipper
cp .env.example .env   # fill in your values
docker compose up --build -d
```

---

## Environment Variables 🔧

| Variable | Required | Description |
|---|---|---|
| `API_ID` | ✅ | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `BOT_USERNAME` | ✅ | Bot username (without @) |
| `MONGO_URL` | ❌ | MongoDB connection URI. If unset, the bot uses in-memory storage (data is not persisted across restarts) |
| `FORCE_SUBSCRIBE` | ❌ | Require users to join the support channels before use (default `true`) |

---

## Tech Stack 🛠️

- **Python 3.13.2**
- **Pyrogram** (KurimuzonAkuma fork)
- **MongoDB** (via PyMongo)
- **7-Zip** (`p7zip-full`) for archive operations

---

## Support 💬

- Channel: [@nub_coder_s](https://t.me/nub_coder_s)
- Bot: [@FILEs_COMPRESSOR_BOT](https://t.me/FILEs_COMPRESSOR_BOT)

## License

Released under the [MIT License](LICENSE). Please also comply with Telegram's Bot API Terms of Service.
