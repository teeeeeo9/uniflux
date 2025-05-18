    # app.py
from flask import Flask, request, jsonify, stream_with_context, Response
from flask_cors import CORS
import sqlite3
import asyncio
from telethon import TelegramClient, utils
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.errors import SessionPasswordNeededError
import traceback
import os
import logging
import pprint
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import json
import re  # Import the regular expression module
from config import DATABASE, LOG_FILE
from data_summarizer import process_and_aggregate_news, generate_insights, main as summarizer_main
import threading
from functools import wraps
import time
# Import the Telegram bot functions
from telegram_bot import (
    notify_new_subscriber, 
    notify_new_feedback, 
    notify_summaries_request, 
    notify_insights_request,
    init_bot,
    sync_notify_new_subscriber,
    sync_notify_new_feedback,
    sync_notify_summaries_request,
    sync_notify_insights_request
)



load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Initialize the Telegram bot
if os.getenv("ENABLE_TELEGRAM_BOT", "false").lower() in ["true", "1", "yes"]:
    try:
        logger.info("Initializing Telegram notification bot...")
        bot_loop = init_bot()
        logger.info("Telegram notification bot initialized and running in background thread")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        logger.error(traceback.format_exc())
        bot_loop = None
else:
    logger.info("Telegram bot initialization skipped (ENABLE_TELEGRAM_BOT is not enabled)")
    bot_loop = None

# Telegram API credentials (move to environment variables for security)
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone_number = os.getenv("TELEGRAM_PHONE_NUMBER")
gemini_api_key = os.getenv("GEMINI_API_KEY")  # Add Gemini API key

messages_limit = 100
CHUNK_SIZE = 20000
LAST_MESSAGE_IDS_FILE = "last_message_ids.json"  # File to store last message IDs
SOURCES_FILE = "sources.json"  # File to store news sources

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Global dictionary to store progress data for different requests
channel_progress_data = {}

def ensure_event_loop():
    """
    Ensures a valid event loop is available for the current thread.
    Creates a new one if needed.
    
    Returns:
        asyncio.AbstractEventLoop: The event loop
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug("Event loop was closed, creating a new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        logger.debug("No event loop found in thread, creating a new one")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_db():
    """Initialize the database with the schema defined in schema.sql"""
    with app.app_context():
        db = get_db()
        with open('schema.sql', 'r') as f:
            db.cursor().executescript(f.read())
        
        # Populate the sources table with sources from the JSON file
        try:
            # Check if sources.json exists
            if not os.path.exists(SOURCES_FILE):
                logger.warning(f"Sources file {SOURCES_FILE} not found. No sources will be added.")
                return
                
            # Load sources from JSON file
            with open(SOURCES_FILE, 'r') as f:
                sources_data = json.load(f)
                
            if 'sources' not in sources_data:
                logger.error(f"Invalid format in {SOURCES_FILE}. 'sources' key not found.")
                return
                
            sources = sources_data['sources']
            logger.info(f"Loaded {len(sources)} sources from {SOURCES_FILE}")
            
            cursor = db.cursor()
            for source in sources:
                if not all(key in source for key in ['url', 'source_type', 'category']):
                    logger.warning(f"Skipping source with missing data: {source}")
                    continue
                    
                # Extract name from source or use a default based on the URL
                name = source.get('name', source['url'].split('/')[-1])
                
                # Default sources have NULL user_id to indicate they're available to all users
                cursor.execute(
                    "INSERT OR IGNORE INTO sources (url, name, source_type, category, user_id) VALUES (?, ?, ?, ?, NULL)",
                    (source['url'], name, source['source_type'], source['category'])
                )
                
                # If the source exists but has different values, update it (preserving user_id)
                cursor.execute(
                    """
                    UPDATE sources 
                    SET name = ?, source_type = ?, category = ? 
                    WHERE url = ? AND (name != ? OR source_type != ? OR category != ?)
                    """,
                    (name, source['source_type'], source['category'], 
                     source['url'], name, source['source_type'], source['category'])
                )
                
            db.commit()
            logger.info(f'Sources table populated from {SOURCES_FILE}')
            
        except json.JSONDecodeError as e:
            logger.error(f'Error parsing sources file: {e}')
        except sqlite3.Error as e:
            logger.error(f'Error populating sources table: {e}')
        except Exception as e:
            logger.error(f'Unexpected error while populating sources: {e}')
            logger.error(traceback.format_exc())
        
        db.commit()
        logger.info('Database initialized with schema from schema.sql')

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    logger.info('Initialized the database.')

def format_log_data(data):
    """Format data for logging, truncating long content"""
    try:
        if isinstance(data, dict) or isinstance(data, list):
            formatted = pprint.pformat(data)
            return formatted
        elif isinstance(data, str):
            return data
        else:
            return str(data)
    except Exception as e:
        return f"[Error formatting log data: {str(e)}]"


@app.route('/summaries', methods=['GET'])
async def get_summaries():
    """
    API endpoint to generate summaries based on time period and sources.
    
    Query Parameters:
    - period: Time period to analyze ('1d', '2d', '1w')
    - sources: Comma-separated list of source URLs to filter by (optional)
    
    Response Format (JSON):
    {
        "topics": [
            {
                "topic": "Topic Name",
                "summary": "Detailed summary...",
                "message_ids": [1, 2, 3],
                "importance": 8,
                "metatopic": "Category"
            },
            ...
        ]
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /summaries - IP: {user_ip}")
    
    # Get query parameters
    period = request.args.get('period', '1d')
    sources_str = request.args.get('sources', '')
    sources = [s.strip() for s in sources_str.split(',')] if sources_str else None
    
    logger.info(f"REQUEST [{request_id}] - Parameters: period={period}, sources={sources}")
    
    # Send Telegram notification
    try:
        # Use synchronous notification method instead of awaiting
        success = sync_notify_summaries_request(request_id, period, sources_str)
        if success:
            logger.info(f"Notification sent successfully for summaries request: {request_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
    
    try:
        # Check if we need to fetch data for any sources that have no messages
        if sources:
            # Import data_fetcher to get messages if needed
            from data_fetcher import fetch_telegram_messages, authorize_client
            from telethon.tl.types import PeerChannel
            
            telegram_sources = []
            no_data_sources = []
            numeric_ids = []  # List of numeric channel IDs that need resolution
            
            # First, identify all types of sources
            for source in sources:
                source_type = None
                channel_id = None
                
                # Handle different source formats
                if source.startswith('https://t.me/'):
                    # This is a Telegram source with handle/username
                    source_type = 'telegram'
                    
                    # Extract channel_id from URL
                    parts = source.split('/')
                    if len(parts) > 3:
                        channel_id = parts[-1]
                    elif len(parts) == 3 and parts[-1]:
                        channel_id = parts[-1]
                    else:
                        channel_id = source
                    
                    telegram_sources.append({"url": source, "channel_id": channel_id, "is_numeric": False})
                
                elif source.isdigit() or (source.startswith('-') and source[1:].isdigit()):
                    # This is a Telegram numeric ID from JSON export
                    source_type = 'telegram'
                    channel_id = source
                    
                    # We'll need to resolve this ID to a proper channel
                    numeric_ids.append({"numeric_id": channel_id})
                    telegram_sources.append({"url": None, "channel_id": channel_id, "is_numeric": True})
            
            # If we have numeric IDs, resolve them to proper channel entities using Telegram API
            resolved_channels = {}  # Map of numeric_id -> proper channel URL
            
            if numeric_ids:
                logger.info(f"REQUEST [{request_id}] - Resolving {len(numeric_ids)} numeric channel IDs")
                
                try:
                    # Authorize Telegram client
                    client = await authorize_client()
                    
                    if client:
                        # Process each numeric ID
                        for item in numeric_ids:
                            numeric_id = item["numeric_id"]
                            try:
                                # Convert the numeric ID to integer
                                channel_id_int = int(numeric_id)
                                
                                # Use PeerChannel to create the proper peer object for the channel
                                print('peer = PeerChannel(channel_id_int)')
                                peer = PeerChannel(channel_id_int)
                                
                                # Get the channel entity directly from the peer
                                entity = await client.get_entity(peer)
                                
                                if entity:
                                    # Get username if available, otherwise use a URL with the numeric ID
                                    if hasattr(entity, 'username') and entity.username:
                                        channel_url = f"https://t.me/{entity.username}"
                                    else:
                                        # For channels without username, we'll use the original numeric ID
                                        # The data_fetcher should be able to handle this via the peer ID
                                        channel_url = f"tg-channel:{numeric_id}"  # Custom format to indicate numeric ID
                                    
                                    resolved_channels[numeric_id] = channel_url
                                    logger.info(f"Resolved channel ID {numeric_id} to {channel_url}")
                                else:
                                    logger.warning(f"Could not resolve channel ID: {numeric_id}")
                            except Exception as e:
                                logger.error(f"Error resolving channel ID {numeric_id}: {e}")
                                logger.error(traceback.format_exc())
                        
                        # Disconnect client when done
                        await client.disconnect()
                    else:
                        logger.error("Failed to authorize Telegram client for channel resolution")
                
                except Exception as e:
                    logger.error(f"Error during channel resolution: {e}")
                    logger.error(traceback.format_exc())
            
            # Now check which channels need data fetching
            for source_info in telegram_sources:
                channel_id = source_info["channel_id"]
                
                # For numeric IDs, use the resolved URL if available
                if source_info["is_numeric"]:
                    if channel_id in resolved_channels:
                        source_info["url"] = resolved_channels[channel_id]
                    else:
                        # Skip this channel if we couldn't resolve it
                        logger.warning(f"Skipping unresolved numeric channel ID: {channel_id}")
                        continue
                
                # Check if there are messages for this channel in the database
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # Try to find messages by channel ID
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM messages WHERE source_type = 'telegram' AND channel_id = ?",
                        (channel_id,)
                    )
                    result = cursor.fetchone()
                    
                    if result and result['count'] == 0:
                        # No messages for this channel, add to fetch list if we have a valid URL
                        if source_info["url"]:
                            logger.info(f"REQUEST [{request_id}] - No messages found for channel: {channel_id}")
                            no_data_sources.append(source_info["url"])
            
            # If there are sources with no data, fetch them
            if no_data_sources:
                logger.info(f"REQUEST [{request_id}] - Found {len(no_data_sources)} sources with no messages. Fetching data: {no_data_sources}")
                
                try:
                    # Fetch messages for these sources
                    fetched_data = await fetch_telegram_messages(no_data_sources, time_range=period)
                    
                    # Count new messages
                    new_messages_count = sum(len(message_ids) for message_ids in fetched_data.values())
                    logger.info(f"REQUEST [{request_id}] - Fetched {new_messages_count} messages for {len(no_data_sources)} sources")
                    
                except Exception as e:
                    logger.error(f"REQUEST [{request_id}] - Error fetching messages: {e}")
                    logger.error(traceback.format_exc())
                    # Continue with summarization even if fetch fails
        
        # Generate summaries with direct await
        logger.info(f"PROCESS [{request_id}] - Calling main with period={period}, sources={sources}")
        # Use main from data_summarizer which includes all enhancements
        summaries = await summarizer_main(period, sources, include_insights=False)
        
        if not summaries:
            logger.warning(f"PROCESS [{request_id}] - No summaries generated")
            return jsonify({"topics": []}), 200
        
        # Log detailed result information
        logger.info(f"RESPONSE [{request_id}] - Generated {len(summaries)} topics")
        
        # Create and log the response
        response = {"topics": summaries}
        logger.info(f"RESPONSE [{request_id}] - Response size: {len(str(response))} bytes")
        
        return jsonify(response), 200
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process summaries request: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({"error": str(e)}), 500

@app.route('/insights', methods=['POST'])
async def get_insights():
    """
    API endpoint to generate actionable insights based on provided summaries.
    
    Request Format (JSON):
    {
        "topics": [
            {
                "topic": "Topic Name",
                "summary": "Detailed summary...",
                "message_ids": [1, 2, 3],
                "importance": 8
            }
        ]
    }
    
    Response Format (JSON):
    {
        "topics": [
            {
                "topic": "Topic Name",
                "summary": "Detailed summary...",
                "message_ids": [1, 2, 3],
                "importance": 8,
                "insights": {
                    "analysis_summary": "Concise interpretation of the news...",
                    "stance": "Long/Short/Neutral/Long-Neutral/Short-Neutral/No Actionable Insight",
                    "rationale_long": "Reasons supporting a long position...",
                    "rationale_short": "Reasons supporting a short position...",
                    "rationale_neutral": "Reasons for neutral stance...",
                    "risks_and_watchouts": [
                        "Risk 1 description...",
                        "Risk 2 description..."
                    ],
                    "key_questions_for_user": [
                        "Question 1 for research...",
                        "Question 2 for research..."
                    ],
                    "suggested_instruments_long": [
                        {
                            "instrument": "Instrument name...",
                            "rationale": "Explanation for this instrument...",
                            "type": "DeFi/TradFi"
                        }
                    ],
                    "suggested_instruments_short": [
                        {
                            "instrument": "Instrument name...",
                            "rationale": "Explanation for this instrument...",
                            "type": "DeFi/TradFi"
                        }
                    ],
                    "useful_resources": [
                        {
                            "url": "https://example.com",
                            "description": "Resource description..."
                        }
                    ]
                }
            }
        ]
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /insights - IP: {user_ip}")
    
    try:
        # Get JSON data from request body
        data = request.get_json()
        if not data or 'topics' not in data:
            return jsonify({"error": "Invalid request body. 'topics' field is required."}), 400
            
        summaries = data['topics']
        if not summaries or not isinstance(summaries, list):
            return jsonify({"error": "Invalid 'topics' field. Expected a non-empty array."}), 400
        
        topic_names = [topic.get('topic', 'Unknown') for topic in summaries]
        logger.info(f"REQUEST [{request_id}] - Processing insights for topic(s): {', '.join(topic_names)}")
        
        # Send Telegram notification
        try:
            # Use synchronous notification method instead of awaiting
            success = sync_notify_insights_request(request_id, len(summaries))
            if success:
                logger.info(f"Notification sent successfully for insights request: {request_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
        
        # Generate insights for each topic with direct await
        logger.info(f"PROCESS [{request_id}] - Generating insights for {len(summaries)} topic(s)")
        
        # Create a fresh event loop for this request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Generate insights in the new event loop
            topics_with_insights = await generate_insights(summaries)
        finally:
            # Don't close the loop here - this can cause issues with subsequent calls
            pass
        
        # Log detailed result information
        logger.info(f"RESPONSE [{request_id}] - Generated insights for {len(topics_with_insights)} topic(s)")
        
        # Create and log the response
        response = {"topics": topics_with_insights}
        logger.info(f"RESPONSE [{request_id}] - Response size: {len(str(response))} bytes")
        
        return jsonify(response), 200
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process insights request: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({"error": str(e)}), 500

@app.route('/sources', methods=['GET'])
async def get_sources():
    """
    API endpoint to retrieve all sources with their categories from the database.
    
    Query Parameters:
        - userId: Optional user ID to filter sources by user
        - includeDefault: Whether to include default sources (default: true)
    
    Returns:
        A JSON list of sources grouped by category.
    """
    try:
        # Ensure we have a valid event loop
        ensure_event_loop()
        
        # Get query parameters
        user_id = request.args.get('userId')
        include_default = request.args.get('includeDefault', 'true').lower() == 'true'
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Build query based on parameters
            query = """
                SELECT id, url, name, source_type, category FROM sources 
                WHERE 1=1
            """
            params = []
            
            if user_id:
                # Include user-specific sources and optionally default sources
                if include_default:
                    query += " AND (user_id = ? OR user_id IS NULL)"
                    params.append(user_id)
                else:
                    query += " AND user_id = ?"
                    params.append(user_id)
            
            query += " ORDER BY category, name, url"
            
            cursor.execute(query, params)
            
            sources = cursor.fetchall()
            
            # Group sources by category
            categorized_sources = {}
            for source in sources:
                category = source['category']
                if category not in categorized_sources:
                    categorized_sources[category] = []
                
                categorized_sources[category].append({
                    'id': source['id'],
                    'url': source['url'],
                    'name': source['name'] if source['name'] else source['url'].split('/')[-1],  # Use last part of URL if no name provided
                    'source_type': source['source_type']
                })
            
            return jsonify({"sources": categorized_sources}), 200
            
    except Exception as e:
        error_message = f"Error retrieving sources: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        return jsonify({"error": error_message}), 500

@app.route('/message/<int:message_id>', methods=['GET'])
async def get_message(message_id):
    """
    API endpoint to retrieve a specific message by its ID.
    
    Parameters:
        message_id: The ID of the message to retrieve
        
    Returns:
        A JSON object with the message content, source, and date
    """
    try:
        # Ensure we have a valid event loop
        ensure_event_loop()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.id, m.data, m.date, m.source_url, 
                       COALESCE(s.name, m.source_url) as source_name
                FROM messages m
                LEFT JOIN sources s ON m.source_url = s.url
                WHERE m.id = ?
                """, 
                (message_id,)
            )
            
            message = cursor.fetchone()
            
            if not message:
                return jsonify({"error": f"Message with ID {message_id} not found"}), 404
            
            return jsonify({
                "id": message['id'],
                "content": message['data'],
                "date": message['date'],
                "source": message['source_name'] or message['source_url']
            }), 200
            
    except Exception as e:
        error_message = f"Error retrieving message: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        return jsonify({"error": error_message}), 500

@app.route('/insights', methods=['GET'])
async def get_insights_legacy():
    """
    Legacy API endpoint that combines both summary and insights generation.
    This is maintained for backward compatibility.
    
    Query Parameters:
    - period: Time period to analyze ('1d', '2d', '1w')
    - sources: Comma-separated list of source URLs to filter by (optional)
    
    Response Format (JSON):
    {
        "topics": [
            {
                "topic": "Topic Name",
                "summary": "Detailed summary...",
                "message_ids": [1, 2, 3],
                "importance": 8,
                "metatopic": "Category",
                "insights": {
                    "analysis_summary": "Concise interpretation of the news...",
                    "stance": "Long/Short/Neutral/Long-Neutral/Short-Neutral/No Actionable Insight",
                    "rationale_long": "Reasons supporting a long position...",
                    "rationale_short": "Reasons supporting a short position...",
                    "rationale_neutral": "Reasons for neutral stance...",
                    "risks_and_watchouts": [
                        "Risk 1 description...",
                        "Risk 2 description..."
                    ],
                    "key_questions_for_user": [
                        "Question 1 for research...",
                        "Question 2 for research..."
                    ],
                    "suggested_instruments_long": [
                        {
                            "instrument": "Instrument name...",
                            "rationale": "Explanation for this instrument...",
                            "type": "DeFi/TradFi"
                        }
                    ],
                    "suggested_instruments_short": [
                        {
                            "instrument": "Instrument name...",
                            "rationale": "Explanation for this instrument...",
                            "type": "DeFi/TradFi"
                        }
                    ],
                    "useful_resources": [
                        {
                            "url": "https://example.com",
                            "description": "Resource description..."
                        }
                    ]
                }
            },
            ...
        ]
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /insights (legacy GET) - IP: {user_ip}")
    
    # Get query parameters
    period = request.args.get('period', '1d')
    sources_str = request.args.get('sources', '')
    sources = [s.strip() for s in sources_str.split(',')] if sources_str else None
    
    logger.info(f"REQUEST [{request_id}] - Parameters: period={period}, sources={sources}")
    
    # We can use the same summaries notification here as it's similar
    try:
        # Use synchronous notification method instead of awaiting
        success = sync_notify_summaries_request(request_id, period, sources_str)
        if success:
            logger.info(f"Notification sent successfully for legacy insights request: {request_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
    
    try:
        # Generate summaries with direct await
        logger.info(f"PROCESS [{request_id}] - Calling main with period={period}, sources={sources}, include_insights=True")
        # Use the main function which now includes all enhancements plus insights
        topics_with_insights = await summarizer_main(period, sources, include_insights=True)
        
        if not topics_with_insights:
            logger.warning(f"PROCESS [{request_id}] - No topics generated")
            return jsonify({"topics": []}), 200
        
        # Log detailed result information
        logger.info(f"RESPONSE [{request_id}] - Generated {len(topics_with_insights)} topics with insights")
        
        # Create and log the response
        response = {"topics": topics_with_insights}
        logger.info(f"RESPONSE [{request_id}] - Response size: {len(str(response))} bytes")
        
        return jsonify(response), 200
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process insights request: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['POST'])
async def submit_feedback():
    """
    API endpoint to submit user feedback.
    
    Request Format (JSON):
    {
        "email": "user@example.com",
        "message": "This is feedback from the user",
        "type": "feedback" | "question" | "bug"
    }
    
    Response Format (JSON):
    {
        "success": true,
        "message": "Feedback submitted successfully"
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /feedback - IP: {user_ip}")
    
    try:
        # Get JSON data from request body
        data = request.get_json()
        
        # Validate required fields
        if not data or not all(key in data for key in ['email', 'message', 'type']):
            return jsonify({
                "success": False,
                "error": "Missing required fields: email, message, type"
            }), 400
            
        # Validate email format
        email = data['email']
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                "success": False,
                "error": "Invalid email format"
            }), 400
            
        # Validate feedback type
        feedback_type = data['type']
        if feedback_type not in ['feedback', 'question', 'bug']:
            return jsonify({
                "success": False,
                "error": "Invalid feedback type. Must be one of: feedback, question, bug"
            }), 400
            
        # Store feedback in database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedback (email, message, type) VALUES (?, ?, ?)",
                (data['email'], data['message'], data['type'])
            )
            conn.commit()
        
        # Send Telegram notification
        try:
            print('Send Telegram notification')
            # Use synchronous notification method instead of awaiting
            success = sync_notify_new_feedback(email, feedback_type, data['message'])
            print(f'Notification sent: {success}')
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            
        logger.info(f"RESPONSE [{request_id}] - Feedback submitted successfully from {email}")
        
        return jsonify({
            "success": True,
            "message": "Feedback submitted successfully"
        }), 201
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to submit feedback: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({
            "success": False,
            "error": f"Failed to submit feedback: {str(e)}"
        }), 500

@app.route('/subscribe', methods=['POST'])
async def subscribe():
    """
    API endpoint to subscribe a user via email.
    
    Request Format (JSON):
    {
        "email": "user@example.com",
        "source": "main" | "custom-sources" | "newsletter" (optional)
    }
    
    Response Format (JSON):
    {
        "success": true,
        "message": "Subscription successful"
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /subscribe - IP: {user_ip}")
    
    try:
        # Get JSON data from request body
        data = request.get_json()
        
        # Validate required fields
        if not data or 'email' not in data:
            return jsonify({
                "success": False,
                "error": "Missing required field: email"
            }), 400
            
        # Validate email format
        email = data['email']
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                "success": False,
                "error": "Invalid email format"
            }), 400
            
        # Get source (optional)
        source = data.get('source', 'main')
        
        # Store subscription in database
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO subscribers (email, source) VALUES (?, ?)",
                    (email, source)
                )
                conn.commit()
                is_new = True
            except sqlite3.IntegrityError:
                # Email already exists, update the source instead
                cursor.execute(
                    "UPDATE subscribers SET source = ?, created_at = CURRENT_TIMESTAMP WHERE email = ?",
                    (source, email)
                )
                conn.commit()
                is_new = False
        
        # Send Telegram notification 
        try:
            print('Send Telegram notification')
            # Use synchronous notification method instead of awaiting
            success = sync_notify_new_subscriber(email, source)
            print(f'Notification sent: {success}')
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            
        message = "Subscription successful" if is_new else "Subscription updated"
        logger.info(f"RESPONSE [{request_id}] - {message} for {email}")
        
        return jsonify({
            "success": True,
            "message": message
        }), 201
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process subscription: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({
            "success": False,
            "error": f"Failed to process subscription: {str(e)}"
        }), 500

@app.route('/subscribers', methods=['GET'])
async def get_subscribers():
    """
    API endpoint to get all subscribers (admin only).
    Requires an admin token for authentication.
    
    Query Parameters:
    - token: Admin token for authentication
    - source: Filter by subscription source (optional)
    
    Response Format (JSON):
    {
        "subscribers": [
            {
                "email": "user@example.com",
                "source": "main",
                "created_at": "2023-05-20T12:34:56"
            },
            ...
        ],
        "count": 1
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Check for admin token
    admin_token = request.args.get('token')
    # In production, use a secure token from environment variables
    if admin_token != os.getenv('ADMIN_TOKEN', 'admin-secret-token'):
        return jsonify({
            "success": False,
            "error": "Unauthorized access"
        }), 401
    
    try:
        # Get source filter (optional)
        source_filter = request.args.get('source')
        
        # Retrieve subscribers from database
        with get_db() as conn:
            cursor = conn.cursor()
            
            if source_filter:
                cursor.execute(
                    "SELECT email, source, created_at FROM subscribers WHERE source = ? ORDER BY created_at DESC",
                    (source_filter,)
                )
            else:
                cursor.execute(
                    "SELECT email, source, created_at FROM subscribers ORDER BY created_at DESC"
                )
                
            subscribers = [
                {
                    "email": row['email'],
                    "source": row['source'],
                    "created_at": row['created_at']
                }
                for row in cursor.fetchall()
            ]
            
        return jsonify({
            "subscribers": subscribers,
            "count": len(subscribers)
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve subscribers: {str(e)}"
        }), 500

@app.route('/upload-telegram-export', methods=['POST'])
async def upload_telegram_export():
    """
    API endpoint to handle uploaded Telegram export files.
    
    Request:
        - multipart/form-data with a 'file' field containing the JSON export
        
    Response Format (JSON):
    {
        "success": true,
        "channels": [
            {
                "id": 1234567890,
                "name": "Channel Name",
                "type": "public_channel"
            },
            ...
        ]
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /upload-telegram-export - IP: {user_ip}")
    logger.debug(f"Request content type: {request.content_type}")
    
    try:
        # Check if file exists in request
        if 'file' not in request.files:
            logger.warning(f"REQUEST [{request_id}] - No file part in the request")
            response = jsonify({
                "success": False,
                "error": "No file uploaded"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
            
        file = request.files['file']
        
        # Check if file has a name
        if file.filename == '':
            logger.warning(f"REQUEST [{request_id}] - Empty filename")
            response = jsonify({
                "success": False,
                "error": "No file selected"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        
        # Log the file info for debugging
        logger.debug(f"File received: {file.filename}, Content-Type: {file.content_type}")
            
        # Check if file is valid JSON
        try:
            file_content = file.read()
            logger.debug(f"Read {len(file_content)} bytes from file")
            export_data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"REQUEST [{request_id}] - Invalid JSON file: {str(e)}")
            response = jsonify({
                "success": False,
                "error": f"Invalid JSON file format: {str(e)}"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        except Exception as e:
            logger.error(f"REQUEST [{request_id}] - Error reading file: {str(e)}")
            response = jsonify({
                "success": False,
                "error": f"Error reading file: {str(e)}"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
            
        # Extract channel information from the export
        channels = []
        
        # Define channel types - ONLY these types are considered valid channels
        # Explicitly exclude regular group chats and private 1-on-1 chats
        # valid_channel_types = ['public_channel', 'private_channel', 'public_supergroup', 'private_supergroup']
        valid_channel_types = ['public_channel']
        
        # Process "chats" section if it exists
        if 'chats' in export_data and 'list' in export_data['chats']:
            for chat in export_data['chats']['list'][:10]: 
                chat_type = chat.get('type')
                logger.debug(f"Chat type: {chat_type}, chat: {chat}")
                if chat_type in valid_channel_types:
                    channels.append({
                        'id': chat.get('id'),
                        'name': chat.get('name', 'Unknown Channel'),
                        'type': chat_type
                    })
                else:
                    logger.debug(f"Skipping chat of type '{chat_type}' as it's not a channel: {chat.get('name')}")
        

        if not channels:
            logger.warning(f"REQUEST [{request_id}] - No channels found in the export")
            response = jsonify({
                "success": False,
                "error": "No channels found in the export file. Please ensure your export contains channels, not regular chats."
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
            
        logger.info(f"RESPONSE [{request_id}] - Found {len(channels)} channels in Telegram export")
        
        response = jsonify({
            "success": True,
            "channels": channels
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 200
        
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process Telegram export: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        response = jsonify({
            "success": False,
            "error": str(e)
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/channel-progress', methods=['GET'])
def get_channel_progress():
    """
    API endpoint to stream progress updates using Server-Sent Events (SSE).
    
    Query Parameters:
    - requestId: A unique identifier for the request to track progress
    
    Response:
    A stream of Server-Sent Events with progress updates
    """
    request_id = request.args.get('requestId', 'default')
    
    def generate():
        prev_data = None
        
        # Send initial data if available
        if request_id in channel_progress_data:
            yield f"data: {json.dumps(channel_progress_data[request_id])}\n\n"
            prev_data = channel_progress_data[request_id]
        else:
            # Send default initial data
            initial_data = {
                "processedChannels": 0,
                "totalChannels": 0,
                "currentChannel": None
            }
            yield f"data: {json.dumps(initial_data)}\n\n"
            prev_data = initial_data
        
        # Keep the connection open and send updates
        while True:
            if request_id in channel_progress_data:
                current_data = channel_progress_data[request_id]
                
                # Only send updates when data changes
                if current_data != prev_data:
                    yield f"data: {json.dumps(current_data)}\n\n"
                    prev_data = current_data.copy()
                    
                # If processing is complete, break the loop
                if current_data.get('processedChannels', 0) >= current_data.get('totalChannels', 0) and current_data.get('totalChannels', 0) > 0:
                    # Send one final update
                    yield f"data: {json.dumps(current_data)}\n\n"
                    break
            
            # Wait before checking again
            time.sleep(0.5)
    
    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable buffering for Nginx
    return response

@app.route('/cluster-channels', methods=['POST'])
async def cluster_channels():
    """
    API endpoint to cluster channels into topics using Gemini Flash.
    Fetches sample messages directly from Telegram, detects language, 
    and intelligently groups channels by topic regardless of language.
    
    Request Format (JSON):
    {
        "channels": [
            {
                "id": 1234567890,
                "name": "Channel Name",
                "type": "public_channel"
            },
            ...
        ],
        "simplified_fetching": true  // Optional, if true, skip link parsing for initial clustering
    }
    
    Response Format (JSON):
    {
        "success": true,
        "topics": [
            {
                "topic": "Finance",
                "language": "en", // Primary language or "mixed" if multiple languages
                "channels": [
                    {
                        "id": 1234567890,
                        "name": "Channel Name",
                        "type": "public_channel",
                        "last_message_date": "2023-05-20T12:34:56",
                        "language": "en"
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /cluster-channels - IP: {user_ip}")
    
    try:
        # Get JSON data from request body
        data = request.get_json()
        
        if not data or 'channels' not in data or not data['channels']:
            response = jsonify({
                "success": False,
                "error": "No channels provided"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
            
        channels = data['channels']
        simplified_fetching = data.get('simplified_fetching', False)
        
        logger.info(f"REQUEST [{request_id}] - Clustering {len(channels)} channels with simplified_fetching={simplified_fetching}")
        
        # Import data_fetcher to get channel messages
        from data_fetcher import fetch_channel_sample_messages
        from instruction_templates import INSTRUCTIONS
        from telethon.tl.types import PeerChannel
        
        # Enhance channel data with sample messages and attempt to detect language
        enhanced_channels = []
        total_channels = len(channels)
        
        # Initialize clustering progress tracking
        if request_id != 'unknown':
            channel_progress_data[request_id] = {
                "processedChannels": 0,
                "totalChannels": total_channels,
                "currentChannel": "Starting analysis..."
            }
        
        for i, channel in enumerate(channels):
            channel_id = str(channel.get('id', ''))
            channel_name = channel.get('name', f"Channel {channel_id}")
            
            # Update progress
            if request_id != 'unknown':
                channel_progress_data[request_id] = {
                    "processedChannels": i,
                    "totalChannels": total_channels,
                    "currentChannel": channel_name
                }
            
            # For numeric IDs (from JSON exports), create special format
            if channel_id.isdigit() or (channel_id.startswith('-') and channel_id[1:].isdigit()):
                channel_url = f"tg-channel:{channel_id}"
            else:
                channel_url = convert_telegram_channel_to_url(channel_id)
            
            # Build enhanced channel object
            enhanced_channel = {
                **channel,
                'url': channel_url,
                'last_message_date': None,
                'sample_content': "",
                'language': "unknown"
            }
            
            # Fetch sample messages directly from Telegram
            try:
                logger.info(f"Fetching sample messages for channel {channel_id} using {channel_url}")
                sample_messages = await fetch_channel_sample_messages(channel_url, message_limit=5, skip_link_parsing=simplified_fetching)
                
                if sample_messages:
                    # Set the latest message date
                    enhanced_channel['last_message_date'] = sample_messages[0]['date']
                    
                    # Combine message content as a sample
                    sample_content = "\n\n".join([msg['text'] for msg in sample_messages if msg['text']])
                    enhanced_channel['sample_content'] = sample_content
                    logger.debug(f"Channel URL: {channel_url}")
                    logger.debug(f"Sample content: {enhanced_channel['sample_content']}")
                    
                    # Improved language detection based on character sets
                    if sample_content:
                        # Check for Cyrillic (Russian, Ukrainian, etc.)
                        cyrillic_chars = sum(1 for c in sample_content if '\u0400' <= c <= '\u04FF')
                        cyrillic_ratio = cyrillic_chars / len(sample_content) if len(sample_content) > 0 else 0
                        
                        # Check for CJK characters (Chinese, Japanese, Korean)
                        cjk_chars = sum(1 for c in sample_content if '\u4E00' <= c <= '\u9FFF')
                        cjk_ratio = cjk_chars / len(sample_content) if len(sample_content) > 0 else 0
                        
                        # Check for Arabic characters
                        arabic_chars = sum(1 for c in sample_content if '\u0600' <= c <= '\u06FF')
                        arabic_ratio = arabic_chars / len(sample_content) if len(sample_content) > 0 else 0
                        
                        if cyrillic_ratio > 0.3:
                            enhanced_channel['language'] = "ru"  # Using "ru" as general Cyrillic identifier
                        elif cjk_ratio > 0.3:
                            enhanced_channel['language'] = "zh"  # Using "zh" as general CJK identifier
                        elif arabic_ratio > 0.3:
                            enhanced_channel['language'] = "ar"  # Using "ar" as general Arabic identifier
                        else:
                            enhanced_channel['language'] = "en"  # Default to English
                        
                        logger.debug(f"Language detection: {enhanced_channel['language']} (Cyrillic: {cyrillic_ratio:.2f}, CJK: {cjk_ratio:.2f}, Arabic: {arabic_ratio:.2f})")
            except Exception as e:
                logger.warning(f"Failed to fetch sample messages for channel {channel_id}: {e}")
                logger.warning(traceback.format_exc())
            
            enhanced_channels.append(enhanced_channel)
        
        # Import Gemini API
        from google import genai
        
        # Configure Gemini API
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            response = jsonify({
                "success": False,
                "error": "Gemini API key not configured"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 500
            
        client = genai.Client(api_key=gemini_api_key)
        model_name = os.getenv('GEMINI_MODEL_METATOPICS', 'gemini-1.5-flash')

        logger.debug(f"enhanced_channels: {[enhanced_channel['name'] for enhanced_channel in enhanced_channels]}")
        
        # Prepare the channel information for the prompt
        channels_info = []
        for i, channel in enumerate(enhanced_channels):
            channel_info = f"{i+1}. Name: {channel['name']}"
            if channel['sample_content']:
                channel_info += f"\nSample content: {channel['sample_content']}"
            if channel['language'] != "unknown":
                channel_info += f"\nDetected language: {channel['language']}"
            channels_info.append(channel_info)
        
        channel_list = "\n\n".join(channels_info)
        
        # Use the template from instruction_templates.py
        # The updated template will translate non-English content and cluster by topic
        prompt = INSTRUCTIONS["channel_clustering"].format(
            channel_info=channel_list
        )
        
        logger.info(f"REQUEST [{request_id}] - Sending clustering request to Gemini API using model: {model_name}")
        logger.debug(f"Prompt: {prompt}")
        
        # Call Gemini API
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        # Extract JSON from response
        response_text = response.text
        logger.debug(f"Gemini response: {response_text}")
        
        # Parse the JSON
        try:
            # Find JSON content (may be wrapped in markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                json_str = response_text
                
            # Parse the JSON
            topics_data = json.loads(json_str)
            logger.debug(f"topics_data: {topics_data}")
            
            # Validate the response structure
            if not isinstance(topics_data, list):
                raise ValueError("Expected a list of topic categories")
                
            # Convert the format to include full channel objects
            topics_result = []
            for topic_item in topics_data:
                topic_name = topic_item.get('topic', 'Miscellaneous')
                language = topic_item.get('language', 'unknown')
                channel_indices = topic_item.get('channel_indices', [])
                
                topic_channels = []
                for idx in channel_indices:
                    if 0 <= idx < len(enhanced_channels):
                        topic_channels.append(enhanced_channels[idx])
                
                topics_result.append({
                    "topic": topic_name,
                    "language": language,
                    "channels": topic_channels
                })
            
            # Update progress to show completion
            if request_id != 'unknown':
                channel_progress_data[request_id] = {
                    "processedChannels": total_channels,
                    "totalChannels": total_channels,
                    "currentChannel": "Clustering complete!"
                }
                
                # Schedule cleanup of progress data
                def cleanup_progress():
                    if request_id in channel_progress_data:
                        del channel_progress_data[request_id]
                    
                # Schedule cleanup after 5 minutes
                threading.Timer(300, cleanup_progress).start()
            
            logger.info(f"RESPONSE [{request_id}] - Clustered channels into {len(topics_result)} topics")

            logger.debug(f"topics_result: {topics_result}")
            
            api_response = jsonify({
                "success": True,
                "topics": topics_result
            })
            api_response.headers['Content-Type'] = 'application/json'
            return api_response, 200
            
        except json.JSONDecodeError as e:
            logger.error(f"ERROR [{request_id}] - Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            api_response = jsonify({
                "success": False,
                "error": "Failed to parse AI response"
            })
            api_response.headers['Content-Type'] = 'application/json'
            return api_response, 500
            
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to cluster channels: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        api_response = jsonify({
            "success": False,
            "error": str(e)
        })
        api_response.headers['Content-Type'] = 'application/json'
        return api_response, 500

def convert_telegram_channel_to_url(channel_id):
    """
    Convert a Telegram channel ID to a source URL.
    
    Args:
        channel_id: Telegram channel ID (numeric or string)
        
    Returns:
        str: Telegram channel URL in the format https://t.me/channelname
    """
    return f"https://t.me/{channel_id}"

@app.route('/save-telegram-channels', methods=['POST'])
async def save_telegram_channels():
    """
    API endpoint to save selected Telegram channels to the database and fetch messages from them.
    
    Request Format (JSON):
    {
        "channels": [
            {
                "id": 1234567890,
                "name": "Channel Name",
                "type": "public_channel",
                "url": "https://t.me/channelname"
            },
            ...
        ],
        "userId": "optional-user-id",  // Optional user ID for future user-specific sources
        "period": "1d"  // Time period for fetching messages (1d, 2d, 1w)
    }
    
    Response Format (JSON):
    {
        "success": true,
        "message": "Channels saved and messages fetched successfully",
        "savedChannels": 5,
        "newMessagesCount": 10
    }
    """
    # Ensure we have a valid event loop
    ensure_event_loop()
    
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', str(int(time.time())))
    
    logger.info(f"REQUEST [{request_id}] - /save-telegram-channels - IP: {user_ip}")
    
    try:
        # Get JSON data from request body
        data = request.get_json()
        
        if not data or 'channels' not in data:
            response = jsonify({
                "success": False,
                "error": "No channels provided"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        
        channels = data['channels']
        user_id = data.get('userId')
        period = data.get('period', '1d')
        
        if not channels:
            response = jsonify({
                "success": False,
                "error": "Empty channels list"
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
        
        logger.info(f"REQUEST [{request_id}] - Saving {len(channels)} Telegram channels")
        
        # Initialize progress tracking
        channel_progress_data[request_id] = {
            "processedChannels": 0,
            "totalChannels": len(channels),
            "currentChannel": None
        }
        
        # First save the channels to the sources table
        saved_channels = 0
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            for channel in channels:
                channel_id = str(channel.get('id', ''))
                channel_name = channel.get('name', f"Channel {channel_id}")
                channel_url = channel.get('url') or convert_telegram_channel_to_url(channel_id)
                
                # Add or update the source in the database
                try:
                    cursor.execute(
                        """
                        INSERT INTO sources (url, name, source_type, category, user_id) 
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE 
                        SET name = ?, user_id = ?
                        """,
                        (channel_url, channel_name, 'telegram', 'Telegram Import', user_id,
                         channel_name, user_id)
                    )
                    saved_channels += 1
                except sqlite3.Error as e:
                    logger.error(f"Error saving channel {channel_name} to database: {e}")
            
            conn.commit()
        
        # Now fetch messages from these channels
        from data_fetcher import fetch_telegram_messages
        
        # Prepare a list of channel URLs for fetching
        channel_urls = []
        for channel in channels:
            channel_url = channel.get('url') or convert_telegram_channel_to_url(str(channel.get('id', '')))
            channel_urls.append({
                'url': channel_url,
                'name': channel.get('name', f"Channel {channel.get('id', '')}")
            })
        
        logger.info(f"REQUEST [{request_id}] - Fetching messages from {len(channel_urls)} channels for period {period}")
        
        # Fetch messages with progress tracking
        fetched_data = await fetch_telegram_messages(
            channel_urls, 
            time_range=period,
            request_id=request_id,
            progress_callback=lambda processed, total, current: update_channel_progress(request_id, processed, total, current)
        )
        
        # Count new messages
        new_messages_count = sum(len(message_ids) for message_ids in fetched_data.values())
        
        logger.info(f"RESPONSE [{request_id}] - Saved {saved_channels} channels and fetched {new_messages_count} messages")
        
        # Finalize progress tracking
        channel_progress_data[request_id] = {
            "processedChannels": len(channels),
            "totalChannels": len(channels),
            "currentChannel": "Complete"
        }
        
        # Schedule cleanup of progress data
        def cleanup_progress():
            if request_id in channel_progress_data:
                del channel_progress_data[request_id]
                
        # Schedule cleanup after 5 minutes
        threading.Timer(300, cleanup_progress).start()
        
        response = jsonify({
            "success": True,
            "message": "Channels saved and messages fetched successfully",
            "savedChannels": saved_channels,
            "newMessagesCount": new_messages_count
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 200
        
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to save channels: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        # Update progress data to indicate error
        if request_id in channel_progress_data:
            channel_progress_data[request_id]['error'] = str(e)
        
        response = jsonify({
            "success": False,
            "error": str(e)
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

def update_channel_progress(request_id, processed_channels, total_channels, current_channel):
    """
    Update the progress data for a specific request.
    
    Args:
        request_id: The unique identifier for the request
        processed_channels: Number of channels processed so far
        total_channels: Total number of channels to process
        current_channel: Name of the channel currently being processed
    """
    channel_progress_data[request_id] = {
        "processedChannels": processed_channels,
        "totalChannels": total_channels,
        "currentChannel": current_channel
    }

if __name__ == '__main__':
    logger.info("Application starting up")
    # Initialize the event loop before starting the app
    ensure_event_loop()
    # Run with threaded=True and a higher thread limit to handle multiple concurrent requests
    app.run(host='0.0.0.0', debug=True, threaded=True, use_reloader=False)  # Disable reloader to avoid event loop issues