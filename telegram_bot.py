import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
import asyncio
from datetime import datetime
from functools import partial

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger('telegram_bot')
logger.setLevel(logging.INFO)

# Telegram API credentials from environment variables
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # You need to create a bot with BotFather and add this
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")  # Your chat ID to receive notifications

# Create the client
bot = TelegramClient('bot_session', API_ID, API_HASH)
bot_loop = None

async def start_bot():
    """Start the bot and set up event handlers"""
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Telegram notification bot started")
    
    # Send a startup message
    if ADMIN_CHAT_ID:
        await bot.send_message(int(ADMIN_CHAT_ID), "🚀 News-Hack notification bot is now online!")

async def stop_bot():
    """Stop the bot"""
    await bot.disconnect()
    logger.info("Telegram notification bot stopped")

async def notify_new_subscriber(email, source="main"):
    """Notify about a new subscriber"""
    if not ADMIN_CHAT_ID:
        logger.warning("No admin chat ID configured for notifications")
        return

    message = f"🎉 **New Subscriber**\n\n" \
              f"**Email:** {email}\n" \
              f"**Source:** {source}\n" \
              f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await bot.send_message(int(ADMIN_CHAT_ID), message)
    logger.info(f"Sent notification about new subscriber: {email}")

def sync_notify_new_subscriber(email, source="main"):
    """Synchronous wrapper for notify_new_subscriber"""
    global bot_loop
    if bot_loop and bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(notify_new_subscriber(email, source), bot_loop)
        try:
            future.result(10)  # Wait up to 10 seconds for the message to be sent
            return True
        except Exception as e:
            logger.error(f"Failed to send subscriber notification: {e}")
            return False
    else:
        logger.error("Bot loop is not running, cannot send notification")
        return False

async def notify_new_feedback(email, feedback_type, message):
    """Notify about new feedback"""
    if not ADMIN_CHAT_ID:
        logger.warning("No admin chat ID configured for notifications")
        return

    notification = f"📝 **New Feedback**\n\n" \
                   f"**Email:** {email}\n" \
                   f"**Type:** {feedback_type}\n" \
                   f"**Message:**\n{message}\n\n" \
                   f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await bot.send_message(int(ADMIN_CHAT_ID), notification)
    logger.info(f"Sent notification about new feedback from: {email}")

def sync_notify_new_feedback(email, feedback_type, message):
    """Synchronous wrapper for notify_new_feedback"""
    global bot_loop
    if bot_loop and bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(notify_new_feedback(email, feedback_type, message), bot_loop)
        try:
            future.result(10)  # Wait up to 10 seconds for the message to be sent
            return True
        except Exception as e:
            logger.error(f"Failed to send feedback notification: {e}")
            return False
    else:
        logger.error("Bot loop is not running, cannot send notification")
        return False

async def notify_summaries_request(request_id, period, sources):
    """Notify when summaries endpoint is called"""
    if not ADMIN_CHAT_ID:
        logger.warning("No admin chat ID configured for notifications")
        return

    sources_text = sources if sources else "All sources"
    message = f"📊 **Summaries Endpoint Called**\n\n" \
              f"**Request ID:** {request_id}\n" \
              f"**Period:** {period}\n" \
              f"**Sources:** {sources_text}\n" \
              f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await bot.send_message(int(ADMIN_CHAT_ID), message)
    logger.info(f"Sent notification about summaries request: {request_id}")

def sync_notify_summaries_request(request_id, period, sources):
    """Synchronous wrapper for notify_summaries_request"""
    global bot_loop
    if bot_loop and bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(notify_summaries_request(request_id, period, sources), bot_loop)
        try:
            future.result(10)  # Wait up to 10 seconds for the message to be sent
            return True
        except Exception as e:
            logger.error(f"Failed to send summaries notification: {e}")
            return False
    else:
        logger.error("Bot loop is not running, cannot send notification")
        return False

async def notify_insights_request(request_id, topic_count):
    """Notify when insights POST endpoint is called"""
    if not ADMIN_CHAT_ID:
        logger.warning("No admin chat ID configured for notifications")
        return

    message = f"🧠 **Insights Endpoint Called**\n\n" \
              f"**Request ID:** {request_id}\n" \
              f"**Number of Topics:** {topic_count}\n" \
              f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await bot.send_message(int(ADMIN_CHAT_ID), message)
    logger.info(f"Sent notification about insights request: {request_id}")

def sync_notify_insights_request(request_id, topic_count):
    """Synchronous wrapper for notify_insights_request"""
    global bot_loop
    if bot_loop and bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(notify_insights_request(request_id, topic_count), bot_loop)
        try:
            future.result(10)  # Wait up to 10 seconds for the message to be sent
            return True
        except Exception as e:
            logger.error(f"Failed to send insights notification: {e}")
            return False
    else:
        logger.error("Bot loop is not running, cannot send notification")
        return False

async def notify_data_fetcher_completion(telegram_results, rss_results):
    """Notify when data fetcher completes its work"""
    if not ADMIN_CHAT_ID:
        logger.warning("No admin chat ID configured for notifications")
        return

    # Prepare the message
    message = f"🔄 **Data Fetcher Completed**\n\n" \
              f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Add Telegram results
    if telegram_results:
        message += "**Telegram Channels:**\n"
        for channel, message_ids in telegram_results.items():
            channel_name = channel.split('/')[-1] if '/' in channel else channel
            message += f"- {channel_name}: {len(message_ids)} messages\n"
    
    # Add RSS results
    if rss_results:
        message += "\n**RSS Feeds:**\n"
        for feed, message_ids in rss_results.items():
            feed_name = feed.split('//')[-1].split('/')[0]  # Extract domain
            message += f"- {feed_name}: {len(message_ids)} messages\n"
    
    await bot.send_message(int(ADMIN_CHAT_ID), message)
    logger.info("Sent notification about data fetcher completion")

def sync_notify_data_fetcher_completion(telegram_results, rss_results):
    """Synchronous wrapper for notify_data_fetcher_completion"""
    global bot_loop
    if bot_loop and bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(notify_data_fetcher_completion(telegram_results, rss_results), bot_loop)
        try:
            future.result(10)  # Wait up to 10 seconds for the message to be sent
            return True
        except Exception as e:
            logger.error(f"Failed to send data fetcher completion notification: {e}")
            return False
    else:
        logger.error("Bot loop is not running, cannot send notification")
        return False

# Initialize bot in a non-blocking way
def init_bot():
    """Initialize the bot without blocking"""
    global bot_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
    bot_loop = loop
    
    # Start the loop in a background thread
    def run_loop_forever(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    import threading
    thread = threading.Thread(target=run_loop_forever, args=(loop,), daemon=True)
    thread.start()
    
    return loop

# Start the bot if this file is run directly
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the bot
    loop = init_bot()
    try:
        logger.info("Bot is running. Press Ctrl+C to stop.")
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        loop.run_until_complete(stop_bot())
        loop.close() 