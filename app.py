    # app.py
from flask import Flask, request, jsonify
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
    level=logging.INFO,
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
                
                cursor.execute(
                    "INSERT OR IGNORE INTO sources (url, name, source_type, category) VALUES (?, ?, ?, ?)",
                    (source['url'], name, source['source_type'], source['category'])
                )
                
                # If the source exists but has different values, update it
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
    
    Returns:
        A JSON list of sources grouped by category.
    """
    try:
        # Ensure we have a valid event loop
        ensure_event_loop()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, url, name, source_type, category FROM sources 
                ORDER BY category, name, url
                """
            )
            
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
        
        # Process "chats" section if it exists
        if 'chats' in export_data and 'list' in export_data['chats']:
            for chat in export_data['chats']['list']:
                if chat.get('type') in ['public_channel', 'private_channel', 'private_supergroup', 'public_supergroup']:
                    channels.append({
                        'id': chat.get('id'),
                        'name': chat.get('name', 'Unknown Channel'),
                        'type': chat.get('type')
                    })
        
        # Process "left_chats" section if it exists
        if 'left_chats' in export_data and 'list' in export_data['left_chats']:
            for chat in export_data['left_chats']['list']:
                if chat.get('type') in ['public_channel', 'private_channel', 'private_supergroup', 'public_supergroup']:
                    channels.append({
                        'id': chat.get('id'),
                        'name': chat.get('name', 'Unknown Channel'),
                        'type': chat.get('type'),
                        'left': True
                    })
        
        if not channels:
            logger.warning(f"REQUEST [{request_id}] - No channels found in the export")
            response = jsonify({
                "success": False,
                "error": "No channels found in the export file"
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

@app.route('/cluster-channels', methods=['POST'])
async def cluster_channels():
    """
    API endpoint to cluster channels into topics using Gemini Flash.
    
    Request Format (JSON):
    {
        "channels": [
            {
                "id": 1234567890,
                "name": "Channel Name",
                "type": "public_channel"
            },
            ...
        ]
    }
    
    Response Format (JSON):
    {
        "success": true,
        "topics": [
            {
                "topic": "Finance",
                "channels": [
                    {
                        "id": 1234567890,
                        "name": "Channel Name",
                        "type": "public_channel"
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
        
        logger.info(f"REQUEST [{request_id}] - Clustering {len(channels)} channels")
        
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
        
        # Prepare the prompt for Gemini
        channel_names = [f"{i+1}. {channel['name']}" for i, channel in enumerate(channels)]
        channel_list = "\n".join(channel_names)
        
        prompt = f"""
        I have a list of Telegram channels that I need to categorize into coherent topic groups.
        Please analyze these channel names and group them into 3-8 meaningful topic categories.
        For each channel, assign it to the most appropriate category.
        
        Channel names:
        {channel_list}
        
        Return the results as a JSON array where each object represents a topic category with the following structure:
        [
            {{
                "topic": "Category name (e.g., Crypto News, Programming, Politics, etc.)",
                "channel_indices": [0, 2, 5]  // Indices of channels (0-based) that belong to this category
            }},
            ...
        ]
        
        Consider that some channels might have names in languages other than English, but try to infer their category from any identifiable words or patterns.
        Use broad, intuitive categories that would make sense for news aggregation.
        """
        
        logger.info(f"REQUEST [{request_id}] - Sending clustering request to Gemini API using model: {model_name}")
        
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
            
            # Validate the response structure
            if not isinstance(topics_data, list):
                raise ValueError("Expected a list of topic categories")
                
            # Convert the format to include full channel objects
            topics_result = []
            for topic_item in topics_data:
                topic_name = topic_item.get('topic', 'Miscellaneous')
                channel_indices = topic_item.get('channel_indices', [])
                
                topic_channels = []
                for idx in channel_indices:
                    if 0 <= idx < len(channels):
                        topic_channels.append(channels[idx])
                
                topics_result.append({
                    "topic": topic_name,
                    "channels": topic_channels
                })
            
            logger.info(f"RESPONSE [{request_id}] - Clustered channels into {len(topics_result)} topics")
            
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

if __name__ == '__main__':
    logger.info("Application starting up")
    # Initialize the event loop before starting the app
    ensure_event_loop()
    # Run with threaded=True and a higher thread limit to handle multiple concurrent requests
    app.run(host='0.0.0.0', debug=False, threaded=True, use_reloader=False)  # Disable reloader to avoid event loop issues