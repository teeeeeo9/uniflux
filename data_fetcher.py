import traceback
import asyncio
import os
import sqlite3
import logging
import sys
import json
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
import telethon.errors
from parser import extract_summary  # Import only the extraction function, get_summary_from_db is used internally

# Configure logging with full detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
    handlers=[
        logging.FileHandler("log.log"),
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
messages_limit = 10  # Number of messages to fetch per request
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
    
    # Extract channel ID from URL
    channel_id = channel_url.split('/')[-1] if channel_url.startswith('https://t.me/') else channel_url
    
    message_data = {
        "internal_id": None,  # Will be populated later if stored in DB
        "source_url": channel_url,
        "source_type": "telegram",
        "channel_id": channel_id,
        "message_id": str(message.id),
        "date": message.date.isoformat() if message.date else None,
        "data": message.message,
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
                hash=0,
                # limit=2
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

def message_exists_in_db(source_type, channel_id, message_id):
    """
    Check if a message already exists in the database.
    
    Args:
        source_type: The type of source (e.g., 'telegram')
        channel_id: The channel identifier
        message_id: The message identifier
        
    Returns:
        Tuple of (exists, id) where exists is a boolean and id is the message ID if it exists, None otherwise
    """
    logger.debug(f"Checking if message exists: {source_type}, {channel_id}, {message_id}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM messages WHERE source_type = ? AND channel_id = ? AND message_id = ?",
                (source_type, channel_id, message_id)
            )
            result = cursor.fetchone()
            exists = result is not None
            msg_id = result['id'] if exists else None
            logger.debug(f"Message exists: {exists}, ID: {msg_id}")
            return exists, msg_id
    except Exception as e:
        logger.error(f"Error checking if message exists: {e}")
        logger.error(traceback.format_exc())
        return False, None

def save_message_to_db(message_data):
    """
    Save a message to the database.
    
    Args:
        message_data: A dictionary containing message data with keys:
            - source_url: URL of the source
            - source_type: Type of source (e.g., 'telegram')
            - channel_id: Channel identifier
            - message_id: Message identifier
            - date: Date of the message as ISO string
            - data: Text content of the message
            - summarized_links_content: JSON string of links and summaries
            
    Returns:
        The ID of the inserted message
    """
    logger.debug(f"Saving message to database: {message_data['source_type']}, {message_data['channel_id']}, {message_data['message_id']}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages 
                (source_url, source_type, channel_id, message_id, date, data, summarized_links_content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_data['source_url'],
                    message_data['source_type'],
                    message_data['channel_id'],
                    message_data['message_id'],
                    message_data['date'],
                    message_data['data'],
                    message_data['summarized_links_content']
                )
            )
            conn.commit()
            msg_id = cursor.lastrowid
            logger.info(f"Message saved to database with ID: {msg_id}")
            return msg_id
    except Exception as e:
        logger.error(f"Error saving message to database: {e}")
        logger.error(traceback.format_exc())
        return None

async def fetch_telegram_messages(channels, time_range="1d", enable_retries=False, debug_mode=False):
    """
    Fetches the latest Telegram messages from a list of channel links or handles.

    Args:
        channels: A list of Telegram channel links (e.g., "https://t.me/...") or handles (e.g., "cointelegraph").
        time_range: Time range to fetch messages for. Either "1d" (1 day) or "1w" (1 week).
        enable_retries: Whether to enable retry logic for extraction (up to 5 attempts).
        debug_mode: Whether to enable LiteLLM debug mode.

    Returns:
        A dictionary where keys are the original channel identifiers and values are lists of
        message IDs in the database.
        Example:
        {
            "https://t.me/channel1": [1, 2, 3],
            "https://t.me/channel2": [4, 5],
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
        
        # Calculate time range based on parameter
        if time_range == "1w":
            since_date_utc = now_utc - timedelta(days=7)
            logger.info(f"Fetching messages for the past week since: {since_date_utc.isoformat()}")
        else:  # Default to "1d"
            since_date_utc = now_utc - timedelta(hours=24)
            logger.info(f"Fetching messages for the past day since: {since_date_utc.isoformat()}")

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
                # messages = await fetch_channel_messages_since(client, entity, one_day_ago_utc, original_identifier)
                messages = await fetch_channel_messages_since(client, entity, since_date_utc, original_identifier)
                
                message_ids = []
                
                # Extract summaries for each link in each message
                for message in messages:
                    logger.info(f"Processing message ID {message['message_id']} with {len(message['links'])} links")
                    
                    # Check if message already exists in database
                    exists, msg_id = message_exists_in_db("telegram", message['channel_id'], message['message_id'])
                    
                    if exists:
                        logger.info(f"Message already exists in database with ID: {msg_id}")
                        message_ids.append(msg_id)
                        continue
                    
                    for link in message["links"]:
                        logger.info(f"Processing link: {link}")
                        try:
                            # Use the async extract_summary function with await
                            logger.info(f"Extracting summary for link: {link}")
                            summary_result = await extract_summary(link, enable_retries=enable_retries, debug_mode=debug_mode)
                            logger.debug(f"Extraction result for {link}: {summary_result}")
                            
                            if summary_result["success"] == 1 and summary_result["content"]:
                                logger.info(f"Successfully extracted content for {link}, length: {len(summary_result['content'])}")
                                message["link_summaries"][link] = summary_result["content"]
                                logger.debug(f"Full content for {link}: {summary_result['content']}")
                            else:
                                logger.warning(f"Failed to extract content for {link}")
                                message["link_summaries"][link] = "Failed to extract content"
                        except Exception as e:
                            logger.error(f"Error extracting summary for {link}: {e}")
                            logger.error(traceback.format_exc())
                            message["link_summaries"][link] = f"Error: {str(e)}"
                    
                    # Prepare message data for saving
                    message_data = {
                        'source_url': message['source_url'],
                        'source_type': message['source_type'],
                        'channel_id': message['channel_id'],
                        'message_id': message['message_id'],
                        'date': message['date'],
                        'data': message['data'],
                        'summarized_links_content': json.dumps(message['link_summaries'])
                    }
                    
                    # Save message to database
                    msg_id = save_message_to_db(message_data)
                    if msg_id:
                        message_ids.append(msg_id)
                
                news_data[original_identifier] = message_ids
                logger.info(f'Saved {len(message_ids)} messages from {channel_identifier} to database')
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
    
    # Time range: "1d" for 1 day or "1w" for 1 week
    time_range = "1w"
    
    # Fetch messages from the channels, optionally enabling retries or debug mode
    news_data = await fetch_telegram_messages(channels, time_range=time_range, enable_retries=False, debug_mode=False)
    
    # Print the results
    for channel, message_ids in news_data.items():
        logger.info(f"\nChannel: {channel}")
        logger.info(f"Number of messages saved to database: {len(message_ids)}")
        logger.info(f"Message IDs: {message_ids}")


if __name__ == "__main__":
    # Run the async main function
    logger.info("Starting data_fetcher.py")
    asyncio.run(main())
    logger.info("data_fetcher.py execution completed")

