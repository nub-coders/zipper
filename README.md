
# File Zipper Bot 📦

A powerful Telegram bot that helps users compress, manage, and uncompress files — with support for password protection, large file handling, and direct link downloads.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/zipper)
[![Deploy to Deplox](https://deplox.nubcoders.com/deploy/button.svg)](https://app.nubcoders.com/deploy?template=https://github.com/nub-coders/zipper)

---

## Features ⚡

- 📁 Compress multiple files into ZIP archives
- �️ Uncompress archives (zip, 7z, tar, rar, etc.)
- 🔐 Password-protected ZIP creation & encrypted archive support
- 📥 Download files from direct links
- 📦 File previews before uncompressing
- 💾 Per-user storage management (up to 10 GB for premium)
- 🔄 Queue system for managing multiple requests
- 📊 User statistics tracking
- 🛑 Cancel individual or all tasks mid-operation
- 💳 Razorpay premium subscription system

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
| `/premium` | View premium plans |

---

## Deploy to Heroku 🚀

### One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/zipper)
[![Deploy to Deplox](https://deplox.nubcoders.com/deploy/button.svg)](https://app.nubcoders.com/deploy?template=https://github.com/nub-coders/zipper)

### Manual Heroku Deploy

1. Clone the repo:
   ```bash
   git clone https://github.com/nub-coders/zipper.git
   cd zipper
   ```

2. Create a Heroku app and add buildpacks **in order**:
   ```bash
   heroku create your-app-name
   heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt
   heroku buildpacks:add --index 2 heroku/python
   ```

3. Set Config Vars:
   ```bash
   heroku config:set API_ID=your_api_id
   heroku config:set API_HASH=your_api_hash
   heroku config:set BOT_TOKEN=your_bot_token
   heroku config:set BOT_USERNAME=your_bot_username
   heroku config:set MONGO_URL=your_mongodb_uri
   heroku config:set RAZORPAY_KEY_ID=your_razorpay_key      # optional
   heroku config:set RAZORPAY_KEY_SECRET=your_razorpay_secret # optional
   ```

4. Deploy the app:
   ```bash
   git push heroku main
   ```

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
| `MONGO_URL` | ✅ | MongoDB connection URI |
| `RAZORPAY_KEY_ID` | ❌ | Razorpay Key ID (for payments) |
| `RAZORPAY_KEY_SECRET` | ❌ | Razorpay Key Secret |

---

## Tech Stack 🛠️

- **Python 3.13.2**
- **Pyrogram** (KurimuzonAkuma fork)
- **MongoDB** (via PyMongo)
- **7-Zip** (`p7zip-full`) for archive operations
- **Razorpay** for payments

---

## Support 💬

- Channel: [@nub_coder_s](https://t.me/nub_coder_s)
- Bot: [@FILEs_COMPRESSOR_BOT](https://t.me/FILEs_COMPRESSOR_BOT)

## License

Open source — please comply with Telegram's Bot API Terms of Service.
