import sqlite3
import json
import asyncio
import logging
import sys
from config import DATABASE, LOG_FILE

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

def get_db_connection():
    """Create a connection to the SQLite database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

async def process_and_aggregate_news(messages_history):
    """
    Processes the raw message history to aggregate and suggest summaries.

    Args:
        messages_history: A list of dictionaries, where each dictionary represents a message
                          and includes 'internal_id', 'telegram_id', 'channel_url', and 'text'.
                          Example:
                          [
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

    Returns:
        A dictionary where keys are summary topics and values are lists of internal message IDs
        relevant to that topic.
        Example:
        {
            "DeFi Protocol Launch": [1, 2, 5],
            "Market Analysis": [3, 7]
        }
    """
    # Mock summarization and aggregation logic
    # In a real implementation, you would use NLP techniques here.

    topics = {}
    for message in messages_history:
        text = message['text'].lower()
        internal_id = message['internal_id']

        if "defi protocol launch" in text or "new defi" in text:
            if "DeFi Protocol Launch" not in topics:
                topics["DeFi Protocol Launch"] = []
            topics["DeFi Protocol Launch"].append(internal_id)

        if "market analysis" in text or "price prediction" in text:
            if "Market Analysis" not in topics:
                topics["Market Analysis"] = []
            topics["Market Analysis"].append(internal_id)

        if "web3 development" in text or "blockchain update" in text:
            if "Web3 Development" not in topics:
                topics["Web3 Development"] = []
            topics["Web3 Development"].append(internal_id)

    return topics

