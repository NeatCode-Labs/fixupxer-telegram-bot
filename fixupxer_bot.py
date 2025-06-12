#!/usr/bin/env python3
import logging
import re
import urllib.parse
import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest

# Enable logging
logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Dictionary to store original user IDs for each bot message
# Format: {bot_message_id: original_user_id}
user_message_map = {}

# Bot owner/admin Telegram user IDs who can access statistics
BOT_ADMINS = []  # Add your Telegram user ID here

# Known tracking parameters from X/Twitter
TRACKING_PARAMS = [
    's', 't', 'twclid', 'ref_src', 'ref_url', 'cxt', 'src', 'partner', 'medium', 
    'source', 'campaign', 'ref', 'feature', 'vertical', 'linkId', 'attr_userid',
    # Add more tracking parameters as you discover them
]

# Initialize database
def init_db():
    """Initialize the SQLite database with required tables"""
    db_path = os.path.join(os.path.dirname(__file__), 'bot_stats.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        chat_id INTEGER PRIMARY KEY,
        chat_title TEXT,
        chat_type TEXT,
        member_count INTEGER DEFAULT 0,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        chat_id INTEGER,
        original_url TEXT,
        converted_url TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (chat_id) REFERENCES chats (chat_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Track user in database
async def track_user(user):
    """Add or update user in the database"""
    if not user:
        return
    
    db_path = os.path.join(os.path.dirname(__file__), 'bot_stats.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update last_active
        cursor.execute(
            "UPDATE users SET username = ?, first_name = ?, last_name = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user.username, user.first_name, user.last_name, user.id)
        )
    else:
        # Insert new user
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user.id, user.username, user.first_name, user.last_name)
        )
    
    conn.commit()
    conn.close()

# Track chat in database
async def track_chat(chat):
    """Add or update chat in the database"""
    if not chat:
        return
    
    db_path = os.path.join(os.path.dirname(__file__), 'bot_stats.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if chat exists
    cursor.execute("SELECT chat_id FROM chats WHERE chat_id = ?", (chat.id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update last_active and title
        cursor.execute(
            "UPDATE chats SET chat_title = ?, last_active = CURRENT_TIMESTAMP WHERE chat_id = ?",
            (chat.title, chat.id)
        )
    else:
        # Insert new chat
        cursor.execute(
            "INSERT INTO chats (chat_id, chat_title, chat_type) VALUES (?, ?, ?)",
            (chat.id, chat.title, chat.type)
        )
    
    conn.commit()
    conn.close()

# Track URL conversion
async def track_conversion(user_id, chat_id, original_url, converted_url):
    """Record a URL conversion in the database"""
    db_path = os.path.join(os.path.dirname(__file__), 'bot_stats.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO conversions (user_id, chat_id, original_url, converted_url) VALUES (?, ?, ?, ?)",
        (user_id, chat_id, original_url, converted_url)
    )
    
    conn.commit()
    conn.close()

# Function to remove tracking parameters from URLs
def clean_url(url):
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    # Remove tracking parameters
    cleaned_params = {k: v for k, v in query_params.items() if k not in TRACKING_PARAMS}
    
    # Rebuild the URL with clean parameters
    clean_query = urllib.parse.urlencode(cleaned_params, doseq=True)
    cleaned_url = urllib.parse.urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        clean_query,
        parsed_url.fragment
    ))
    
    return cleaned_url

# Function to convert x.com to fixupx.com and twitter.com to fxtwitter.com
# Also clean tracking from fixupx.com and fxtwitter.com links
def convert_to_fixupx(url):
    # First, get the domain to check if it's already fixupx or fxtwitter
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # If it's already fixupx.com or fxtwitter.com, just clean the tracking parameters
    if 'fixupx.com' in domain or 'fxtwitter.com' in domain:
        return clean_url(url)
    
    # Otherwise, clean and then convert the domain
    cleaned_url = clean_url(url)
    
    # Convert x.com to fixupx.com
    if 'x.com' in cleaned_url:
        return cleaned_url.replace('x.com', 'fixupx.com')
    
    # Convert twitter.com to fxtwitter.com
    elif 'twitter.com' in cleaned_url:
        return cleaned_url.replace('twitter.com', 'fxtwitter.com')
    
    # If it's none of the above, just return the cleaned URL
    return cleaned_url

# Define URL pattern to match x.com, twitter.com, fixupx.com, and fxtwitter.com links
URL_PATTERN = re.compile(r'https?://(?:www\.)?(x\.com|twitter\.com|fixupx\.com|fxtwitter\.com)/[^\s]+')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm FixupXer Bot. I'll automatically convert any x.com or twitter.com links "
        "to fixupx.com or fxtwitter.com and remove tracking parameters.\n\n"
        "I'll also clean tracking from fixupx.com and fxtwitter.com links if they're directly posted.\n\n"
        "The original poster can delete my message by replying to it with /delete.\n\n"
        "Just add me to your group chat and I'll do the rest!\n\n"
        "Note: I need admin privileges to delete messages."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Add me to your group chat, and I'll automatically detect and convert any "
        "x.com or twitter.com links to fixupx.com or fxtwitter.com.\n\n"
        "I'll also remove tracking parameters from these links to protect your privacy.\n\n"
        "I handle both original Twitter/X links and already converted fixupx/fxtwitter links.\n\n"
        "When someone posts a matching link, I'll:\n"
        "1. Delete their original message\n"
        "2. Post a new message with their username and the fixed link\n\n"
        "The original poster can delete my message by replying to it with /delete.\n\n"
        "Note: I need admin privileges to delete messages."
    )

# Command to show statistics
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot usage statistics to authorized users"""
    user_id = update.message.from_user.id
    
    # Check if user is authorized to see stats
    if user_id not in BOT_ADMINS:
        await update.message.reply_text("You are not authorized to view bot statistics.")
        return
    
    db_path = os.path.join(os.path.dirname(__file__), 'bot_stats.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get general stats
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM chats")
    total_chats = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM conversions")
    total_conversions = cursor.fetchone()[0]
    
    # Get most active chats
    cursor.execute("""
        SELECT c.chat_title, COUNT(*) as count 
        FROM conversions cv
        JOIN chats c ON cv.chat_id = c.chat_id
        GROUP BY c.chat_id
        ORDER BY count DESC
        LIMIT 5
    """)
    active_chats = cursor.fetchall()
    
    # Get most active users
    cursor.execute("""
        SELECT u.username, COUNT(*) as count 
        FROM conversions cv
        JOIN users u ON cv.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY count DESC
        LIMIT 5
    """)
    active_users = cursor.fetchall()
    
    # Generate stats message
    stats_message = f"📊 *Bot Statistics*\n\n"
    stats_message += f"*Total Groups:* {total_chats}\n"
    stats_message += f"*Total Users:* {total_users}\n"
    stats_message += f"*Total Conversions:* {total_conversions}\n\n"
    
    if active_chats:
        stats_message += "*Most Active Groups:*\n"
        for chat in active_chats:
            chat_title = chat[0] or "Unknown"
            stats_message += f"- {chat_title}: {chat[1]} conversions\n"
        stats_message += "\n"
    
    if active_users:
        stats_message += "*Most Active Users:*\n"
        for user in active_users:
            username = user[0] or "Unknown"
            stats_message += f"- @{username}: {user[1]} conversions\n"
    
    conn.close()
    
    await update.message.reply_text(stats_message, parse_mode="Markdown")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /delete command to delete the bot's message."""
    # Check if the message is a reply to a bot message
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user.is_bot:
        # Not a reply to bot message, ignore
        return
    
    # Get the user ID of the person who wants to delete
    user_id = update.message.from_user.id
    # Get the bot message ID that user wants to delete
    bot_message_id = update.message.reply_to_message.message_id
    
    try:
        # Check if the user is the original poster or an admin
        chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        is_admin = chat_member.status in ['administrator', 'creator']
        is_original_poster = bot_message_id in user_message_map and user_message_map[bot_message_id] == user_id
        
        if is_original_poster or is_admin:
            # Delete the bot's message
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=bot_message_id
            )
            # Delete the command message
            await update.message.delete()
            
            # Remove from the map if it exists
            if bot_message_id in user_message_map:
                del user_message_map[bot_message_id]
                
            logger.info(f"Message {bot_message_id} deleted by user {user_id}")
        else:
            # User is not authorized to delete this message
            await update.message.reply_text(
                "You can only delete messages that were originally posted by you.",
                reply_to_message_id=update.message.message_id
            )
            # Delete the unauthorized command after 5 seconds
            context.job_queue.run_once(
                lambda _: context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                ),
                5
            )
    except BadRequest as e:
        logger.error(f"Error deleting message: {e}")
        await update.message.reply_text(
            "Failed to delete the message. I might not have the necessary permissions.",
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the message to find and convert Twitter/X links."""
    message = update.message.text
    
    # Skip processing if the message is from the bot itself
    if update.message.from_user.is_bot:
        return
    
    # Track user and chat for statistics
    await track_user(update.message.from_user)
    await track_chat(update.effective_chat)
    
    # Find all Twitter/X URLs in the message
    matches = URL_PATTERN.findall(message)
    if not matches:
        return
    
    # Get message metadata
    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    date_obj = datetime.fromtimestamp(update.message.date.timestamp())
    date_str = date_obj.strftime("%Y-%m-%d")
    time_str = date_obj.strftime("%H:%M:%S")
    
    # Find and convert each URL
    for match in URL_PATTERN.finditer(message):
        original_url = match.group(0)
        fixed_url = convert_to_fixupx(original_url)
        
        # Only process if the URL was actually changed or if it contains tracking parameters
        # that need to be removed (even if the domain is already fixupx or fxtwitter)
        if fixed_url != original_url:
            try:
                # Create attribution text in italics
                attribution = f"_Originally posted by {username} on date and time of this message:_"
                
                # Extract any additional text from the original message
                # Get the text before and after the URL
                start_idx = match.start()
                end_idx = match.end()
                
                text_before = message[:start_idx].strip()
                text_after = message[end_idx:].strip()
                
                # Combine any user text
                user_text = ""
                if text_before:
                    user_text += text_before + " "
                if text_after:
                    user_text += text_after
                
                # Construct the final message
                final_message = attribution
                
                # Add user text if present
                if user_text.strip():
                    final_message += f"\n\n{user_text.strip()}"
                
                # Add the fixed URL
                final_message += f"\n\n{fixed_url}"
                
                # Post new message with attribution
                chat_id = update.effective_chat.id
                bot_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=final_message,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                
                # Store the original user ID with this bot message ID
                user_message_map[bot_message.message_id] = user.id
                
                # Track conversion for statistics
                await track_conversion(user.id, chat_id, original_url, fixed_url)
                
                # Delete the original message
                await update.message.delete()
                
                # Log the action
                logger.info(f"Converted {original_url} to {fixed_url} for {username}")
                
                # We only handle the first match to avoid duplicate actions
                break
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # If deletion fails (likely due to missing admin privileges), reply instead
                await update.message.reply_text(
                    "I need admin privileges to delete messages. For now, here's the fixed link:\n\n"
                    f"{fixed_url}",
                    disable_web_page_preview=False
                )
                break

def main() -> None:
    """Start the bot."""
    # Initialize the database
    init_db()
    
    # Create the Application with your bot token
    application = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN").build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Add message handler to process all messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 