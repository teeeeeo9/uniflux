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
from instruction_templates import INSTRUCTIONS
from typing import Dict, Any
import litellm
# from litellm import LLMExtractionStrategy, LLMConfig, CrawlerRunConfig, CacheMode, BrowserConfig
# from litellm.crawlers import AsyncWebCrawler


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
GEMINI_MODEL_SUMMARIZER = os.getenv('GEMINI_MODEL_SUMMARIZER', 'gemini-1.5-pro')  # Default to gemini-1.5-pro if not specified
GEMINI_MODEL_INSIGHTS = os.getenv('GEMINI_MODEL_INSIGHTS', 'gemini-1.5-pro')  # Default to gemini-1.5-pro if not specified
GEMINI_MODEL_METATOPICS = os.getenv('GEMINI_MODEL_METATOPICS', 'gemini-1.5-flash')  # Default to gemini-1.5-flash if not specified
GEMINI_MODEL_IMPORTANCE = os.getenv('GEMINI_MODEL_IMPORTANCE', 'gemini-1.5-flash')  # Default to gemini-1.5-flash if not specified

SONAR_MODEL_INSIGHTS = os.getenv('SONAR_MODEL_INSIGHTS', 'perplexity/sonar-reasoning-pro')  # Default to sonar-reasoning-pro if not specified
# Ensure we use the right environment variable for Perplexity API
PERPLEXITYAI_API_KEY = os.getenv('PERPLEXITYAI_API_KEY')

logger.info("Gemini API configured")
logger.info(f"Using models: Summarizer={GEMINI_MODEL_SUMMARIZER}, Insights={GEMINI_MODEL_INSIGHTS}, Metatopics={GEMINI_MODEL_METATOPICS}, Importance={GEMINI_MODEL_IMPORTANCE}")
logger.info(f"Sonar model available: {SONAR_MODEL_INSIGHTS}")
logger.info(f"Perplexity API Key available: {PERPLEXITYAI_API_KEY is not None}")

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
            logger.debug(f"Filtering by {len(sources)} sources")
            placeholders = ','.join(['?' for _ in sources])
            query += f" AND source_url IN ({placeholders})"
            params.extend(sources)
            
        logger.debug(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)
        
        messages = []
        logger.debug("Starting to fetch and process rows")
        for row in cursor.fetchall():
            message = dict(row)
            logger.debug(f"Processing message ID: {message['id']}")
            
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
                logger.debug(f"No summarized_links_content for message {message['id']}")
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

def batch_messages(messages, batch_size=300):
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
    
    # Check if the event loop is closed and create a new one if needed
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug("Event loop was closed, creating a new one")
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        logger.debug("No event loop found, creating a new one")
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    try:
        # Create a fresh client for this request to avoid connection issues
        request_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        logger.debug("Created Gemini model instance")
        
        if prompt_type == "initial":
            logger.debug("Using initial summarization prompt")
            prompt = INSTRUCTIONS["initial_summarization"].format(text_content=text_content)
        else:  # incremental
            logger.debug("Using incremental summarization prompt")
            prompt = INSTRUCTIONS["incremental_summarization"].format(
                current_summary=text_content['current_summary'],
                new_messages=text_content['new_messages']
            )
        
        logger.debug(f"Sending request to Gemini API using model: {GEMINI_MODEL_SUMMARIZER}")
        # Use the request-specific client instead of the global one
        response = await request_client.aio.models.generate_content(
            model=GEMINI_MODEL_SUMMARIZER, contents=prompt
        )
        logger.debug("Received response from Gemini API")
        
        # Extract JSON from response
        response_text = response.text
        logger.debug(f"Response text length: {len(response_text)}")
        
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
            logger.debug(f"Attempting to parse JSON response of length: {len(json_str)}")
            parsed_json = json.loads(json_str)
            logger.info("Successfully parsed JSON response")
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            # Fallback: return as text
            logger.debug("Returning error object as fallback")
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
    logger.info(f"[PROCESS_START] process_and_aggregate_news for period: {period}, sources: {sources}")
    
    try:
        # Get messages from the database
        logger.info(f"[PROCESS_STEP] Fetching messages from database for period: {period}")
        messages = get_messages(period, sources)
        
        if not messages:
            logger.warning(f"[PROCESS_EMPTY] No messages found for period: {period}, sources: {sources}")
            return []
        
        # Process in batches
        logger.info(f"[PROCESS_STEP] Processing {len(messages)} messages in batches")
        batches = list(batch_messages(messages))
        logger.info(f"[PROCESS_INFO] Created {len(batches)} batches")
        current_summary = None
        
        for i, batch in enumerate(batches):
            logger.info(f"[PROCESS_BATCH] Processing batch {i+1}/{len(batches)} with {len(batch)} messages")
            
            try:
                # Combine message content for each message in the batch
                logger.debug(f"[PROCESS_DETAIL] Combining message content for batch {i+1}")
                combined_texts = []
                for message in batch:
                    message_text = combine_message_content(message)
                    combined_texts.append(f"Message ID: {message['id']}\n{message_text}")
                    
                batch_text = "\n\n===== NEXT MESSAGE =====\n\n".join(combined_texts)
                logger.debug(f"[PROCESS_DETAIL] Combined text length: {len(batch_text)} characters")
                
                if i == 0:
                    # Initial summarization
                    logger.info(f"[PROCESS_API_CALL] Performing initial summarization via Gemini API")
                    current_summary = await summarize_with_gemini(batch_text, "initial")
                    logger.info(f"[PROCESS_API_RESULT] Completed initial summarization")
                else:
                    # Incremental summarization
                    logger.info(f"[PROCESS_API_CALL] Performing incremental summarization for batch {i+1} via Gemini API")
                    text_content = {
                        'current_summary': json.dumps(current_summary, indent=2),
                        'new_messages': batch_text
                    }
                    current_summary = await summarize_with_gemini(text_content, "incremental")
                    logger.info(f"[PROCESS_API_RESULT] Completed incremental summarization for batch {i+1}")
            
            except Exception as e:
                logger.error(f"[PROCESS_ERROR] Error processing batch {i+1}: {e}")
                logger.error(traceback.format_exc())
                # Continue with next batch if one fails
                continue
        
        # Format the final output
        logger.info(f"[PROCESS_FINAL] Finalizing summary data")
        if isinstance(current_summary, list):
            # Already in the correct format
            logger.info(f"[PROCESS_COMPLETE] Generated {len(current_summary)} topic summaries")
            logger.debug(f"[PROCESS_DETAIL] Topics: {[t.get('topic', 'Unknown') for t in current_summary]}")
            return current_summary
        elif isinstance(current_summary, dict) and "error" in current_summary:
            # Error occurred
            logger.error(f"[PROCESS_ERROR] Error in summarization: {current_summary['error']}")
            return []
        else:
            # Unexpected format
            logger.warning(f"[PROCESS_WARNING] Unexpected summary format: {type(current_summary)}")
            logger.debug(f"[PROCESS_DETAIL] Summary content: {str(current_summary)[:200]}...")
            return []
    
    except Exception as e:
        logger.error(f"[PROCESS_ERROR] Error in process_and_aggregate_news: {e}")
        logger.error(traceback.format_exc())
        return []

async def generate_insights(summary_data, use_sonar=True):
    """
    Generate actionable financial insights based on summarized news data
    
    Args:
        summary_data: List of summarized topics with details
        use_sonar: Boolean flag to use Sonar instead of Gemini (default: True)
        
    Returns:
        List of topics with added insights
    """
    model_type = "Sonar" if use_sonar else "Gemini"
    logger.info(f"[INSIGHTS_START] Generating insights for {len(summary_data)} topics using {model_type}")
    
    # Ensure we have a valid event loop at the start
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug("[INSIGHTS_LOOP] Event loop was closed, creating a new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        logger.debug("[INSIGHTS_LOOP] No event loop found, creating a new one")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    insights_prompt_template = INSTRUCTIONS["financial_insights"]
    enhanced_summaries = []
    
    for i, topic in enumerate(summary_data):
        try:
            topic_name = topic.get('topic', 'Unknown')
            logger.info(f"[INSIGHTS_TOPIC_{i+1}] Generating insights for topic: {topic_name} using {model_type}")
            
            # Format the summary for the prompt
            topic_summary = f"Topic: {topic_name}\n"
            topic_summary += f"Summary: {topic.get('summary', '')}\n"
            topic_summary += f"Importance: {topic.get('importance', 0)}/10\n"
            
            prompt = insights_prompt_template.format(summary=topic_summary)
            logger.debug(f"[INSIGHTS_PROMPT_{i+1}] Created prompt with length: {len(prompt)}")
            
            response_text = ""
            if use_sonar:
                # Use Sonar with litellm
                try:
                    logger.debug(f"[INSIGHTS_SONAR_{i+1}] Creating Sonar client with litellm")
                    
                    # Prepare messages format for Sonar
                    messages = [{"role": "user", "content": prompt}]
                    
                    logger.debug(f"[INSIGHTS_API_CALL_{i+1}] Calling Sonar API with model: {SONAR_MODEL_INSIGHTS}")
                    response = await litellm.acompletion(
                        model=SONAR_MODEL_INSIGHTS,
                        messages=messages
                    )
                    
                    logger.debug(f"[INSIGHTS_API_RESPONSE_{i+1}] Received response from Sonar API")
                    response_text = response.choices[0].message.content
                except Exception as sonar_error:
                    logger.error(f"[INSIGHTS_SONAR_ERROR_{i+1}] Failed to use Sonar API: {sonar_error}")
                    logger.error(traceback.format_exc())
                    # Fall back to Gemini if Sonar fails
                    logger.warning(f"[INSIGHTS_FALLBACK_{i+1}] Falling back to Gemini due to Sonar error")
                    use_sonar = False
            
            if not use_sonar:
                # Use Gemini as before
                try:
                    request_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
                    logger.debug(f"[INSIGHTS_CLIENT_{i+1}] Created fresh Gemini client")
                
                    # Use Gemini to generate insights with the fresh client
                    logger.debug(f"[INSIGHTS_API_CALL_{i+1}] Calling Gemini API with model: {GEMINI_MODEL_INSIGHTS}")
                    response = await request_client.aio.models.generate_content(
                        model=GEMINI_MODEL_INSIGHTS, contents=prompt
                    )
                    logger.debug(f"[INSIGHTS_API_RESPONSE_{i+1}] Received response from Gemini API")
                    
                    # Extract text from response
                    response_text = response.text
                except Exception as client_error:
                    logger.error(f"[INSIGHTS_CLIENT_ERROR_{i+1}] Failed to use Gemini API: {client_error}")
                    logger.error(traceback.format_exc())
                    # Add the topic without insights
                    logger.debug(f"[INSIGHTS_FALLBACK_{i+1}] Adding topic without insights due to API error")
                    enhanced_summaries.append(topic)
                    continue
            
            logger.debug(f"[INSIGHTS_PARSE_{i+1}] Response text length: {len(response_text)}")
            
            # Find JSON content (may be wrapped in markdown code blocks)
            if "```json" in response_text:
                logger.debug(f"[INSIGHTS_PARSE_{i+1}] Found JSON content in markdown json code block")
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                logger.debug(f"[INSIGHTS_PARSE_{i+1}] Found JSON content in markdown code block")
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                logger.debug(f"[INSIGHTS_PARSE_{i+1}] No markdown code blocks found, using raw response")
                json_str = response_text
                
            # Parse the JSON
            try:
                logger.debug(f"[INSIGHTS_PARSE_{i+1}] Attempting to parse JSON of length: {len(json_str)}")
                insights = json.loads(json_str)
                logger.info(f"[INSIGHTS_SUCCESS_{i+1}] Successfully parsed insights for topic: {topic_name}")
                
                # Validate expected fields in new JSON structure
                expected_fields = [
                    "analysis_summary", "stance", "rationale_long", "rationale_short", 
                    "rationale_neutral", "risks_and_watchouts", "key_questions_for_user", 
                    "suggested_instruments_long", "suggested_instruments_short", "useful_resources"
                ]
                
                missing_fields = [field for field in expected_fields if field not in insights]
                if missing_fields:
                    logger.warning(f"[INSIGHTS_VALIDATION_{i+1}] Missing expected fields in response: {missing_fields}")
                    # Add default empty values for missing fields to ensure consistency
                    for field in missing_fields:
                        if field in ["risks_and_watchouts", "key_questions_for_user", 
                                    "suggested_instruments_long", "suggested_instruments_short", 
                                    "useful_resources"]:
                            insights[field] = []
                        else:
                            insights[field] = ""
                
                # Log the formatted JSON insights
                formatted_insights = json.dumps(insights, indent=2)
                logger.info(f"[INSIGHTS_JSON_{i+1}] Generated insights:\n{formatted_insights}")
                
                # Add insights to the topic
                enhanced_topic = topic.copy()
                enhanced_topic["insights"] = insights
                logger.debug(f"[INSIGHTS_ADDED_{i+1}] Added insights to topic: {topic_name}")
                
                # Log insight types
                insight_keys = list(insights.keys())
                logger.debug(f"[INSIGHTS_DETAIL_{i+1}] Insight categories: {insight_keys}")
                
                enhanced_summaries.append(enhanced_topic)
                
            except json.JSONDecodeError as e:
                logger.error(f"[INSIGHTS_ERROR_{i+1}] Failed to parse response as JSON: {e}")
                logger.error(f"[INSIGHTS_ERROR_{i+1}] Raw response: {response_text}")
                # Add the topic without insights
                logger.debug(f"[INSIGHTS_FALLBACK_{i+1}] Adding topic without insights due to JSON parsing error")
                enhanced_summaries.append(topic)
                
        except Exception as e:
            logger.error(f"[INSIGHTS_ERROR_{i+1}] Error generating insights for topic {i}: {e}")
            logger.error(traceback.format_exc())
            # Include the topic without insights if there's an error
            logger.debug(f"[INSIGHTS_FALLBACK_{i+1}] Adding topic without insights due to general error")
            enhanced_summaries.append(topic)
    
    logger.info(f"[INSIGHTS_COMPLETE] Completed generating insights for {len(summary_data)} topics using {model_type}")
    return enhanced_summaries

async def classify_topics_to_metatopics(topics):
    """
    Classifies each topic into a broader metatopic category.
    
    Args:
        topics: List of topic dictionaries from summarization
        
    Returns:
        The same list of topics with a 'metatopic' field added to each
    """
    logger.info(f"[METATOPICS_START] Starting metatopic classification for {len(topics)} topics using model: {GEMINI_MODEL_METATOPICS}")
    
    if not topics:
        logger.warning("[METATOPICS_EMPTY] No topics to classify")
        return topics
    
    # Prepare the content for the prompt
    logger.debug("[METATOPICS_PREP] Preparing topics data for classification")
    topics_text = []
    for i, topic in enumerate(topics):
        topic_name = topic.get('topic', 'Unknown')
        logger.debug(f"[METATOPICS_PREP] Processing topic {i+1}: {topic_name}")
        topics_text.append(f"Topic {i+1}: {topic_name}\nSummary: {topic.get('summary', '')}")
    
    topics_content = "\n\n".join(topics_text)
    logger.debug(f"[METATOPICS_PREP] Prepared content with {len(topics_content)} characters")
    
    try:
        # Create a fresh client for this request to avoid connection issues
        logger.debug("[METATOPICS_CLIENT] Creating fresh Gemini client")
        request_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        prompt = INSTRUCTIONS.get("metatopic_classification", "").format(topics=topics_content)
        logger.debug(f"[METATOPICS_PROMPT] Created prompt with {len(prompt)} characters")
        
        # Log API call
        logger.info(f"[METATOPICS_API_CALL] Sending classification request to Gemini model: {GEMINI_MODEL_METATOPICS}")
        response = await request_client.aio.models.generate_content(
            model=GEMINI_MODEL_METATOPICS, contents=prompt
        )
        logger.info("[METATOPICS_API_RESULT] Received response from Gemini API for metatopic classification")
        
        # Extract JSON from response
        response_text = response.text
        logger.debug(f"[METATOPICS_PARSE] Parsing response text with {len(response_text)} characters")
        
        # Find JSON content (may be wrapped in markdown code blocks)
        json_str = ""
        if "```json" in response_text:
            logger.debug("[METATOPICS_PARSE] Found JSON content in markdown json code block")
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            logger.debug("[METATOPICS_PARSE] Found JSON content in markdown code block")
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            logger.debug("[METATOPICS_PARSE] No markdown code blocks found, using raw response")
            json_str = response_text
            
        # Parse the JSON
        try:
            logger.debug(f"[METATOPICS_PARSE] Attempting to parse JSON string of length {len(json_str)}")
            metatopics_data = json.loads(json_str)
            logger.info("[METATOPICS_PARSE] Successfully parsed metatopic classification response")
            
            # Apply metatopics to the original topics list
            logger.debug(f"[METATOPICS_APPLY] Applying metatopics data to {len(topics)} topics")
            if isinstance(metatopics_data, list) and len(metatopics_data) == len(topics):
                for i, metatopic_info in enumerate(metatopics_data):
                    if isinstance(metatopic_info, dict) and 'metatopic' in metatopic_info:
                        topics[i]['metatopic'] = metatopic_info['metatopic']
                        logger.debug(f"[METATOPICS_APPLY] Topic {i+1}: assigned metatopic '{metatopic_info['metatopic']}'")
                    else:
                        logger.warning(f"[METATOPICS_WARNING] Unexpected format for metatopic at index {i}")
                        topics[i]['metatopic'] = "Other"
                        logger.debug(f"[METATOPICS_APPLY] Topic {i+1}: assigned default metatopic 'Other'")
                logger.info(f"[METATOPICS_COMPLETE] Successfully applied metatopics to {len(topics)} topics")
                logger.debug(f"[METATOPICS_SUMMARY] Metatopic distribution: {count_metatopics(topics)}")
            else:
                logger.warning(f"[METATOPICS_WARNING] Unexpected metatopics response format: length mismatch or invalid structure")
                # Apply a default metatopic if the response format doesn't match
                for i, topic in enumerate(topics):
                    topic['metatopic'] = "Other"
                    logger.debug(f"[METATOPICS_APPLY] Topic {i+1}: assigned default metatopic 'Other' due to format mismatch")
                logger.info("[METATOPICS_FALLBACK] Applied default 'Other' metatopic to all topics")
                
            return topics
            
        except json.JSONDecodeError as e:
            logger.error(f"[METATOPICS_ERROR] Failed to parse Gemini response as JSON: {e}")
            logger.error(f"[METATOPICS_ERROR] Raw response: {response_text[:500]}...")
            # Return original topics without metatopics in case of error
            for i, topic in enumerate(topics):
                topic['metatopic'] = "Other"
                logger.debug(f"[METATOPICS_APPLY] Topic {i+1}: assigned default metatopic 'Other' due to JSON parse error")
            logger.info("[METATOPICS_FALLBACK] Applied default 'Other' metatopic to all topics due to JSON parse error")
            return topics
            
    except Exception as e:
        logger.error(f"[METATOPICS_ERROR] Error in metatopic classification: {e}")
        logger.error(traceback.format_exc())
        # Return original topics without metatopics in case of error
        for i, topic in enumerate(topics):
            topic['metatopic'] = "Other"
            logger.debug(f"[METATOPICS_APPLY] Topic {i+1}: assigned default metatopic 'Other' due to exception")
        logger.info("[METATOPICS_FALLBACK] Applied default 'Other' metatopic to all topics due to exception")
        return topics

def count_metatopics(topics):
    """Count the distribution of metatopics for logging purposes"""
    counts = {}
    for topic in topics:
        metatopic = topic.get('metatopic', 'Unknown')
        counts[metatopic] = counts.get(metatopic, 0) + 1
    return counts

async def rate_topic_importance(topics):
    """
    Rates the importance of each topic on a scale from 1 to 10.
    
    Args:
        topics: List of topic dictionaries from summarization
        
    Returns:
        The same list of topics with an 'importance' field added to each
    """
    logger.info(f"[IMPORTANCE_START] Starting importance rating for {len(topics)} topics using model: {GEMINI_MODEL_IMPORTANCE}")
    
    if not topics:
        logger.warning("[IMPORTANCE_EMPTY] No topics to rate")
        return topics
    
    # Prepare the content for the prompt
    logger.debug("[IMPORTANCE_PREP] Preparing topics data for importance rating")
    topics_text = []
    for i, topic in enumerate(topics):
        topic_name = topic.get('topic', 'Unknown')
        logger.debug(f"[IMPORTANCE_PREP] Processing topic {i+1}: {topic_name}")
        topics_text.append(f"Topic {i+1}: {topic_name}\nSummary: {topic.get('summary', '')}")
    
    topics_content = "\n\n".join(topics_text)
    logger.debug(f"[IMPORTANCE_PREP] Prepared content with {len(topics_content)} characters")
    
    try:
        # Create a fresh client for this request to avoid connection issues
        logger.debug("[IMPORTANCE_CLIENT] Creating fresh Gemini client")
        request_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        prompt = INSTRUCTIONS.get("importance_rating", "").format(topics=topics_content)
        logger.debug(f"[IMPORTANCE_PROMPT] Created prompt with {len(prompt)} characters")
        
        # Log API call
        logger.info(f"[IMPORTANCE_API_CALL] Sending importance rating request to Gemini model: {GEMINI_MODEL_IMPORTANCE}")
        response = await request_client.aio.models.generate_content(
            model=GEMINI_MODEL_IMPORTANCE, contents=prompt
        )
        logger.info("[IMPORTANCE_API_RESULT] Received response from Gemini API for importance rating")
        
        # Extract JSON from response
        response_text = response.text
        logger.debug(f"[IMPORTANCE_PARSE] Parsing response text with {len(response_text)} characters")
        
        # Find JSON content (may be wrapped in markdown code blocks)
        json_str = ""
        if "```json" in response_text:
            logger.debug("[IMPORTANCE_PARSE] Found JSON content in markdown json code block")
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            logger.debug("[IMPORTANCE_PARSE] Found JSON content in markdown code block")
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            logger.debug("[IMPORTANCE_PARSE] No markdown code blocks found, using raw response")
            json_str = response_text
            
        # Parse the JSON
        try:
            logger.debug(f"[IMPORTANCE_PARSE] Attempting to parse JSON string of length {len(json_str)}")
            importance_data = json.loads(json_str)
            logger.info("[IMPORTANCE_PARSE] Successfully parsed importance rating response")
            
            # Apply importance ratings to the original topics list
            logger.debug(f"[IMPORTANCE_APPLY] Applying importance data to {len(topics)} topics")
            if isinstance(importance_data, list) and len(importance_data) == len(topics):
                importance_values = []
                for i, importance_info in enumerate(importance_data):
                    if isinstance(importance_info, dict) and 'importance' in importance_info:
                        importance_value = importance_info['importance']
                        topics[i]['importance'] = importance_value
                        importance_values.append(importance_value)
                        logger.debug(f"[IMPORTANCE_APPLY] Topic {i+1}: assigned importance '{importance_value}'")
                    else:
                        logger.warning(f"[IMPORTANCE_WARNING] Unexpected format for importance at index {i}")
                        topics[i]['importance'] = 5  # Default mid-range importance
                        importance_values.append(5)
                        logger.debug(f"[IMPORTANCE_APPLY] Topic {i+1}: assigned default importance 5")
                        
                # Log importance distribution
                if importance_values:
                    avg_importance = sum(importance_values) / len(importance_values)
                    logger.info(f"[IMPORTANCE_STATS] Average importance: {avg_importance:.2f}, Min: {min(importance_values)}, Max: {max(importance_values)}")
                
                logger.info(f"[IMPORTANCE_COMPLETE] Successfully applied importance ratings to {len(topics)} topics")
            else:
                logger.warning(f"[IMPORTANCE_WARNING] Unexpected importance response format: length mismatch or invalid structure")
                # Apply a default importance if the response format doesn't match
                for i, topic in enumerate(topics):
                    topic['importance'] = 5
                    logger.debug(f"[IMPORTANCE_APPLY] Topic {i+1}: assigned default importance 5 due to format mismatch")
                logger.info("[IMPORTANCE_FALLBACK] Applied default importance rating of 5 to all topics")
                
            return topics
            
        except json.JSONDecodeError as e:
            logger.error(f"[IMPORTANCE_ERROR] Failed to parse Gemini response as JSON: {e}")
            logger.error(f"[IMPORTANCE_ERROR] Raw response: {response_text[:500]}...")
            # Return original topics with default importance in case of error
            for i, topic in enumerate(topics):
                topic['importance'] = 5
                logger.debug(f"[IMPORTANCE_APPLY] Topic {i+1}: assigned default importance 5 due to JSON parse error")
            logger.info("[IMPORTANCE_FALLBACK] Applied default importance rating of 5 to all topics due to JSON parse error")
            return topics
            
    except Exception as e:
        logger.error(f"[IMPORTANCE_ERROR] Error in importance rating: {e}")
        logger.error(traceback.format_exc())
        # Return original topics with default importance in case of error
        for i, topic in enumerate(topics):
            topic['importance'] = 5
            logger.debug(f"[IMPORTANCE_APPLY] Topic {i+1}: assigned default importance 5 due to exception")
        logger.info("[IMPORTANCE_FALLBACK] Applied default importance rating of 5 to all topics due to exception")
        return topics

async def main(period='1d', sources=None, include_insights=False, use_sonar_for_insights=True):
    """Main function to run the summarizer"""
    logger.info(f"[MAIN_START] Starting main function with period={period}, sources={sources}, include_insights={include_insights}, use_sonar={use_sonar_for_insights}")
    
    try:
        # Step 1: Get the initial topic summaries
        logger.info(f"[MAIN_STEP1] Starting topic summarization")
        result = await process_and_aggregate_news(period, sources)
        
        if not result:
            logger.warning("[MAIN_EMPTY] No results generated from summarization")
            return []
        else:
            logger.info(f"[MAIN_STEP1_COMPLETE] Generated {len(result)} topic summaries")
            
            # Step 2: Enhance with metatopics
            logger.info("[MAIN_STEP2] Starting metatopic classification")
            result = await classify_topics_to_metatopics(result)
            logger.info(f"[MAIN_STEP2_COMPLETE] Added metatopics to {len(result)} topics")
            logger.debug(f"[MAIN_STEP2_DETAIL] Metatopic distribution: {count_metatopics(result)}")
            
            # Step 3: Add importance ratings
            logger.info("[MAIN_STEP3] Starting importance rating")
            result = await rate_topic_importance(result)
            logger.info(f"[MAIN_STEP3_COMPLETE] Added importance ratings to {len(result)} topics")
            
            # Log importance distribution
            if result:
                importance_values = [topic.get('importance', 0) for topic in result]
                avg_importance = sum(importance_values) / len(importance_values) if importance_values else 0
                logger.debug(f"[MAIN_STEP3_DETAIL] Importance stats: Avg={avg_importance:.2f}, Min={min(importance_values) if importance_values else 0}, Max={max(importance_values) if importance_values else 0}")
             
            # Step 4: Generate insights if requested
            if include_insights:
                logger.info(f"[MAIN_STEP4] Starting insights generation using {'Sonar' if use_sonar_for_insights else 'Gemini'}")
                result = await generate_insights(result, use_sonar=use_sonar_for_insights)
                logger.info(f"[MAIN_STEP4_COMPLETE] Added insights to {len(result)} topics")
                
                # Log insight completeness
                topics_with_insights = sum(1 for topic in result if 'insights' in topic and topic['insights'])
                logger.debug(f"[MAIN_STEP4_DETAIL] Topics with insights: {topics_with_insights}/{len(result)}")
            
        logger.info("[MAIN_COMPLETE] Processing completed successfully")
        logger.debug(f"[MAIN_RESULT] Returning {len(result)} topics")
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        logger.error(f"[MAIN_ERROR] Error in main function: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    # Parse command line arguments
    logger.info("[SCRIPT_START] Starting data_summarizer.py")
    
    try:
        logger.debug("[SCRIPT_EXEC] Parsing command line arguments")
        import argparse
        
        parser = argparse.ArgumentParser(description='Summarize news from various sources')
        parser.add_argument('--period', type=str, default='1d', help='Time period (e.g., 1d, 2d, 1w)')
        parser.add_argument('--sources', type=str, nargs='*', help='List of source URLs to filter by')
        parser.add_argument('--include-insights', action='store_true', help='Generate insights for the topics')
        parser.add_argument('--use-sonar', action='store_true', help='Use Sonar model for insights instead of Gemini')
        
        args = parser.parse_args()
        
        asyncio.run(main(
            period=args.period, 
            sources=args.sources, 
            include_insights=args.include_insights,
            use_sonar_for_insights=args.use_sonar
        ))
        logger.info("[SCRIPT_COMPLETE] data_summarizer.py execution completed")
    except Exception as e:
        logger.error(f"[SCRIPT_ERROR] Unhandled exception in data_summarizer.py: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

