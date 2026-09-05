# <img src="fixupxer_round.png" alt="FixupXer Bot Logo" width="40" style="vertical-align: middle;"> FixupXer Telegram Bot

A Telegram bot that removes known tracking parameters from URLs and converts X/Twitter, Instagram and TikTok links to third-party frontends for improved Telegram embeds. Facebook links are cleaned without changing their domain. The local cleaner engine includes platform-specific cleaners for Twitter, Instagram, Facebook, YouTube, TikTok, Reddit, LinkedIn, Amazon, Google Search, Substack, Pinterest, Snapchat, Discord, GitHub, Spotify, eBay, AliExpress and more, plus a generic UTM/click-id remover. Telegram delivery and optional proxy health checks require network access; the cleaning engine itself runs offline on the bot host.

<p align="center">
  <img src="fixupxer_round.png" alt="FixupXer Bot Logo" width="150">
</p>

## Changes in 0.3.2 (2026-09-05)

Instagram cleaning now removes the `stkn` share parameter from Instagram URLs and recognised or configured Instagram proxy URLs. For example, `https://www.instagram.com/reel/Dc4fAOCs97R/?stkn=anBpYnlkeG82MDJz` cleans to `https://www.instagram.com/reel/Dc4fAOCs97R/` before frontend conversion.

This release also closes two existing bot cleaning gaps: `igsi`, already covered by the Android app, and `ig_rid`, listed in [Brave's Instagram cleaning rules](https://github.com/brave/adblock-lists/blob/master/brave-lists/clean-urls.json). Both are existing parameters. For example, `https://www.instagram.com/reel/Da0a2ylvv4z/?igsi=Nm44MGppNTFIZXNw` now cleans to `https://www.instagram.com/reel/Da0a2ylvv4z/`.

Unknown and functional parameters, such as `img_index` and `story_media_id`, remain intact. The existing exact, case-sensitive key policy applies to `stkn`, `igsi` and `ig_rid`: duplicate pairs and keys percent-encoded once are removed; differently cased keys, double-encoded keys and fragment contents are preserved. Other hosts, including retired unsafe frontends, do not receive these Instagram-specific rules.

## ✨ Features

- 🔄 **Automatic Link Conversion**: Cleans and converts X/Twitter, Instagram and TikTok links for improved embeds; Facebook receives tracking removal only
- 🧹 **Tracking Removal**: Removes known platform tracking parameters and generic UTM/click IDs while preserving unknown or functional URL parameters
- 🔁 **Auto‑healing Instagram & TikTok proxies**: Health‑checks each candidate's OpenGraph tags before replying, falls back through the configured list, opens a circuit breaker on consistent failures
- 🎯 **Prefers direct‑serving proxies**: A proxy that 302s back to `instagram.com` (common for `/reel/` paths) is only used as a last resort — the bot keeps probing for a proxy that serves the embed itself, because Telegram doesn't render previews for plain `instagram.com` links
- ♻️ **Migrates recognised legacy proxy URLs**: Known legacy Instagram and TikTok hosts can be redirected to the configured active roster; retired unsafe frontends are excluded
- 🤫 **No spam on already‑clean URLs**: If the cleaner engine and domain rewrite both leave the URL unchanged, the bot stays silent
- 📝 **Preserves Original Text**: Includes surrounding text in the first successful repost; retains the original if complete delivery cannot be confirmed
- 🧵 **Forum Topics**: Keeps reposts in the incoming message's Telegram topic
- 🏷️ **Attribution**: Names the original poster in the repost; Telegram displays the repost's time
- 🗑️ **Delete Control**: Original posters and chat admins can remove bot reposts with `/delete`; ownership is scoped to both chat and message
- 📊 **Usage Statistics**: Admin-only counts and rankings; new conversion records omit URL contents

## 🧭 Commands

| Command | Where to use | Who can use it | What it does |
|---------|--------------|---------------|--------------|
| `/start` | Any chat (DM or group) | Anyone | Sends the welcome/introduction message. |
| `/help` | Any chat | Anyone | Displays a concise help message summarizing features and usage. |
| `/delete` *(reply)* | Reply to a bot repost | Original poster **or** group admins | Deletes that repost when ownership/admin checks and Telegram permissions permit. |
| `/stats` | Private chat recommended | IDs listed in `FIXUPXER_ADMINS` | Shows usage statistics and rankings. |
| `/setproxy` | Private chat only | IDs listed in `FIXUPXER_ADMINS` | Override or auto-pick the active Instagram proxy; `status` shows per-proxy health for both Instagram and TikTok. |

> **Tip:** Grant the bot the group access it needs to receive ordinary messages and the "Delete Messages" permission if you want it to remove originals after successful processing. Send admin commands privately to avoid displaying statistics or proxy settings to the whole group.

### Known limitations

- **Captions and edited messages are not processed.** The bot only handles plain text messages. URLs in photo/video captions, polls, or messages edited after posting are ignored on purpose to keep behaviour predictable.
- **Facebook and YouTube are cleaned without a frontend rewrite.** When tracking is removed, the bot posts a two-link reply with the cleaned and original URLs. Embedding remains subject to the source platform and Telegram.
- **No reply on already‑clean URLs.** Pasting a tracking‑free URL on a non‑converted platform (e.g. `https://example.com/page`) silently does nothing — the bot only intervenes when it has something to add.
- **At most three links requiring processing are attempted per message.** Identical URL strings are deduplicated. If the cap is reached, the original stays in the chat, including additional links.
- **Incomplete delivery keeps the original.** Proxy failures, conversion/send errors, failed metadata writes and oversized replies all prevent automatic deletion. A very long message can receive a compact link-only reply while its complete text remains in the original.
- **Telegram limits still apply.** Reposts are spaced per chat. Explicit `RetryAfter` responses receive at most two retries, each with a requested wait of at most 30 seconds. Ambiguous network failures are not automatically retried because Telegram may already have accepted the message.
- **URL extraction uses visible text.** Links hidden behind a formatted text label are not extracted from Telegram message entities.

## 📱 How It Works

When someone posts a URL in your group:

1. The bot extracts HTTP(S) URLs from plain text, removes duplicate occurrences from its processing list and attempts up to three links that require processing.
2. URL cleaning runs locally. X/Twitter, Instagram and TikTok can also receive a frontend domain rewrite. With health verification enabled, Instagram/TikTok probes contact the configured services; Instagram prefers a frontend that serves the embed directly over a usable redirect fallback.
3. Facebook and other platforms such as YouTube, Reddit and Amazon receive tracking removal without a frontend rewrite. Already-clean URLs that need no rewrite trigger no reply.
4. Each processed link gets its own repost so it can have its own preview, in the same Telegram forum topic where applicable. Surrounding user text accompanies one successful repost. If an earlier send fails, a later attempt can still carry that text.
5. The original is deleted only after complete delivery, successful metadata handling and preservation of the user text. Partial failures, the three-link cap and compact replies for long text retain the original. Missing deletion permissions also leave it intact.

Messages containing hidden links, spoilers or other Telegram formatting remain intact. The bot sends compact replies for ordinary URL spans without copying formatted text. URLs covered by a spoiler, code block, hidden-link label or other formatting are skipped, so a repost cannot expose protected content or change a hidden link's target.


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

Use Python 3.10 or newer. CI runs lint and offline tests on Python 3.10, 3.11 and 3.12.

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

# 3. Install all required packages
python -m pip install -r requirements.txt
```

Polling mode uses `requirements.txt`. For webhook mode, install the optional runtime dependencies as well:

```bash
python -m pip install -r requirements-webhook.txt
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
2. Check the cleaned or converted reply and whether the original is retained under the rules above
3. Try replying to the bot's message with `/delete` to test that feature

## 💡 Tips & Tricks

- **Making the Bot Admin**: This is required for the bot to delete messages. Without admin rights, it will only reply with fixed links.
- **Delete Feature**: Only the original poster or group admins can delete the bot's messages.
- **Bot Token Security**: Keep your bot token private! Anyone with this token can control your bot.
- **Privacy Mode**: Group visibility depends on Telegram's bot privacy mode and administrator settings. If ordinary link messages are not reaching the bot, check those settings with BotFather and your group administrators.

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

Unless statistics are disabled, FixupXer keeps a local SQLite database (`bot_stats.db`) on the device/VPS running the bot. It contains four tables:

* **chats** – `chat_id`, `chat_title`, `chat_type`, timestamps.
* **users** – `user_id`, `username`, first/last names, timestamps.
* **conversions** – timestamp, `user_id`, `chat_id`. The existing `original_url` and `converted_url` columns are retained for compatibility, but new records write `NULL` to both.
* **delete_tokens** – `(chat_id, bot_message_id)`, original poster's `user_id` and a timestamp, used to authorise `/delete` after restarts. Tokens older than 24 hours are pruned when a new token is saved.

The database does not save full message text or media. It does retain Telegram IDs, profile fields, chat titles and usage timestamps, which can be personal data. Existing conversion rows may still contain URLs written by older versions. Upgrading does not erase those rows, existing backups or earlier log files, and there is no automatic retention policy for usage statistics.

For a consistent backup, use SQLite's backup facilities, or stop the bot before taking a database snapshot. Do not remove an active database or its WAL files: doing so can lose statistics and `/delete` ownership state. Any cleanup should be a separate, deliberate maintenance action after a verified backup.

Set `FIXUPXER_DISABLE_STATS=1` before starting the bot to skip database initialisation, statistics writes and persistent delete tokens. This leaves existing files untouched. `/delete` then relies on its bounded in-memory ownership cache and chat-admin checks; cached ownership does not survive a restart.

The bot's operational log messages omit raw URLs, message text, usernames and exception payloads. The `httpx` and `httpcore` loggers are kept at `WARNING` to avoid informational request logs containing Telegram tokens or URL data. This reduces new log exposure; it does not sanitise older logs.

## ⚙️ Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from `@BotFather`. Bot exits if missing. |
| `FIXUPXER_ADMINS` | *(empty)* | Comma-separated Telegram user IDs allowed to use `/stats` and `/setproxy`. |
| `FIXUPXER_DISABLE_STATS` | `0` | Set to `1` to skip SQLite initialisation/writes and persistent delete tokens; existing data remains untouched. |
| `FIXUPXER_DB_PATH` | `<repo>/bot_stats.db` | Override the SQLite path (used in Docker to point at a mounted volume). |
| `FIXUPXER_LOG_LEVEL` | `INFO` | Python `logging` level (`DEBUG`, `INFO`, `WARNING`, …). |
| `FIXUPXER_MODE` | `polling` | Set to `webhook` to use `run_webhook()` instead of long-polling; requires `requirements-webhook.txt`. |
| `FIXUPXER_WEBHOOK_URL` | — | Public HTTPS URL Telegram will post updates to (required when `FIXUPXER_MODE=webhook`). |
| `FIXUPXER_WEBHOOK_LISTEN` | `0.0.0.0` | Webhook bind address. |
| `FIXUPXER_WEBHOOK_PORT` | `8443` | Webhook bind port. |
| `FIXUPXER_WEBHOOK_PATH` | *(bot token)* | URL path component; defaults to the token to make the endpoint unguessable. |
| `FIXUPXER_WEBHOOK_SECRET` | *(none)* | Optional `X-Telegram-Bot-Api-Secret-Token` value enforced by PTB. |
| `FIXUPXER_IG_PROXY_ORDER` | `toinstagram.com, adamlikes.men, instagram7.com` | Ordered Instagram proxy fallback list of validated bare hostnames. |
| `FIXUPXER_TIKTOK_PROXY_ORDER` | `tnktok.com, tfxktok.com, tiktokez.com, kktiktok.com` | Ordered TikTok proxy fallback list (subdomain prefixes like `vm.` are preserved on rewrite). |
| `FIXUPXER_TIKTOK_VERIFY_EMBED` | *(follows `FIXUPXER_IG_VERIFY_EMBED`)* | Set to `0` to skip the TikTok embed health-check. |
| `FIXUPXER_TIKTOK_BG_PROBE_PATH` | `/@cwknix/video/7529264180000509202` | URL path used by the TikTok background probe. Must be a real public video; swap if it is deleted. |
| `FIXUPXER_IG_HEALTH_TTL_SECONDS` | `600` | How long an embed-health probe result is cached. |
| `FIXUPXER_IG_PROBE_INTERVAL_SECONDS` | `120` | Background probe interval; set to `0` to disable. |
| `FIXUPXER_IG_BG_PROBE_PATH` | `/p/DXKIQo0CPjX/` | URL path used by the background probe. Must be a real public post that every configured proxy can serve; swap if the default post is deleted. |
| `FIXUPXER_IG_VERIFY_EMBED` | `1` | Set to `0` to skip the embed health-check (also auto-disabled if `httpx`/`cachetools` are missing). |
| `FIXUPXER_IG_CACHE_BUST` | `0` | Append a `_t=` query param to Instagram URLs to bypass Telegram's link preview cache. |

### Custom Proxy Rosters

`FIXUPXER_IG_PROXY_ORDER` and `FIXUPXER_TIKTOK_PROXY_ORDER` replace the corresponding fallback order at startup. Supply comma-separated bare DNS hostnames, with no scheme, path, credentials or port. Duplicate entries are removed. Invalid names, reserved platform hosts, retired frontends and conflicting Instagram/TikTok aliases are rejected from the roster; an empty valid roster falls back to the built-in defaults.

Configured aliases receive their platform's cleaning rules as well as frontend conversion. Choose a service that supports the expected platform URL paths. `facebookez.com` and `kkinstagram.com`, including their subdomains, are retired and cannot be re-enabled through these settings. A valid hostname or a successful embed probe is not a privacy or security endorsement of the service.

Restart after changing the environment. `/setproxy <domain>` selects a configured Instagram frontend, `/setproxy auto` restores automatic selection, and `/setproxy status` displays Instagram and TikTok probe status. This command does not add a new domain to a roster.

Each probe has a six-second total budget across its redirects, HTML read and
optional video-header check. HTML reads stop at 64 KiB; image/video bodies and
redirect response bodies are not downloaded. Compressed HTML that ignores the
identity-encoding request is rejected rather than decompressed without a bound.
Telegram payload debug logging remains disabled even when the bot's own log
level is DEBUG.

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

The bundled Dockerfile installs the polling dependencies. For a webhook deployment, build an image that installs `requirements-webhook.txt`, set the webhook environment variables and expose the configured port or use a reverse proxy that terminates TLS. Changing `FIXUPXER_MODE` alone does not install webhook dependencies.

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Make sure the bot is running and has been added to your group |
| Bot doesn't delete messages | Ensure the bot has admin privileges with "Delete messages" permission |
| Original remains after a reply | Check for incomplete delivery, long text, more than three links, a metadata failure or missing deletion permissions |
| "Bad Request" errors | Check Telegram permissions, message formatting and size; this error does not always mean missing admin rights |
| Bot doesn't see messages | Check BotFather privacy mode and the bot's group administrator settings |

## 🧪 Local Tests

Install the normal dependencies, then run the offline checks from the repository root:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest ruff
python -m pytest -q
ruff check .
```

`tests/conftest.py` prevents `.env` loading before the bot module is imported, supplies isolated test configuration and assigns a temporary SQLite database to each test. It disables default embed verification and blocks real HTTP transports; tests that exercise HTTP behaviour provide mocked transports. These checks do not need a real Telegram token or a running bot and do not use the deployment database.

Tests cover cleaner fixtures, proxy selection, message delivery failures, `/delete` ownership, Telegram message limits, forum topics, retry bounds and statistics/log privacy. Instagram `stkn`, `igsi` and `ig_rid` regressions also cover duplicate and encoded keys, functional query preservation, host boundaries and custom proxies, with an additional mocked message-delivery regression for `stkn`. CI repeats the offline suite and lint on Python 3.10, 3.11 and 3.12. Live Telegram behaviour and deployment checks are separate from this suite.

## 🤝 Contributing

Contributions are welcome! Feel free to fork this repository and submit pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 

## 🚨 Disclaimer

**Privacy**: URL cleaning runs locally on the machine hosting the bot. Telegram receives messages sent to and from the bot. When Instagram/TikTok verification is enabled, the bot sends requests to configured frontend services and may follow their redirects to retrieve embed or media information. Telegram and users' clients may also fetch linked pages to render previews. These services can receive URL paths and functional parameters; improved embedding does not guarantee greater privacy. Local statistics storage is described above.

**Third-Party Services**: FixupXer depends on public, third-party proxy services for link conversion:

* `fixupx.com` / `fxtwitter.com` – Twitter / X link conversion
* `tnktok.com` (and the `tfxktok.com` / `tiktokez.com` / `kktiktok.com` fallbacks) – TikTok link conversion; the bot picks the first one whose embed health‑check passes; `FIXUPXER_TIKTOK_PROXY_ORDER` is configurable
* `toinstagram.com` / `adamlikes.men` (primaries) and `instagram7.com` (backup) – Instagram embedding frontends. The bot prefers a working frontend that serves the embed directly; `FIXUPXER_IG_PROXY_ORDER` is configurable as described above.

Facebook has no built-in frontend conversion. Retired `facebookez.com` and `kkinstagram.com` hosts are excluded from the configured rosters and receive no platform migration or conversion.

These services are **not operated by NeatCode Labs** and may stop working at any time without notice. We have no control over their availability or functionality.

**Trademarks**: Names such as "Facebook", "Twitter", "X", "Instagram" and others are trademarks of their respective owners. This app is **not affiliated with, endorsed by, or connected to** these services or to Meta Platforms Inc.

**Warranty**: This software is provided *"as is"*, without warranty of any kind. Use at your own risk.

**Note to frontend maintainers**: If you wish to be credited in this README, please contact us via the contact form on our [website](https://neatcodelabs.com/).

---

<div align="center">

**Created with ❤️ by [NeatCode Labs](https://neatcodelabs.com)**  
Visit us for more useful tools and projects!

[![Website](https://img.shields.io/badge/Website-neatcodelabs.com-blue?style=for-the-badge)](https://neatcodelabs.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/neatcodelabs)

</div>
