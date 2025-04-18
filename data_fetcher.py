import traceback
import asyncio
import os
import sqlite3
import logging
import sys
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
import telethon.errors
from parser import extract_summary  # Import the extraction function

# Configure logging with full detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
    handlers=[
        logging.FileHandler("telegram_fetcher.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded from .env file")

# Telegram API credentials from environment variables
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone_number = os.getenv("TELEGRAM_PHONE_NUMBER")
logger.info(f"Telegram credentials loaded: API ID: {api_id}, Phone: {phone_number}")

# Configuration
messages_limit = 100  # Number of messages to fetch per request
session_file = "telegram_session"
DATABASE = 'sources.db'
logger.info(f"Configuration set: messages_limit={messages_limit}, session_file={session_file}, database={DATABASE}")

def get_db_connection():
    """Create and return a database connection"""
    logger.debug("Opening database connection to %s", DATABASE)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    logger.debug("Database connection established")
    return conn

def extract_links_from_entities(message):
    """
    Extracts links from MessageEntityTextUrl and MessageEntityUrl entities.
    Returns a list of extracted URLs.
    """
    logger.debug(f"Extracting links from message ID: {message.id}")
    links = []
    if message.entities:
        logger.debug(f"Message has {len(message.entities)} entities")
        for entity in message.entities:
            if hasattr(entity, 'url') and hasattr(entity, 'offset') and hasattr(entity, 'length'):
                offset = entity.offset
                length = entity.length
                url = entity.url
                logger.debug(f"Found URL entity: {url} at offset {offset}, length {length}")
                links.append(url)
            elif hasattr(entity, 'offset') and hasattr(entity, 'length') and not hasattr(entity, 'url'):
                offset = entity.offset
                length = entity.length
                if 0 <= offset < len(message.message):
                    url = message.message[offset:offset + length]
                    if url.startswith(('http://', 'https://')):
                        logger.debug(f"Found URL text: {url} at offset {offset}, length {length}")
                        links.append(url)
    logger.debug(f"Extracted {len(links)} links from message: {links}")
    return links

def serialize_message(message, channel_url):
    """
    Serializes a Telethon Message object to a dictionary, handling various data types
    and extracting links from entities. Includes the channel URL and Telegram ID.
    """
    logger.debug(f"Serializing message ID: {message.id} from channel: {channel_url}")
    links = extract_links_from_entities(message)
    message_data = {
        "internal_id": None,  # Will be populated later if stored in DB
        "telegram_id": message.id,
        "channel_url": channel_url,
        "date": message.date.isoformat() if message.date else None,
        "text": message.message,
        "links": links,
        "link_summaries": {}  # Initialize empty dictionary for link summaries
    }
    logger.debug(f"Serialized message data: {message_data}")
    return message_data

async def fetch_channel_messages_since(client, entity, since_date, channel_url):
    """Fetches messages from a Telegram channel since a given date.

    Args:
        client: The Telethon client.
        entity: The Telegram channel entity.
        since_date: The datetime object representing the starting point.
        channel_url: The URL of the channel.

    Returns:
        A list of serialized message objects. Returns an empty list if there's an issue.
    """
    logger.info(f"Fetching messages from {channel_url} since {since_date.isoformat()}")
    try:
        all_messages = []
        offset_id = 0
        batch_count = 0
        
        while True:
            batch_count += 1
            logger.debug(f"Fetching batch #{batch_count} with offset_id={offset_id}")
            
            history = await client(GetHistoryRequest(
                peer=entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=messages_limit,
                max_id=0,
                min_id=0,
                hash=0
            ))
            
            if not history.messages:
                logger.debug(f"No messages returned in batch #{batch_count}")
                break
                
            messages = history.messages
            logger.debug(f"Received {len(messages)} messages in batch #{batch_count}")
            
            for message in messages:
                if message.date and message.date > since_date:
                    logger.debug(f"Message ID {message.id} from {message.date.isoformat()} is within date range")
                    all_messages.append(serialize_message(message, channel_url))
                elif message.date and message.date <= since_date:
                    logger.debug(f"Message ID {message.id} from {message.date.isoformat()} is outside date range. Stopping fetch.")
                    return all_messages
                    
            offset_id = messages[-1].id
            logger.debug(f"Setting new offset_id to {offset_id}")
            
            if len(messages) < messages_limit:
                logger.debug(f"Received fewer messages ({len(messages)}) than limit ({messages_limit}). Stopping fetch.")
                break
                
        logger.info(f"Fetched a total of {len(all_messages)} messages from {channel_url}")
        return all_messages

    except Exception as e:
        logger.error(f"An error occurred while fetching messages from {channel_url}: {e}")
        logger.error(traceback.format_exc())
        return []

async def get_channel_entity(client, channel_identifier):
    """Resolves a channel username or ID to its entity."""
    logger.info(f"Resolving channel entity for: {channel_identifier}")
    try:
        entity = await client.get_entity(channel_identifier)
        logger.debug(f"Entity resolved: {entity}")
        return entity
    except Exception as e:
        logger.error(f"Could not find channel '{channel_identifier}': {e}")
        logger.error(traceback.format_exc())
        return None

async def authorize_client():
    """
    Handles the authorization process for the Telegram client.
    Returns an authorized client or None if authorization fails.
    """
    logger.info("Starting Telegram client authorization")
    client = TelegramClient(session_file, api_id, api_hash)
    
    try:
        logger.debug("Connecting to Telegram")
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.info("User not authorized. Starting authorization process...")
            
            if not phone_number:
                phone = input("Please enter your phone number (with country code, e.g., +1234567890): ")
                
            else:
                phone = phone_number
                logger.info(f"Using phone number from environment: {phone}")
            
            logger.debug(f"Sending code request to phone: {phone}")
            await client.send_code_request(phone)
            code = input("Please enter the verification code you received: ")
            logger.debug("Verification code entered")
            
            try:
                # First try to sign in with just the code
                logger.debug("Attempting to sign in with verification code")
                await client.sign_in(phone, code)
                logger.info("Successfully authorized!")
            except telethon.errors.SessionPasswordNeededError:
                # 2FA is enabled, ask for the password
                logger.info("Two-factor authentication is enabled.")
                
                # Give the user multiple attempts for the 2FA password
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        password = input(f"Please enter your 2FA password (attempt {attempt+1}/{max_attempts}): ")
                        logger.debug(f"Attempting 2FA sign-in (attempt {attempt+1}/{max_attempts})")
                        await client.sign_in(password=password)
                        logger.info("Successfully authorized with 2FA!")
                        break
                    except Exception as e:
                        if attempt < max_attempts - 1:
                            logger.warning(f"Incorrect password. Error: {e}")
                        else:
                            logger.error(f"Failed to authenticate after {max_attempts} attempts: {e}")
                            return None
            except Exception as e:
                logger.error(f"Error during sign in: {e}")
                logger.error(traceback.format_exc())
                return None
        else:
            logger.info("Already authorized!")
        
        return client
    
    except Exception as e:
        logger.error(f"Error during authorization: {e}")
        logger.error(traceback.format_exc())
        return None

def get_summary_from_db(url):
    """
    Check if a URL's summary exists in the database and return it if found
    
    Args:
        url: The URL to look up
        
    Returns:
        The summary content or None if not found
    """
    logger.debug(f"Checking database for summary of URL: {url}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT summary_content FROM link_summaries WHERE url = ?", (url,))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Summary for {url} found in database")
            return result["summary_content"]
        
        logger.debug(f"No summary found in database for {url}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving summary from database: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            logger.debug("Closing database connection")
            conn.close()

async def fetch_telegram_messages(channels):
    """
    Fetches the latest Telegram messages from a list of channel links or handles.

    Args:
        channels: A list of Telegram channel links (e.g., "https://t.me/...") or handles (e.g., "cointelegraph").

    Returns:
        A dictionary where keys are the original channel identifiers and values are lists of
        serialized message objects, each including 'channel_url'.
        Example:
        {
            "https://t.me/channel1": [
                {
                    "internal_id": None,
                    "telegram_id": 123,
                    "channel_url": "https://t.me/channel1",
                    "date": "2024-01-01T00:00:00",
                    "text": "Message text",
                    "links": ["link1", "link2"],
                    "link_summaries": {
                        "link1": "Summary of link1 content",
                        "link2": "Summary of link2 content"
                    }
                },
                ...
            ],
            "https://t.me/channel2": [...],
            ...
        }
    """
    logger.info(f"Starting to fetch messages from {len(channels)} Telegram channels")
    logger.debug(f"Channels to fetch: {channels}")
    
    client = await authorize_client()
    if not client:
        logger.error("Failed to authorize client. Exiting.")
        return {}
        
    news_data = {}

    try:
        if not client.is_connected():
            logger.error("Telegram client failed to connect.")
            return {}

        now_utc = datetime.now(timezone.utc)
        one_day_ago_utc = now_utc - timedelta(hours=24)
        logger.info(f"Fetching messages since: {one_day_ago_utc.isoformat()}")

        for original_identifier in channels:
            channel_identifier = original_identifier
            if original_identifier.startswith("https://t.me/"):
                parts = original_identifier.split('/')
                if len(parts) > 3:
                    channel_identifier = parts[-1]
                elif len(parts) == 3 and parts[-1]:
                    channel_identifier = parts[-1]
            
            logger.info(f'Processing identifier: {original_identifier} (using handle: {channel_identifier})')
            entity = await get_channel_entity(client, channel_identifier)
            logger.debug(f'Entity for {channel_identifier}: {entity}')
            
            if entity:
                logger.info(f'Fetching messages from: {channel_identifier} ({original_identifier})')
                messages = await fetch_channel_messages_since(client, entity, one_day_ago_utc, original_identifier)
                
                # Extract summaries for each link in each message
                for message in messages:
                    logger.info(f"Processing message ID {message['telegram_id']} with {len(message['links'])} links")
                    
                    for link in message["links"]:
                        logger.info(f"Processing link: {link}")
                        try:
                            # First check if the summary is already in the database
                            cached_summary = get_summary_from_db(link)
                            if cached_summary:
                                logger.info(f"Using cached summary for {link}")
                                message["link_summaries"][link] = cached_summary
                                continue
                                
                            # If not in database, extract from the link
                            logger.info(f"Extracting summary for link: {link}")
                            summary = extract_summary(link)
                            logger.debug(f"Extraction result for {link}: {summary}")
                            
                            if "content" in summary:
                                logger.info(f"Successfully extracted content for {link}, length: {len(summary['content'])}")
                                message["link_summaries"][link] = summary["content"]
                                logger.debug(f"Full content for {link}: {summary['content']}")
                            else:
                                logger.warning(f"Failed to extract content for {link}")
                                message["link_summaries"][link] = "Failed to extract content"
                                if "error" in summary:
                                    logger.error(f"Error during extraction for {link}: {summary['error']}")
                        except Exception as e:
                            logger.error(f"Error extracting summary for {link}: {e}")
                            logger.error(traceback.format_exc())
                            message["link_summaries"][link] = f"Error: {str(e)}"
                
                news_data[original_identifier] = messages
                logger.info(f'Fetched {len(messages)} messages from {channel_identifier}')
            else:
                logger.warning(f"Could not resolve entity for {channel_identifier}, returning empty list")
                news_data[original_identifier] = []

        logger.info(f"Completed fetching messages from all {len(channels)} channels")
        return news_data

    except Exception as e:
        logger.error(f"Error fetching Telegram news: {e}")
        logger.error(traceback.format_exc())
        return {}
    finally:
        logger.debug("Disconnecting Telegram client")
        await client.disconnect()


async def main():
    """
    Example function to demonstrate how to use the fetch_telegram_messages function.
    """
    logger.info("Starting main function")
    
    # List of Telegram channels to fetch messages from
    channels = [
        # "https://t.me/cointelegraph",
        "https://t.me/CoinDeskGlobal"
        # "https://t.me/binanceupdates",
        # "cryptonews"  # Can also use just the handle
    ]
    
    logger.info(f"Channels to fetch: {channels}")
    
    # Fetch messages from the channels
    news_data = await fetch_telegram_messages(channels)
    
    # Print the results
    for channel, messages in news_data.items():
        logger.info(f"\nChannel: {channel}")
        logger.info(f"Number of messages: {len(messages)}")
        for i, message in enumerate(messages[:3]):  # Print first 3 messages as example
            logger.info(f"Message {i+1}:")
            logger.info(f"  Date: {message['date']}")
            logger.info(f"  Text: {message['text']}")  # Log full text without truncation
            logger.info(f"  Links: {message['links']}")
            logger.info(f"  Summaries:")
            for link, summary in message['link_summaries'].items():
                logger.info(f"    Link: {link}")
                logger.info(f"    Summary: {summary}")  # Log full summary without truncation


if __name__ == "__main__":
    # Run the async main function
    logger.info("Starting data_fetcher.py")
    asyncio.run(main())
    logger.info("data_fetcher.py execution completed")

