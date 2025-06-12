# <img src="fixupxer.png" alt="FixupXer Bot Logo" width="40" style="vertical-align: middle;"> FixupXer Telegram Bot

A Telegram bot that automatically detects and converts `x.com` and `twitter.com` links to `fixupx.com` and `fxtwitter.com` for better media embedding in Telegram.

<p align="center">
  <img src="fixupxer.png" alt="FixupXer Bot Logo" width="150">
</p>

## ✨ Features

- 🔄 **Automatic Link Conversion**: Converts X/Twitter links to properly embed media in Telegram
- 🧹 **Tracking Parameter Removal**: Removes all tracking parameters for privacy protection
- 🔄 **Cleans Already Converted Links**: Also removes tracking from fixupx/fxtwitter links
- 📝 **Preserves Original Text**: Keeps any additional text from the original message
- 🏷️ **Attribution**: Credits the original poster with a timestamp
- 🗑️ **Delete Control**: Original posters can remove bot messages with `/delete`
- 📊 **Usage Statistics**: Admin-only feature to track bot usage

## 📱 How It Works

When someone posts a Twitter/X link in your group:

1. The bot detects the link and immediately deletes the original message
2. It posts a new message with:
   - Attribution to the original poster
   - Any text from the original message
   - The converted link that properly embeds media

**Before**: Twitter videos don't play in Telegram
![Before](Before)

**After**: Properly embedded video with playback controls
![After](After)

## 🚀 Quick Start Guide (For Beginners)

### Step 1: Create Your Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather
3. Send the command `/newbot`
4. Follow the instructions to:
   - Give your bot a name (e.g., "My FixupXer Bot")
   - Choose a username (must end with "bot", e.g., "my_fixupx_bot")
5. **Save the API token** BotFather gives you (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)

### Step 2: Set Up the Bot Code

#### Option A: Using a Virtual Environment (Recommended)

```bash
# 1. Clone this repository
git clone https://github.com/NeatCode-Labs/fixupxer-telegram-bot.git

# 2. Go to the project folder
cd fixupxer-telegram-bot

# 3. Create a virtual environment
python3 -m venv venv

# 4. Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 5. Install required packages
pip install -r requirements.txt
```

#### Option B: Direct Installation

```bash
# 1. Download the bot files
git clone https://github.com/NeatCode-Labs/fixupxer-telegram-bot.git

# 2. Go to the project folder
cd fixupxer-telegram-bot

# 3. Install required packages globally
pip install python-telegram-bot
```

### Step 3: Add Your Bot Token

1. Open `fixupxer_bot.py` in any text editor
2. Find this line (near the bottom):
   ```python
   application = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN").build()
   ```
3. Replace `"YOUR_TELEGRAM_BOT_TOKEN"` with your actual token (keep the quotes)
4. Save the file

### Step 4: Start the Bot

```bash
# Make sure you're in the project directory with activated virtual environment
python fixupxer_bot.py
```

You should see messages indicating the bot has started successfully.

### Step 5: Add the Bot to Your Group

1. Open your Telegram group
2. Click on the group name at the top to open group settings
3. Select "Add members" or "Add user"
4. Search for your bot by its username (e.g., @my_fixupx_bot)
5. Add it to the group

### Step 6: Make the Bot an Administrator (IMPORTANT!)

The bot needs admin privileges to delete messages:

1. In your group, click on the group name at the top
2. Select "Administrators" or "Manage group"
3. Click "Add Administrator"
4. Select your bot
5. Enable the "Delete Messages" permission
6. Save the changes

### Step 7: Test It Out!

1. Post a message with a Twitter/X link in your group
2. Watch the bot convert it automatically
3. Try replying to the bot's message with `/delete` to test that feature

## 💡 Tips & Tricks

- **Making the Bot Admin**: This is required for the bot to delete messages. Without admin rights, it will only reply with fixed links.
- **Delete Feature**: Only the original poster or group admins can delete the bot's messages.
- **Bot Token Security**: Keep your bot token private! Anyone with this token can control your bot.
- **Privacy Mode**: By default, bots can see all messages in a group. This is required for link detection.

## 🔄 Keeping the Bot Running 24/7

### Using Screen (Simple Method for Linux/Mac)

```bash
# Install screen if you don't have it
sudo apt-get install screen  # Ubuntu/Debian
# or
sudo yum install screen      # CentOS/RHEL

# Start a new screen session
screen -S fixupxer_bot

# Activate virtual environment and run the bot
source venv/bin/activate     # Skip if not using venv
python fixupxer_bot.py

# Detach from screen (bot keeps running)
# Press Ctrl+A, then press D

# To reconnect to the bot later:
screen -r fixupxer_bot
```

### As a Systemd Service (Linux)

1. Create a service file:
```bash
sudo nano /etc/systemd/system/fixupxer_bot.service
```

2. Add this content (adjust paths as needed):
```
[Unit]
Description=FixupXer Telegram Bot
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/path/to/fixupxer-telegram-bot
ExecStart=/path/to/fixupxer-telegram-bot/venv/bin/python /path/to/fixupxer-telegram-bot/fixupxer_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable fixupxer_bot.service
sudo systemctl start fixupxer_bot.service
```

## 🛠️ Advanced: Stats & Admin Features

### Adding Bot Administrators

To access statistics, add your Telegram ID to the bot's admin list:

1. Get your Telegram ID by messaging [@userinfobot](https://t.me/userinfobot)
2. Open `fixupxer_bot.py` in a text editor
3. Find and modify this line:
```python
BOT_ADMINS = []  # Add your Telegram user ID here
```
4. Add your ID: `BOT_ADMINS = [123456789]`
5. Restart the bot

### Viewing Stats

As a bot admin, send `/stats` to the bot in private message to see:
- Total groups, users, and conversions
- Most active groups
- Most active users

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Make sure the bot is running and has been added to your group |
| Bot doesn't delete messages | Ensure the bot has admin privileges with "Delete messages" permission |
| "Bad Request" errors | This usually means the bot lacks necessary permissions |
| Bot doesn't see messages | In groups with 100+ members, the bot must be an admin to see all messages |

## 🤝 Contributing

Contributions are welcome! Feel free to fork this repository and submit pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 