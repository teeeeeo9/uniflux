import traceback
import asyncio
import os
import sqlite3
import logging
import sys
import json
from datetime import datetime, timezone, timedelta
import feedparser  # For parsing RSS feeds
import time
import hashlib  # For generating unique IDs for RSS entries
import requests
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
import telethon.errors
from parser import extract_summary  # Import only the extraction function, get_summary_from_db is used internally
from config import DATABASE, LOG_FILE, TELEGRAM_SESSION
from google import genai
from instruction_templates import INSTRUCTIONS


# Configure module-specific logger
logger = logging.getLogger('data_fetcher')
logger.setLevel(logging.DEBUG)  # Set module level to DEBUG

# Check if the logger already has handlers to avoid duplicate handlers
if not logger.handlers:
    # Create file handler that logs to the same file
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(funcName)s() - %(message)s'))
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(funcName)s() - %(message)s'))
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Now the logger is configured specifically for this module with DEBUG level
logger.info("Data fetcher module initializing")

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded from .env file")

# Telegram API credentials from environment variables
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone_number = os.getenv("TELEGRAM_PHONE_NUMBER")
logger.info(f"Telegram credentials loaded: API ID: {api_id}, Phone: {phone_number}")

# Configure Gemini API
try:
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        logger.warning("GEMINI_API_KEY not found in environment variables.")
        gemini_client = None
    else:
        # Use the Client API for asynchronous calls
        gemini_client = genai.Client(api_key=gemini_api_key)
        GEMINI_MODEL_CLEANER = os.getenv('GEMINI_MODEL_CLEANER', 'gemini-1.5-flash') # Use flash for simple tasks
        logger.info(f"Gemini API configured for cleaning using model: {GEMINI_MODEL_CLEANER}")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    gemini_client = None

# Configuration
messages_limit = 100  # Number of messages to fetch per request
session_file = TELEGRAM_SESSION
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

def identify_repetitive_links(messages, threshold=0.7):
    """
    Identifies links that appear repetitively across messages from the same channel.
    
    Args:
        messages: List of serialized message objects with 'links' field
        threshold: The proportion of messages a link must appear in to be considered repetitive
                   (e.g., 0.7 means the link appears in 70% of messages)
    
    Returns:
        A set of repetitive links
    """
    logger.debug(f"Identifying repetitive links across {len(messages)} messages")
    
    if not messages or len(messages) < 2:
        logger.debug("Not enough messages to identify repetitive links")
        return set()
    
    # Count occurrences of each link
    link_counts = {}
    for message in messages:
        if 'links' in message and message['links']:
            for link in message['links']:
                link_counts[link] = link_counts.get(link, 0) + 1
    
    # Calculate the minimum number of occurrences needed to be considered repetitive
    min_occurrences = max(2, int(len(messages) * threshold))
    logger.debug(f"Minimum occurrences to be considered repetitive: {min_occurrences}")
    
    # Identify repetitive links
    repetitive_links = {link for link, count in link_counts.items() if count >= min_occurrences}
    logger.info(f"Identified {len(repetitive_links)} repetitive links: {repetitive_links}")
    
    return repetitive_links

def filter_repetitive_links(message, repetitive_links):
    """
    Filters out repetitive links from a message.
    
    Args:
        message: Serialized message object with 'links' field
        repetitive_links: Set of links identified as repetitive
    
    Returns:
        Updated message with repetitive links filtered out
    """
    if not repetitive_links or 'links' not in message or not message['links']:
        return message
    
    original_links = message['links']
    filtered_links = [link for link in original_links if link not in repetitive_links]
    
    if len(original_links) != len(filtered_links):
        logger.debug(f"Filtered out {len(original_links) - len(filtered_links)} repetitive links from message {message.get('message_id', 'unknown')}")
        message['links'] = filtered_links
    
    return message

async def fetch_channel_messages_since(client, entity, since_date, channel_url, min_id=0):
    """Fetches messages from a Telegram channel since a given date.

    Args:
        client: The Telethon client.
        entity: The Telegram channel entity.
        since_date: The datetime object representing the starting point.
        channel_url: The URL of the channel.
        min_id: The minimum message ID to fetch (exclusive). Messages with IDs <= min_id will be skipped.
               This is used to avoid fetching messages we already have.

    Returns:
        A list of serialized message objects. Returns an empty list if there's an issue.
    """
    logger.info(f"Fetching messages from {channel_url} since {since_date.isoformat()}")
    if min_id:
        logger.info(f"Starting from message ID > {min_id}")
    
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
                min_id=int(min_id) if min_id else 0,  # Only fetch messages with ID > min_id
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

def get_latest_message_id_for_channel(source_type, channel_id):
    """
    Get the latest (highest) message ID for a given channel from the database.
    
    Args:
        source_type: The type of source (e.g., 'telegram')
        channel_id: The channel identifier
        
    Returns:
        The latest message ID as a string or None if no messages are found
    """
    logger.debug(f"Getting latest message ID for channel: {source_type}, {channel_id}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Use CAST to ensure numeric comparison of message_id
            cursor.execute(
                "SELECT message_id FROM messages WHERE source_type = ? AND channel_id = ? ORDER BY CAST(message_id AS INTEGER) DESC LIMIT 1",
                (source_type, channel_id)
            )
            result = cursor.fetchone()
            if result:
                message_id = result['message_id']
                logger.info(f"Latest message ID for {channel_id}: {message_id}")
                return message_id
            else:
                logger.info(f"No previous messages found for {channel_id}")
                return None
    except Exception as e:
        logger.error(f"Error getting latest message ID: {e}")
        logger.error(traceback.format_exc())
        return None

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
        time_range: Time range to fetch messages for. Either "1d" (1 day), "2d" (2 days) or "1w" (1 week).
        enable_retries: Whether to enable retry logic for extraction (up to 5 attempts).
        debug_mode: Whether to enable LiteLLM debug mode.

    Returns:
        A dictionary where keys are the original channel identifiers and values are lists of
        message IDs in the database.
    """
    logger.info(f"Starting to fetch messages from {len(channels)} Telegram channels")
    logger.debug(f"Channels to fetch: {channels}")
    
    client = await authorize_client()
    if not client:
        logger.error("Failed to authorize client. Exiting.")
        return {}
        
    news_data = {}
    total_channels = len(channels)
    current_channel = 0

    try:
        if not client.is_connected():
            logger.error("Telegram client failed to connect.")
            return {}

        now_utc = datetime.now(timezone.utc)
        
        # Calculate time range based on parameter
        if time_range == "1w":
            since_date_utc = now_utc - timedelta(days=7)
            logger.info(f"Fetching messages for the past week since: {since_date_utc.isoformat()}")
        elif time_range == "2d":
            since_date_utc = now_utc - timedelta(days=2)
            logger.info(f"Fetching messages for the past 2 days since: {since_date_utc.isoformat()}")
        else:  # Default to "1d"
            since_date_utc = now_utc - timedelta(hours=24)
            logger.info(f"Fetching messages for the past day since: {since_date_utc.isoformat()}")

        for original_identifier in channels:
            current_channel += 1
            logger.info(f"[Progress: {current_channel}/{total_channels} channels] Processing {original_identifier}")
            
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
                # Get the latest message ID from the database for this channel
                latest_message_id = get_latest_message_id_for_channel("telegram", channel_identifier)
                
                logger.info(f'Fetching messages from: {channel_identifier} ({original_identifier})')
                
                if latest_message_id:
                    logger.info(f'Found previous messages for this channel. Latest message ID: {latest_message_id}')
                    # Fetch messages with ID > latest_message_id
                    messages = await fetch_channel_messages_since(
                        client, entity, since_date_utc, original_identifier, min_id=latest_message_id
                    )
                else:
                    logger.info(f'No previous messages found for this channel. Fetching from scratch.')
                    # Fetch all messages in the time range
                    messages = await fetch_channel_messages_since(client, entity, since_date_utc, original_identifier)
                
                message_ids = []
                total_messages = len(messages)
                current_message = 0
                
                # Identify repetitive links across all fetched messages
                repetitive_links = identify_repetitive_links(messages)
                
                # Extract summaries for each link in each message
                for message in messages:
                    current_message += 1
                    logger.info(f"[Progress: {current_channel}/{total_channels} channels, {current_message}/{total_messages} messages] Processing message ID {message['message_id']} with {len(message['links'])} links")
                    
                    # Check if message already exists in database
                    exists, msg_id = message_exists_in_db("telegram", message['channel_id'], message['message_id'])
                    
                    if exists:
                        logger.info(f"Message already exists in database with ID: {msg_id}")
                        message_ids.append(msg_id)
                        continue
                    
                    # Filter out repetitive links before processing
                    message = filter_repetitive_links(message, repetitive_links)
                    logger.info(f"After filtering repetitive links: {len(message['links'])} links remain")
                    
                    for link in message["links"]:
                        logger.info(f"Processing link: {link}")
                        try:
                            # Use the async extract_summary function with await
                            logger.info(f"Extracting summary for link: {link}")
                            
                            # Implement progressive retries
                            max_extraction_attempts = 3
                            for attempt in range(max_extraction_attempts):
                                summary_result = await extract_summary(link, enable_retries=(attempt > 0), debug_mode=debug_mode)
                                logger.debug(f"Extraction result for {link}: {summary_result}")
                                
                                if summary_result["success"] == 1 and summary_result["content"]:
                                    logger.info(f"Successfully extracted content for {link}, length: {len(summary_result['content'])}")
                                    message["link_summaries"][link] = summary_result["content"]
                                    logger.debug(f"Full content for {link}: {summary_result['content']}")
                                    break
                                elif "error" in summary_result and "Gemini API error: " in summary_result.get("error", ""):
                                    error_msg = summary_result.get("error", "")
                                    
                                    # Handle rate limit errors (code 429)
                                    if "RESOURCE_EXHAUSTED" in error_msg and "code\": 429" in error_msg and attempt < max_extraction_attempts - 1:
                                        # Try to extract the recommended retry delay
                                        retry_delay_match = None
                                        try:
                                            if "retryDelay" in error_msg:
                                                import re
                                                retry_delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_msg)
                                        except Exception:
                                            logger.warning("Failed to parse retry delay from error response")
                                        
                                        # Use the recommended delay if available, otherwise use our default
                                        if retry_delay_match:
                                            wait_time = int(retry_delay_match.group(1))
                                            logger.warning(f"Gemini API rate limit error encountered. Using recommended retry delay of {wait_time}s. Retry {attempt+1}/{max_extraction_attempts}")
                                        else:
                                            wait_time = 5 * (attempt + 1)  # Progressive backoff
                                            logger.warning(f"Gemini API rate limit error encountered. Using default retry delay of {wait_time}s. Retry {attempt+1}/{max_extraction_attempts}")
                                        
                                        logger.warning(f"Waiting {wait_time}s before retry {attempt+1}/{max_extraction_attempts}")
                                        time.sleep(wait_time)
                                    # Handle operation cancelled errors (code 499)
                                    elif "code\": 499" in error_msg and "The operation was cancelled" in error_msg and attempt < max_extraction_attempts - 1:
                                        wait_time = 5 * (attempt + 1)  # Progressive backoff
                                        logger.warning(f"Gemini API error 499 encountered, waiting {wait_time}s before retry {attempt+1}/{max_extraction_attempts}")
                                        time.sleep(wait_time)
                                    else:
                                        # Either different error or exceeded retries
                                        logger.error(f"Failed to extract content after {attempt+1} attempts due to Gemini API error: {error_msg}")
                                        message["link_summaries"][link] = f"Failed to extract content: {error_msg}"
                                else:
                                    # Other failure
                                    logger.warning(f"Failed to extract content for {link}")
                                    message["link_summaries"][link] = "Failed to extract content"
                                    break
                                
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

def get_messages_from_db(source_type, source_link, period="1d"):
    """
    Retrieves messages from the database based on source type, source link, and time period.
    
    Args:
        source_type: The type of source (e.g., 'telegram', 'rss')
        source_link: The source URL or identifier (e.g., 'https://t.me/channel')
        period: Time period to retrieve messages for. Either "1d" (1 day), "2d" (2 days) or "1w" (1 week).
        
    Returns:
        A list of dictionaries containing complete message details.
    """
    logger.info(f"Retrieving {period} messages for {source_type} source: {source_link}")
    
    # Extract channel_id from source_link depending on source type
    channel_id = source_link
    if source_type == 'telegram' and source_link.startswith("https://t.me/"):
        parts = source_link.split('/')
        if len(parts) > 3:
            channel_id = parts[-1]
        elif len(parts) == 3 and parts[-1]:
            channel_id = parts[-1]
    elif source_type == 'rss':
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(source_link)
            channel_id = parsed_url.netloc
        except Exception as e:
            logger.warning(f"Could not parse RSS URL into channel ID, using full URL: {e}")
            channel_id = source_link
    
    logger.debug(f"Using channel_id: {channel_id}")
    
    # Calculate time range based on parameter
    now_utc = datetime.now(timezone.utc)
    if period == "1w":
        since_date_utc = now_utc - timedelta(days=7)
        logger.info(f"Fetching messages for the past week since: {since_date_utc.isoformat()}")
    elif period == "2d":
        since_date_utc = now_utc - timedelta(days=2)
        logger.info(f"Fetching messages for the past 2 days since: {since_date_utc.isoformat()}")
    else:  # Default to "1d"
        since_date_utc = now_utc - timedelta(hours=24)
        logger.info(f"Fetching messages for the past day since: {since_date_utc.isoformat()}")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, source_url, source_type, channel_id, message_id, date, data, summarized_links_content
                FROM messages
                WHERE source_type = ? AND channel_id = ? AND date >= ?
                ORDER BY date DESC
                """,
                (source_type, channel_id, since_date_utc.isoformat())
            )
            
            results = cursor.fetchall()
            logger.info(f"Retrieved {len(results)} messages from database")
            
            messages = []
            for row in results:
                message = dict(row)
                
                # Parse JSON string back to dictionary
                if message['summarized_links_content']:
                    try:
                        message['link_summaries'] = json.loads(message['summarized_links_content'])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse summarized_links_content for message {message['id']}")
                        message['link_summaries'] = {}
                else:
                    message['link_summaries'] = {}
                    
                messages.append(message)
                
            return messages
            
    except Exception as e:
        logger.error(f"Error retrieving messages from database: {e}")
        logger.error(traceback.format_exc())
        return []

async def clean_rss_summary(raw_summary: str) -> str:
    """
    Cleans HTML/XML tags from a raw summary string using Gemini.
    Falls back to basic regex cleaning if the Gemini API fails.

    Args:
        raw_summary: The raw summary text potentially containing HTML/XML.

    Returns:
        The cleaned plain text summary, or the original summary if cleaning fails.
    """
    if not raw_summary:
        logger.debug("Skipping summary cleaning (empty summary).")
        return ""
    
    # Print first 100 chars of the raw summary for debugging
    logger.debug(f"Raw summary starts with: {raw_summary[:100]}")
    
    # More thorough detection of HTML content
    has_html = False
    html_indicators = ['<div', '<p>', '<br', '<span', '<a href', '&lt;', '&gt;', '&amp;', '&quot;', '&#']
    for indicator in html_indicators:
        if indicator in raw_summary:
            has_html = True
            logger.debug(f"HTML/XML detected: found '{indicator}' in content")
            break
    
    # If no HTML detected, return as is
    if not has_html and '<' not in raw_summary and '>' not in raw_summary:
        logger.debug("No HTML/XML content detected, returning original.")
        return raw_summary
    
    # Try cleaning with Gemini if available
    if gemini_client:
        logger.info("Attempting to clean HTML content using Gemini.")
        
        # Use the template from instruction_templates.py
        prompt = INSTRUCTIONS["clean_html"].format(raw_text=raw_summary)
        
        try:
            # Use the async generate_content method
            response = await gemini_client.aio.models.generate_content(
                model=GEMINI_MODEL_CLEANER,
                contents=prompt
            )
            
            cleaned_text = response.text.strip()
            
            # Log both the original and cleaned text for debugging
            logger.debug(f"ORIGINAL (first 100 chars): {raw_summary[:100]}")
            logger.debug(f"CLEANED (first 100 chars): {cleaned_text[:100]}")
            
            # Verify the cleaning worked by checking if HTML indicators are gone
            html_remains = False
            for indicator in html_indicators:
                if indicator in cleaned_text:
                    html_remains = True
                    logger.warning(f"HTML/XML remains in cleaned content: found '{indicator}'")
                    break
            
            if cleaned_text and not html_remains:
                logger.info(f"Successfully cleaned summary using Gemini. Original length: {len(raw_summary)}, Cleaned length: {len(cleaned_text)}")
                return cleaned_text
            else:
                logger.warning("Gemini cleaning did not remove all HTML or returned empty string. Returning the original.")
                
        except Exception as e:
            logger.error(f"Error cleaning summary with Gemini: {e}")
            logger.error(traceback.format_exc())
            logger.warning("Falling back to regex-based cleaning.")
    else:
        logger.warning("Gemini client not configured.")
    
    return raw_summary

async def fetch_rss_feed(feed_url, time_range="1d", enable_retries=False, debug_mode=False):
    """
    Fetches and parses an RSS feed from the given URL.

    Args:
        feed_url: URL of the RSS feed
        time_range: Time range to fetch entries for. Either "1d" (1 day), "2d" (2 days) or "1w" (1 week).
        enable_retries: Whether to enable retry logic for extraction (up to 5 attempts).
        debug_mode: Whether to enable LiteLLM debug mode.

    Returns:
        A list of saved message IDs in the database.
    """
    logger.info(f"Fetching RSS feed from URL: {feed_url}")
    
    # Calculate time range based on parameter
    now_utc = datetime.now(timezone.utc)
    if time_range == "1w":
        since_date_utc = now_utc - timedelta(days=7)
        logger.info(f"Fetching RSS entries for the past week since: {since_date_utc.isoformat()}")
    elif time_range == "2d":
        since_date_utc = now_utc - timedelta(days=2)
        logger.info(f"Fetching RSS entries for the past 2 days since: {since_date_utc.isoformat()}")
    else:  # Default to "1d"
        since_date_utc = now_utc - timedelta(hours=24)
        logger.info(f"Fetching RSS entries for the past day since: {since_date_utc.isoformat()}")
    
    try:
        # Parse the RSS feed
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            logger.error(f"Error parsing RSS feed {feed_url}: {feed.bozo_exception}")
            return []
        
        logger.info(f"Successfully parsed RSS feed: {feed.feed.get('title', 'Untitled Feed')}")
        logger.info(f"Total entries: {len(feed.entries)}")

        # Extract channel ID from feed URL
        # Use the domain name as channel ID
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(feed_url)
            channel_id = parsed_url.netloc
            logger.info(f"Using {channel_id} as channel ID for RSS feed")
        except Exception as e:
            logger.warning(f"Could not parse URL into channel ID, using full URL: {e}")
            channel_id = feed_url
        
        message_ids = []
        
        # Identify repetitive links across all entries by first collecting them
        all_entries = []
        for entry in feed.entries:
            # Get entry date
            entry_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                entry_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                entry_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
            else:
                # Use current time if no date is available
                entry_date = now_utc
                logger.warning(f"No date found for entry {entry.get('title', 'Untitled')}. Using current time.")
            
            # Skip entries older than the time range
            if entry_date < since_date_utc:
                continue
            
            # Create a serialized entry with links
            links = [entry.get('link')] if 'link' in entry else []
            serialized_entry = {
                'id': entry.get('id', ''),
                'title': entry.get('title', ''),
                'links': links
            }
            all_entries.append(serialized_entry)
        
        # Identify repetitive links
        repetitive_links = identify_repetitive_links(all_entries)
        logger.info(f"Identified {len(repetitive_links)} repetitive links in RSS feed")
        
        # Process each entry
        total_entries = len(feed.entries)
        current_entry = 0
        
        for entry in feed.entries:
            current_entry += 1
            logger.info(f"[Progress: {current_entry}/{total_entries} entries] Processing entry: {entry.get('title', 'Untitled')}")
            
            # Get entry date
            entry_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                entry_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                entry_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
            else:
                # Use current time if no date is available
                entry_date = now_utc
                logger.warning(f"No date found for entry {entry.get('title', 'Untitled')}. Using current time.")
            
            # Skip entries older than the time range
            if entry_date < since_date_utc:
                logger.info(f"Skipping entry from {entry_date.isoformat()} as it's outside the time range")
                continue
            
            # Extract links from entry (must be done for each entry being processed)
            links = [entry.get('link')] if 'link' in entry else []
            
            # Filter out repetitive links
            original_links = links.copy()
            links = [link for link in links if link not in repetitive_links]
            if len(original_links) != len(links):
                logger.debug(f"Filtered out {len(original_links) - len(links)} repetitive links from entry {entry.get('title', 'Untitled')}")
            logger.info(f"After filtering repetitive links: {len(links)} links remain")
            
            # Generate a unique message ID for the RSS entry using hash of title and link
            entry_id_str = f"{entry.get('title', '')}-{entry.get('link', '')}"
            message_id = hashlib.md5(entry_id_str.encode()).hexdigest()
            
            # Check if entry already exists in database
            exists, msg_id = message_exists_in_db("rss", channel_id, message_id)
            if exists:
                logger.info(f"Entry already exists in database with ID: {msg_id}")
                message_ids.append(msg_id)
                continue

            # Clean the summary using Gemini
            raw_summary = entry.get('summary', '')
            cleaned_summary = await clean_rss_summary(raw_summary)
            
            # Prepare entry data
            entry_data = {
                'source_url': feed_url,
                'source_type': 'rss',
                'channel_id': channel_id,
                'message_id': message_id,
                'date': entry_date.isoformat(),
                # Use cleaned summary here
                'data': f"{entry.get('title', 'Untitled')}\n\n{cleaned_summary}\n\nLink: {entry.get('link', '')}", 
                'summarized_links_content': '{}'  # Empty JSON object
            }
            
            # Extract links from entry
            link_summaries = {}
            
            # Fetch summaries for each link
            total_links = len(links)
            current_link = 0
            
            for link in links:
                current_link += 1
                logger.info(f"[Progress: {current_entry}/{total_entries} entries, {current_link}/{total_links} links] Processing link: {link}")
                try:
                    logger.info(f"Extracting summary for link: {link}")
                    
                    # Implement progressive retries
                    max_extraction_attempts = 3
                    for attempt in range(max_extraction_attempts):
                        summary_result = await extract_summary(link, enable_retries=(attempt > 0), debug_mode=debug_mode)
                        logger.debug(f"Extraction result for {link}: {summary_result}")
                        
                        if summary_result["success"] == 1 and summary_result["content"]:
                            logger.info(f"Successfully extracted content for {link}, length: {len(summary_result['content'])}")
                            link_summaries[link] = summary_result["content"]
                            logger.debug(f"Full content for {link}: {summary_result['content']}")
                            break
                        elif "error" in summary_result and "Gemini API error: " in summary_result.get("error", ""):
                            error_msg = summary_result.get("error", "")
                            
                            # Handle rate limit errors (code 429)
                            if "RESOURCE_EXHAUSTED" in error_msg and "code\": 429" in error_msg and attempt < max_extraction_attempts - 1:
                                # Try to extract the recommended retry delay
                                retry_delay_match = None
                                try:
                                    if "retryDelay" in error_msg:
                                        import re
                                        retry_delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_msg)
                                except Exception:
                                    logger.warning("Failed to parse retry delay from error response")
                                
                                # Use the recommended delay if available, otherwise use our default
                                if retry_delay_match:
                                    wait_time = int(retry_delay_match.group(1))
                                    logger.warning(f"Gemini API rate limit error encountered. Using recommended retry delay of {wait_time}s. Retry {attempt+1}/{max_extraction_attempts}")
                                else:
                                    wait_time = 5 * (attempt + 1)  # Progressive backoff
                                    logger.warning(f"Gemini API rate limit error encountered. Using default retry delay of {wait_time}s. Retry {attempt+1}/{max_extraction_attempts}")
                                
                                logger.warning(f"Waiting {wait_time}s before retry {attempt+1}/{max_extraction_attempts}")
                                time.sleep(wait_time)
                            # Handle operation cancelled errors (code 499)
                            elif "code\": 499" in error_msg and "The operation was cancelled" in error_msg and attempt < max_extraction_attempts - 1:
                                wait_time = 5 * (attempt + 1)  # Progressive backoff
                                logger.warning(f"Gemini API error 499 encountered, waiting {wait_time}s before retry {attempt+1}/{max_extraction_attempts}")
                                time.sleep(wait_time)
                            else:
                                # Either different error or exceeded retries
                                logger.error(f"Failed to extract content after {attempt+1} attempts due to Gemini API error: {error_msg}")
                                link_summaries[link] = f"Failed to extract content: {error_msg}"
                        else:
                            # Other failure
                            logger.warning(f"Failed to extract content for {link}")
                            link_summaries[link] = "Failed to extract content"
                            break
                        
                except Exception as e:
                    logger.error(f"Error extracting summary for {link}: {e}")
                    logger.error(traceback.format_exc())
                    link_summaries[link] = f"Error: {str(e)}"
            
            # Update entry data with link summaries
            entry_data['summarized_links_content'] = json.dumps(link_summaries)
            
            # Save entry to database
            msg_id = save_message_to_db(entry_data)
            if msg_id:
                message_ids.append(msg_id)
        
        logger.info(f"Saved {len(message_ids)} entries from RSS feed {feed_url} to database")
        return message_ids
    
    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_url}: {e}")
        logger.error(traceback.format_exc())
        return []

async def fetch_rss_feeds(feed_urls, time_range="1d", enable_retries=False, debug_mode=False):
    """
    Fetches multiple RSS feeds and processes their entries.

    Args:
        feed_urls: A list of RSS feed URLs
        time_range: Time range to fetch entries for. Either "1d" (1 day), "2d" (2 days) or "1w" (1 week).
        enable_retries: Whether to enable retry logic for extraction (up to 5 attempts).
        debug_mode: Whether to enable LiteLLM debug mode.
    
    Returns:
        A dictionary where keys are feed URLs and values are lists of saved message IDs.
    """
    logger.info(f"Fetching {len(feed_urls)} RSS feeds")
    
    feeds_data = {}
    
    for feed_url in feed_urls:
        message_ids = await fetch_rss_feed(feed_url, time_range, enable_retries, debug_mode)
        feeds_data[feed_url] = message_ids
    
    logger.info(f"Completed fetching all RSS feeds")
    return feeds_data

async def main():
    """
    Example function to demonstrate how to use the fetch_telegram_messages function.
    """
    logger.info("Starting main function")
    
    # Get list of sources from database
    telegram_channels = []
    rss_feeds = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT url, source_type 
                FROM sources 
                """
            )
            for row in cursor.fetchall():
                if row['source_type'] == 'rss':
                    rss_feeds.append(row['url'])
                else:  # Default to telegram
                    telegram_channels.append(row['url'])
                    
        if not telegram_channels and not rss_feeds:
            logger.error("No active sources found in database")
    except Exception as e:
        logger.error(f"Error retrieving sources from database: {e}")
        logger.error(traceback.format_exc())
    
    logger.info(f"Telegram channels to fetch: {telegram_channels}")
    logger.info(f"RSS feeds to fetch: {rss_feeds}")
    
    # Time range: "1d" for 1 day or "1w" for 1 week
    time_range = "1d"
    
    # Fetch messages from Telegram channels
    if telegram_channels:
        telegram_data = await fetch_telegram_messages(telegram_channels, time_range=time_range, enable_retries=False, debug_mode=False)
        
        # Print the results
        for channel, message_ids in telegram_data.items():
            logger.info(f"\nTelegram channel: {channel}")
            logger.info(f"Number of messages saved to database: {len(message_ids)}")
            logger.info(f"Message IDs: {message_ids}")
    
    # Fetch RSS feeds
    if rss_feeds:
        rss_data = await fetch_rss_feeds(rss_feeds, time_range=time_range, enable_retries=False, debug_mode=False)
        
        # Print the results
        for feed, message_ids in rss_data.items():
            logger.info(f"\nRSS feed: {feed}")
            logger.info(f"Number of entries saved to database: {len(message_ids)}")
            logger.info(f"Message IDs: {message_ids}")

if __name__ == "__main__":
    # Run the async main function
    logger.info("Starting data_fetcher.py")
    asyncio.run(main())
    logger.info("data_fetcher.py execution completed")

