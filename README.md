# <img src="fixupxer_round.png" alt="FixupXer Bot Logo" width="40" style="vertical-align: middle;"> FixupXer Telegram Bot

A Telegram bot that automatically strips tracking parameters from any URL and converts X/Twitter, Instagram, TikTok and Facebook links to privacy-friendly alternatives (`fixupx.com`/`fxtwitter.com`, `toinstagram.com`/`adamlikes.men`/`instagram7.com`/`kkinstagram.com`, `tnktok.com`, `facebookez.com`) for perfect embeds in Telegram. The cleaner engine ports the full Android FixupXer rule set (~20 platform‑specific cleaners — Twitter, Instagram, Facebook, YouTube, TikTok, Reddit, LinkedIn, Amazon, Google Search, Substack, Pinterest, Snapchat, Discord, GitHub, Spotify, eBay, AliExpress, …) plus a generic UTM/click‑id remover for everything else.

<p align="center">
  <img src="fixupxer_round.png" alt="FixupXer Bot Logo" width="150">
</p>

## ✨ Features

- 🔄 **Automatic Link Conversion**: Cleans & converts X/Twitter, Instagram, TikTok and Facebook links so they embed perfectly in Telegram
- 🧹 **Universal Tracking Removal**: Strips per‑platform tracking from ~20 social/shopping/search platforms (YouTube, Reddit, LinkedIn, Amazon, Spotify, …) plus a generic UTM/click‑id pass for any other host
- 🔁 **Auto‑healing Instagram & TikTok proxies**: Health‑checks each candidate's OpenGraph tags before replying, falls back through the configured list, opens a circuit breaker on consistent failures
- 🎯 **Prefers direct‑serving proxies**: A proxy that 302s back to `instagram.com` (common for `/reel/` paths) is only used as a last resort — the bot keeps probing for a proxy that serves the embed itself, because Telegram doesn't render previews for plain `instagram.com` links
- ♻️ **Rewrites stale Instagram proxy URLs**: A pasted link on a dead Instagram proxy is automatically re‑hosted onto whatever proxy is currently healthy
- 🤫 **No spam on already‑clean URLs**: If the cleaner engine and domain rewrite both leave the URL unchanged, the bot stays silent
- 📝 **Preserves Original Text**: Keeps any additional text from the original message
- 🏷️ **Attribution**: Credits the original poster with a timestamp
- 🗑️ **Delete Control**: Original posters can remove bot messages with `/delete`
- 📊 **Usage Statistics**: Admin-only feature to track bot usage

## 🧭 Commands

| Command | Where to use | Who can use it | What it does |
|---------|--------------|---------------|--------------|
| `/start` | Any chat (DM or group) | Anyone | Sends the welcome/introduction message. |
| `/help` | Any chat | Anyone | Displays a concise help message summarizing features and usage. |
| `/delete` *(reply)* | Group chats | Original poster **or** group admins | When replied to the bot's repost, deletes the bot message (bot needs "Delete Messages" permission). |
| `/stats` | Private chat with the bot | IDs listed in `FIXUPXER_ADMINS` | Shows usage statistics and basic analytics. |
| `/setproxy` | Private chat with the bot | IDs listed in `FIXUPXER_ADMINS` | Override or auto-pick the active Instagram proxy; `status` shows per-proxy health for both Instagram and TikTok. |

> **Tip:** In large groups the bot must have admin rights to see every message and to delete originals with `/delete`.

### Known limitations

- **Captions and edited messages are not processed.** The bot only handles plain text messages. URLs in photo/video captions, polls, or messages edited after posting are ignored on purpose to keep behaviour predictable.
- **YouTube is cleaned but not rewritten.** YouTube already embeds correctly via Google's own oEmbed flow; rewriting the host would add latency with no embed improvement. The bot still strips tracking (`si=`, `feature=`, `utm_*`, …) and posts a 2‑link reply (cleaned URL + dirty original).
- **No reply on already‑clean URLs.** Pasting a tracking‑free URL on a non‑converted platform (e.g. `https://example.com/page`) silently does nothing — the bot only intervenes when it has something to add.
- **At most three URLs per message** are converted. Additional links are dropped to keep the bot's reply small and to avoid Telegram rate-limiting in busy groups.

## 📱 How It Works

When someone posts a URL in your group:

1. The bot extracts up to 3 URLs from the message and runs each through the cleaner engine.
2. For X/Twitter, Instagram, TikTok, and Facebook URLs it also rewrites the host to a privacy‑friendly proxy (`fixupx.com` / `toinstagram.com` / `tnktok.com` / `facebookez.com`) so Telegram renders a proper embed. For Instagram specifically, the bot probes the configured proxies in order and picks the first one that serves the embed itself; a proxy that merely 302s back to `instagram.com` (typical for `/reel/` paths) is kept only as a last-resort fallback.
3. For other platforms (YouTube, Reddit, Amazon, …) it just removes tracking parameters; the host is preserved.
4. If at least one URL was meaningfully changed, the bot posts a new message with attribution + any user text + the cleaned/converted link, then deletes the original. URLs that are already clean trigger no reply.


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

The token is read from the `TELEGRAM_BOT_TOKEN` environment variable. Either export it in your shell, or create a `.env` file next to `fixupxer_bot.py`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
# Optional — comma-separated Telegram IDs of bot admins (for /stats and /setproxy)
FIXUPXER_ADMINS=11111111,22222222
# Optional — set to 1 to disable the local stats database
# FIXUPXER_DISABLE_STATS=1
```

The `.env` file is loaded automatically via `python-dotenv` on startup. Do **not** commit it — `.env` is already in `.gitignore`.

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

1. Post a message with any supported link (e.g., a tweet, Instagram post, or Facebook post) in your group
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

To access `/stats` and `/setproxy`, add your Telegram ID to `FIXUPXER_ADMINS` (comma-separated):

1. Get your Telegram ID by messaging [@userinfobot](https://t.me/userinfobot)
2. Edit your `.env` file (or shell environment) and set:
   ```env
   FIXUPXER_ADMINS=123456789
   # multiple admins:
   # FIXUPXER_ADMINS=123456789,987654321
   ```
3. Restart the bot

### Viewing Stats

As a bot admin, send `/stats` to the bot **in a private chat**. The bot replies with a Markdown-formatted snapshot of:

| Field | What it means |
|-------|---------------|
| **Total Groups** | How many unique Telegram groups/supergroups the bot has been active in. |
| **Total DMs** | How many private chats (DMs with the bot) have triggered a conversion. |
| **Total Users** | Count of distinct users that have triggered a conversion. |
| **Total Conversions** | Number of URLs the bot has cleaned/converted. |
| **Most Active Groups / Users** | Top 5 groups and users ranked by conversions (DMs are excluded from the group ranking). |

#### Where does this data come from?

FixupXer keeps a tiny local SQLite database (`bot_stats.db`) on the same device/VPS that runs the bot.  It contains three tables:

* **chats** – `chat_id`, `chat_title`, `chat_type`, timestamps.
* **users** – `user_id`, `username`, first/last names, timestamps.
* **conversions** – timestamp, `user_id`, `chat_id`, original URL, converted URL.

The database **does NOT store** full message texts, media, or any sensitive personal info beyond the numeric Telegram ID and public profile fields already visible in the chat.  Nothing is ever transmitted to NeatCode Labs or any external server.

You can inspect or delete the database at any time (the bot will recreate empty tables on next start). If you don't want stats at all, set the environment variable `FIXUPXER_DISABLE_STATS=1` before launching the bot to disable all database writes.

## ⚙️ Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from `@BotFather`. Bot exits if missing. |
| `FIXUPXER_ADMINS` | *(empty)* | Comma-separated Telegram user IDs allowed to use `/stats` and `/setproxy`. |
| `FIXUPXER_DISABLE_STATS` | `0` | Set to `1` to skip all SQLite writes (no DB created). |
| `FIXUPXER_DB_PATH` | `<repo>/bot_stats.db` | Override the SQLite path (used in Docker to point at a mounted volume). |
| `FIXUPXER_LOG_LEVEL` | `INFO` | Python `logging` level (`DEBUG`, `INFO`, `WARNING`, …). |
| `FIXUPXER_MODE` | `polling` | Set to `webhook` to use `run_webhook()` instead of long-polling. |
| `FIXUPXER_WEBHOOK_URL` | — | Public HTTPS URL Telegram will post updates to (required when `FIXUPXER_MODE=webhook`). |
| `FIXUPXER_WEBHOOK_LISTEN` | `0.0.0.0` | Webhook bind address. |
| `FIXUPXER_WEBHOOK_PORT` | `8443` | Webhook bind port. |
| `FIXUPXER_WEBHOOK_PATH` | *(bot token)* | URL path component; defaults to the token to make the endpoint unguessable. |
| `FIXUPXER_WEBHOOK_SECRET` | *(none)* | Optional `X-Telegram-Bot-Api-Secret-Token` value enforced by PTB. |
| `FIXUPXER_IG_PROXY_ORDER` | `toinstagram.com, adamlikes.men, instagram7.com, kkinstagram.com` | Ordered Instagram proxy fallback list. |
| `FIXUPXER_TIKTOK_PROXY_ORDER` | `tnktok.com, tfxktok.com, tiktokez.com, kktiktok.com` | Ordered TikTok proxy fallback list (subdomain prefixes like `vm.` are preserved on rewrite). |
| `FIXUPXER_TIKTOK_VERIFY_EMBED` | *(follows `FIXUPXER_IG_VERIFY_EMBED`)* | Set to `0` to skip the TikTok embed health-check. |
| `FIXUPXER_TIKTOK_BG_PROBE_PATH` | `/@cwknix/video/7529264180000509202` | URL path used by the TikTok background probe. Must be a real public video; swap if it is deleted. |
| `FIXUPXER_IG_HEALTH_TTL_SECONDS` | `600` | How long an embed-health probe result is cached. |
| `FIXUPXER_IG_PROBE_INTERVAL_SECONDS` | `120` | Background probe interval; set to `0` to disable. |
| `FIXUPXER_IG_BG_PROBE_PATH` | `/p/DXKIQo0CPjX/` | URL path used by the background probe. Must be a real public post that every configured proxy can serve; swap if the default post is deleted. |
| `FIXUPXER_IG_VERIFY_EMBED` | `1` | Set to `0` to skip the embed health-check (also auto-disabled if `httpx`/`cachetools` are missing). |
| `FIXUPXER_IG_CACHE_BUST` | `0` | Append a `_t=` query param to Instagram URLs to bypass Telegram's link preview cache. |

## 🐳 Docker

A minimal `Dockerfile` and `docker-compose.yml` ship with the project. The compose file mounts a named volume at `/data` so `bot_stats.db` survives container restarts.

```bash
# 1. Create a .env next to docker-compose.yml with at least TELEGRAM_BOT_TOKEN.
#    (See "Environment Variables" above for the full list.)

# 2. Build and run
docker compose up -d --build

# 3. Tail logs
docker compose logs -f
```

For webhook mode, set `FIXUPXER_MODE=webhook` and friends in `.env`, and uncomment the `ports:` block in `docker-compose.yml` (or front the bot with a reverse proxy that terminates TLS).

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

## 🚨 Disclaimer

**Privacy**: This bot processes URLs *locally* on Telegram's servers only for the lifetime of each message. It does **not** collect, store or transmit any user data or URLs to any external servers.

**Third-Party Services**: FixupXer depends on public, third-party proxy services for link conversion:

* `facebookez.com` – Facebook link conversion
* `fixupx.com` / `fxtwitter.com` – Twitter / X link conversion
* `tnktok.com` (and the `tfxktok.com` / `tiktokez.com` / `kktiktok.com` fallbacks) – TikTok link conversion; the bot picks the first one whose embed health‑check passes; `FIXUPXER_TIKTOK_PROXY_ORDER` is configurable
* `toinstagram.com` and `adamlikes.men` (primaries — both embed media + post/reel title & description) and `instagram7.com` / `kkinstagram.com` (backups) – Instagram link conversion via [InstaFix](https://github.com/Wikidepia/InstaFix)‑compatible mirrors. The bot picks the first one whose embed health‑check passes (preferring proxies that serve the embed directly); `FIXUPXER_IG_PROXY_ORDER` is configurable. See `OPERATIONS.md` for how to swap in a new proxy when one of these dies.

These services are **not operated by NeatCode Labs** and may stop working at any time without notice. We have no control over their availability or functionality.

**Trademarks**: Names such as "Facebook", "Twitter", "X", "Instagram" and others are trademarks of their respective owners. This app is **not affiliated with, endorsed by, or connected to** these services or to Meta Platforms Inc.

**Warranty**: This software is provided *"as is"*, without warranty of any kind. Use at your own risk.

**Note to Instagram proxy and facebookez.com maintainers**: If you wish to be credited in this README, please contact us via the contact form on our [website](https://neatcodelabs.com/).

---

<div align="center">

**Created with ❤️ by [NeatCode Labs](https://neatcodelabs.com)**  
Visit us for more useful tools and projects!

[![Website](https://img.shields.io/badge/Website-neatcodelabs.com-blue?style=for-the-badge)](https://neatcodelabs.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/neatcodelabs)

</div>