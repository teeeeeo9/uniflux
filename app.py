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
CORS(app)

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

# Helper function to run async functions in a synchronous context
def run_async(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get or create an event loop for this thread
        loop = ensure_event_loop()
        
        try:
            # Run the function in the event loop
            return loop.run_until_complete(func(*args, **kwargs))
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # If the loop closed during execution, create a new one and retry
                logger.warning("Event loop closed during execution. Creating a new one and retrying...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(func(*args, **kwargs))
            else:
                raise
        finally:
            # Don't close the loop after use - this helps prevent issues with subsequent calls
            pass
    return wrapper

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
                    "general": "...",
                    "long": "...",
                    "exec_options_long": [
                        {"text": "...", "description": "...", "type": "defi"}
                    ],
                    "short": "...",
                    "neutral": "..."
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
                    "general": "...",
                    "long": "...",
                    "exec_options_long": [
                        {"text": "...", "description": "...", "type": "defi"}
                    ],
                    "short": "...",
                    "neutral": "..."
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

if __name__ == '__main__':
    logger.info("Application starting up")
    # Initialize the event loop before starting the app
    ensure_event_loop()
    # Run with threaded=True and a higher thread limit to handle multiple concurrent requests
    app.run(debug=True, threaded=True, use_reloader=False)  # Disable reloader to avoid event loop issues