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


load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log.log"),
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

DATABASE = 'sources.db'

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

@app.route('/process_news', methods=['POST'])
async def process_news_api():
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
        # Call the processing function
        logger.info(f"PROCESS [{request_id}] - Calling process_and_aggregate_news with {message_count} messages")
        processed_data = await process_and_aggregate_news(messages_history)
        
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

if __name__ == '__main__':
    logger.info("Application starting up")
    app.run(debug=True)