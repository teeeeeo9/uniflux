import sqlite3
import json
import asyncio
import logging
import sys
import datetime
from datetime import timedelta
# import google.generativeai as genai
from google import genai
from google.genai import types
import os
import traceback
from dotenv import load_dotenv
from config import DATABASE, LOG_FILE


# Load environment variables
load_dotenv()

# Configure module-specific logger
logger = logging.getLogger('data_summarizer')
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

logger.info("Data summarizer module initializing")

# Configure Gemini API
# genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

logger.info("Gemini API configured")

def get_db_connection():
    """Create a connection to the SQLite database"""
    logger.debug(f"Opening database connection to {DATABASE}")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    logger.debug("Database connection established")
    return conn

def get_time_range(period):
    """
    Convert the time period string to a start and end datetime
    
    Args:
        period: String like '1d', '2d', '1w'
        
    Returns:
        tuple: (start_date, end_date) as datetime objects
    """
    now = datetime.datetime.now()
    
    if period.endswith('d'):
        days = int(period[:-1])
        start_date = now - timedelta(days=days)
    elif period.endswith('w'):
        weeks = int(period[:-1])
        start_date = now - timedelta(weeks=weeks)
    else:
        # Default to 1 day if format is not recognized
        start_date = now - timedelta(days=1)
        
    return start_date, now

def get_messages(period, sources=None):
    """
    Fetch messages from the database based on period and sources
    
    Args:
        period: Time period string (e.g., '1d', '2d', '1w')
        sources: List of source URLs to filter by or None for all sources
        
    Returns:
        List of message dictionaries
    """
    logger.info(f"Retrieving messages for period: {period}, sources: {sources}")
    start_date, end_date = get_time_range(period)
    logger.debug(f"Time range: {start_date.isoformat()} to {end_date.isoformat()}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, source_url, source_type, channel_id, message_id, 
               date, data, summarized_links_content
        FROM messages
        WHERE date BETWEEN ? AND ?
        """
        
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if sources:
            placeholders = ','.join(['?' for _ in sources])
            query += f" AND source_url IN ({placeholders})"
            params.extend(sources)
            
        logger.debug(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)
        
        messages = []
        for row in cursor.fetchall():
            message = dict(row)
            
            # Parse the summarized links content if it exists
            if message['summarized_links_content']:
                try:
                    message['summarized_links_content'] = json.loads(
                        message['summarized_links_content']
                    )
                    logger.debug(f"Parsed summarized_links_content for message {message['id']}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse summarized_links_content for message {message['id']}")
                    message['summarized_links_content'] = {}
            else:
                message['summarized_links_content'] = {}
                
            messages.append(message)
            
        logger.info(f"Retrieved {len(messages)} messages from database")
        return messages
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            logger.debug("Database connection closed")

def combine_message_content(message):
    """
    Combine the message text with any summarized link content
    
    Args:
        message: Message dictionary from database
        
    Returns:
        str: Combined text content
    """
    combined_text = message['data']
    
    # Add summarized link content if available
    if message['summarized_links_content']:
        for url, summary in message['summarized_links_content'].items():
            if summary and summary != "Failed to extract content":
                combined_text += f"\n\nLink summary ({url}):\n{summary}"
                
    return combined_text

def batch_messages(messages, batch_size=25):
    """Split messages into batches of specified size"""
    for i in range(0, len(messages), batch_size):
        yield messages[i:i + batch_size]

async def summarize_with_gemini(text_content, prompt_type="initial"):
    """
    Summarize text content using Gemini API
    
    Args:
        text_content: Text to summarize
        prompt_type: Type of prompt to use ('initial' or 'incremental')
        
    Returns:
        str: Summary generated by Gemini
    """
    logger.info(f"Summarizing content with Gemini using prompt type: {prompt_type}")
    
    try:
        # model = genai.GenerativeModel('gemini-pro')
        logger.debug("Created Gemini model instance")
        
        if prompt_type == "initial":
            logger.debug("Using initial summarization prompt")
            prompt = f"""
            Analyze the following crypto news messages and create a summary that:
            1. Identifies key topics/themes
            2. Provides a concise summary for each topic
            3. Assigns an importance score (1-10) to each topic based on potential impact
            
            Format your response as a JSON array with objects containing:
            - "topic": Short name for the topic
            - "summary": Detailed summary
            - "message_ids": List of message IDs related to this topic
            - "importance": Numeric score from 1-10
            
            Here are the messages to analyze:
            
            {text_content}
            """
        else:  # incremental
            logger.debug("Using incremental summarization prompt")
            prompt = f"""
            Here is the current summary of crypto news topics:
            
            {text_content['current_summary']}
            
            Now analyze these additional messages and update the summary:
            
            {text_content['new_messages']}
            
            Keep the same JSON format as before, but merge topics that are related,
            update existing topics with new information, and add new topics as needed.
            """
        
        logger.debug("Sending request to Gemini API")
        # response = await model.generate_content_async(prompt)
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash', contents=prompt
        )
        logger.debug("Received response from Gemini API")
        
        # Extract JSON from response
        response_text = response.text
        
        # Find JSON content (may be wrapped in markdown code blocks)
        if "```json" in response_text:
            logger.debug("Found JSON content in markdown json code block")
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            logger.debug("Found JSON content in markdown code block")
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            logger.debug("No markdown code blocks found, using raw response")
            json_str = response_text
            
        # Parse the JSON
        try:
            parsed_json = json.loads(json_str)
            logger.info("Successfully parsed JSON response")
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            # Fallback: return as text
            return {"error": "Failed to parse response", "raw_response": response_text}
            
    except Exception as e:
        logger.error(f"Error using Gemini API: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

async def process_and_aggregate_news(period, sources=None):
    """
    Processes messages to aggregate and suggest summaries.

    Args:
        period: Time period string (e.g., '1d', '2d', '1w')
        sources: Optional list of source URLs to filter by
        
    Returns:
        A JSON object with topics, summaries, message IDs, and importance scores
    """
    logger.info(f"Starting to process and aggregate news for period: {period}, sources: {sources}")
    
    try:
        # Get messages from the database
        messages = get_messages(period, sources)
        
        if not messages:
            logger.warning("No messages found for the specified period and sources")
            return []
        
        # Process in batches
        logger.info(f"Processing {len(messages)} messages in batches")
        batches = list(batch_messages(messages))
        logger.info(f"Created {len(batches)} batches")
        current_summary = None
        
        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} messages")
            
            try:
                # Combine message content for each message in the batch
                combined_texts = []
                for message in batch:
                    message_text = combine_message_content(message)
                    combined_texts.append(f"Message ID: {message['id']}\n{message_text}")
                    
                batch_text = "\n\n===== NEXT MESSAGE =====\n\n".join(combined_texts)
                
                if i == 0:
                    # Initial summarization
                    logger.info("Performing initial summarization")
                    current_summary = await summarize_with_gemini(batch_text, "initial")
                else:
                    # Incremental summarization
                    logger.info(f"Performing incremental summarization for batch {i+1}")
                    text_content = {
                        'current_summary': json.dumps(current_summary, indent=2),
                        'new_messages': batch_text
                    }
                    current_summary = await summarize_with_gemini(text_content, "incremental")
            
            except Exception as e:
                logger.error(f"Error processing batch {i+1}: {e}")
                logger.error(traceback.format_exc())
                # Continue with next batch if one fails
                continue
        
        # Format the final output
        if isinstance(current_summary, list):
            # Already in the correct format
            logger.info(f"Summarization complete. Generated {len(current_summary)} topic summaries")
            return current_summary
        elif isinstance(current_summary, dict) and "error" in current_summary:
            # Error occurred
            logger.error(f"Error in summarization: {current_summary['error']}")
            return []
        else:
            # Unexpected format
            logger.warning(f"Unexpected summary format: {type(current_summary)}")
            return []
    
    except Exception as e:
        logger.error(f"Error in process_and_aggregate_news: {e}")
        logger.error(traceback.format_exc())
        return []

async def main(period='1d', sources=None):
    """Main function to run the summarizer"""
    logger.info(f"Starting main function with period={period}, sources={sources}")
    
    try:
        result = await process_and_aggregate_news(period, sources)
        
        if not result:
            logger.warning("No results generated from summarization")
        else:
            logger.info(f"Generated {len(result)} topic summaries")
            
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    # Parse command line arguments
    logger.info("Starting data_summarizer.py")
    
    try:
        # import argparse
        
        # parser = argparse.ArgumentParser(description='Summarize news from various sources')
        # parser.add_argument('--period', type=str, default='1d', help='Time period (e.g., 1d, 2d, 1w)')
        # parser.add_argument('--sources', type=str, nargs='*', help='List of source URLs to filter by')
        
        # args = parser.parse_args()
        
        asyncio.run(main())
        logger.info("data_summarizer.py execution completed")
    except Exception as e:
        logger.error(f"Unhandled exception in data_summarizer.py: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

