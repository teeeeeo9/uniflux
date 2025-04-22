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
from data_summarizer import process_and_aggregate_news, generate_insights
import threading
from functools import wraps


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

app = Flask(__name__)
CORS(app)

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
        
        # Populate the sources table with sources from environment variable
        telegram_sources = os.getenv("TELEGRAM_SOURCES", "").split(",")
        cursor = db.cursor()
        try:
            for source in telegram_sources:
                source = source.strip()
                if source:  # Skip empty strings
                    cursor.execute("INSERT OR IGNORE INTO sources (url) VALUES (?)", (source,))
            db.commit()
            logger.info(f'Sources table populated with {len(telegram_sources)} sources from environment')
        except sqlite3.Error as e:
            logger.error(f'Error populating sources table: {e}')
        
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
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@app.route('/process_news', methods=['POST'])
def process_news_api():
    """
    API endpoint to receive message history and return aggregated summaries with message IDs.

    Request Body (JSON):
    {
        "messages_history": [
            {
                "internal_id": 1,
                "telegram_id": 100,
                "channel_url": "https://t.me/channel1",
                "text": "Breaking news: Protocol XYZ launched!",
                "date": "...",
                "links": []
            },
            {
                "internal_id": 2,
                "telegram_id": 101,
                "channel_url": "https://t.me/channel1",
                "text": "More details on Protocol XYZ...",
                "date": "...",
                "links": ["whitepaper_link"]
            },
            ...
        ]
    }

    Response Format (JSON):
    {
        "summaries": {
            "DeFi Protocol Launch": [1, 2, 5],
            "Market Analysis": [3, 7]
        }
    }
    """
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /process_news - IP: {user_ip}")
    logger.info(f"REQUEST [{request_id}] - Headers: {format_log_data(headers)}")
    
    # Log request body
    try:
        data = request.get_json()
        logger.info(f"REQUEST [{request_id}] - Body: {format_log_data(data)}")
    except Exception as e:
        logger.error(f"REQUEST [{request_id}] - Failed to parse JSON body: {str(e)}")
        return jsonify({"error": "Invalid JSON in request body"}), 400
    
    if not data or 'messages_history' not in data or not isinstance(data['messages_history'], list):
        logger.error(f"REQUEST [{request_id}] - Invalid format - Missing or invalid messages_history field")
        return jsonify({"error": "Invalid request. 'messages_history' list is required in the request body."}), 400

    messages_history = data['messages_history']
    
    # Extract message details for logging
    message_count = len(messages_history)
    message_ids = [msg.get('internal_id', 'unknown') for msg in messages_history]

    # Extract the sources for tracking
    source_urls = set()
    for message in messages_history:
        if 'channel_url' in message and message['channel_url']:
            source_urls.add(message['channel_url'])
    
    # Log detailed request information
    logger.info(f"PROCESS [{request_id}] - Processing {message_count} messages from {len(source_urls)} sources")
    logger.info(f"PROCESS [{request_id}] - Message IDs sample: {message_ids}")
    logger.info(f"PROCESS [{request_id}] - Sources: {list(source_urls)}")
    
    try:
        # Call the processing function synchronously
        logger.info(f"PROCESS [{request_id}] - Calling process_and_aggregate_news with {message_count} messages")
        processed_data = run_async(process_and_aggregate_news)(messages_history)
        
        # Log detailed result information
        topic_count = len(processed_data)
        topics_summary = {}
        for topic, msg_ids in processed_data.items():
            topics_summary[topic] = {
                "count": len(msg_ids),
                "sample_ids": msg_ids
            }
        
        logger.info(f"RESPONSE [{request_id}] - Generated {topic_count} topics")
        logger.info(f"RESPONSE [{request_id}] - Topics summary: {format_log_data(topics_summary)}")
        
        # Create and log the response
        response = {"summaries": processed_data}
        logger.info(f"RESPONSE [{request_id}] - Full response: {format_log_data(response)}")
        
        return jsonify(response), 200
    
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"ERROR [{request_id}] - Failed to process request: {error_details['error_type']}: {error_details['error_message']}")
        logger.error(f"ERROR [{request_id}] - Traceback: {error_details['traceback']}")
        
        return jsonify({"error": str(e)}), 500

@app.route('/insights', methods=['GET'])
def get_insights():
    """
    API endpoint to generate summaries and actionable insights based on time period and sources.
    
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
    # Log request details
    user_ip = request.remote_addr
    headers = dict(request.headers)
    request_id = headers.get('X-Request-ID', 'unknown')
    
    logger.info(f"REQUEST [{request_id}] - /insights - IP: {user_ip}")
    
    # Get query parameters
    period = request.args.get('period', '1d')
    sources_str = request.args.get('sources', '')
    sources = [s.strip() for s in sources_str.split(',')] if sources_str else None
    
    logger.info(f"REQUEST [{request_id}] - Parameters: period={period}, sources={sources}")
    
    try:
        # Generate summaries
        logger.info(f"PROCESS [{request_id}] - Calling process_and_aggregate_news with period={period}, sources={sources}")
        summaries = run_async(process_and_aggregate_news)(period, sources)
        
        if not summaries:
            logger.warning(f"PROCESS [{request_id}] - No summaries generated")
            return jsonify({"topics": []}), 200
        
        # Generate insights for each topic
        logger.info(f"PROCESS [{request_id}] - Generating insights for {len(summaries)} topics")
        topics_with_insights = run_async(generate_insights)(summaries)
        
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

if __name__ == '__main__':
    logger.info("Application starting up")
    app.run(debug=True)