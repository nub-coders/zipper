
# Telegram File Compressor Bot

A powerful Telegram bot that allows users to download, compress, and manage files with queue-based processing and user verification features.

## Features

- **File Download & Compression**: Download files from various sources and compress them into ZIP archives
- **Queue Management**: Premium and regular user queues for efficient file processing
- **User Verification**: Verification system for enhanced storage limits
- **File Management**: List, delete, and organize user files
- **Admin Controls**: Administrative commands for bot management
- **MongoDB Integration**: User data storage and management
- **GoFile Upload**: Large file upload support via GoFile.io

## Bot Commands

### User Commands
- `/start` - Start the bot and show welcome message
- `/help` - Display help information
- `/my_files` - List all files in your directory
- `/del <number>` - Delete a specific file by number
- `/fzip` - Create ZIP archive from your files
- `/clear` - Clear all files from your directory
- `/premium` - Check premium status
- `/status` - Check bot status

### Admin Commands
- `/users` - View user statistics
- `/set` - Configure bot settings
- `/ad` - Manage advertisements
- `/get` - Get bot information
- `/loud` - Broadcast messages
- `/reboot` - Restart bot
- `/skip` - Skip current process
- `/authorize` - Manage user authorization

## File Support

The bot supports various file types:
- Documents
- Photos
- Videos
- Audio files
- Voice messages
- Video notes
- Stickers
- Animations
- Direct download links (HTTP/HTTPS)

## Setup Instructions

### Prerequisites
- Python 3.11+
- MongoDB Atlas account
- Telegram Bot Token (from @BotFather)
- Telegram API credentials

### Configuration

1. **Update `config.py`** with your credentials:
   ```python
   API_ID = your_api_id
   API_HASH = 'your_api_hash'
   BOT_TOKEN = 'your_bot_token'
   ```

2. **MongoDB Setup**:
   - Update the MongoDB connection string in `config.py`
   - Ensure your MongoDB cluster allows connections

3. **Admin Setup**:
   - Add admin user IDs to `admin.txt` (one per line)

### Installation

1. Clone or download the project files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

## Project Structure

```
├── plugins/
│   ├── admin_commands.py      # Admin-only commands
│   ├── admin_handlers.py      # Admin callback handlers
│   ├── basic_commands.py      # Basic user commands
│   ├── callback_handlers.py   # Button callback handlers
│   ├── file_handlers.py       # File processing logic
│   ├── file_operations.py     # File operations utilities
│   ├── installer.py           # Database setup
│   ├── ui_components.py       # UI keyboard layouts
│   ├── user_management.py     # User data management
│   └── verification.py        # User verification system
├── config.py                  # Bot configuration
├── main.py                    # Main bot entry point
├── tools.py                   # Utility functions
├── admin.txt                  # Admin user IDs
└── requirements.txt           # Python dependencies
```

## Key Features

### Queue System
- **Premium Queue**: Priority processing for verified users
- **Regular Queue**: Standard processing for all users
- **Background Processing**: Asynchronous queue management

### User Management
- User registration and data storage
- Verification status tracking
- Storage limit management
- Admin privilege system

### File Operations
- Multi-format file support
- ZIP compression with optional password protection
- File size monitoring
- Automatic cleanup systems

## Storage Limits

- **Free Users**: Limited storage with file management
- **Verified Users**: Enhanced storage limits
- **Premium Users**: Priority queue access

## Error Handling

The bot includes comprehensive error handling for:
- Network connectivity issues
- File processing errors
- Database connection problems
- User input validation

## Deployment

This bot is configured to run on Replit with:
- Python 3.11 runtime
- Cloud Run deployment target
- Automatic dependency management

## Support

For support and updates:
- Join the official channel: @nub_coder_s
- Bot: @FILEs_COMPRESSOR_BOT

## License

This project is open source. Please ensure you comply with Telegram's Bot API terms of service.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Security Notes

- Keep your bot token and API credentials secure
- Regularly update dependencies
- Monitor bot usage and implement rate limiting as needed
- Ensure MongoDB security best practices
