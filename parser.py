import os
import asyncio
import json
import time
import sqlite3
import logging
import sys
import traceback
from pydantic import BaseModel
from typing import Dict, Any, Optional
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from instruction_templates import INSTRUCTIONS, DEFAULT_INSTRUCTION
import litellm

# Custom JSON formatter for logs
def format_json(obj):
    """Format an object as pretty JSON if it's a dict or list, otherwise return as string"""
    if isinstance(obj, (dict, list)):
        return "\n" + json.dumps(obj, indent=2)
    return str(obj)

# Configure logging with full detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
    handlers=[
        logging.FileHandler("log.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("Parser module initializing")

# Database file path
DATABASE = 'sources.db'
logger.info(f"Database path: {DATABASE}")

class Article(BaseModel):
    name: str
    summarized_content: str

def get_db_connection():
    """Create and return a database connection"""
    logger.info(f"Opening database connection to {DATABASE}")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    logger.info("Database connection established")
    return conn

def get_summary_from_db(url: str) -> Dict[str, Any]:
    """
    Check if a URL's summary exists in the database and return it if found
    
    Args:
        url: The URL to look up
        
    Returns:
        A dictionary with the summary content or None if not found
    """
    logger.info(f"Checking if summary for URL exists in database: {url}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT summary_content FROM link_summaries WHERE url = ?", (url,))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Summary for {url} found in database")
            logger.info(f"Full summary content from database: {result['summary_content']}")
            return {"content": result["summary_content"]}
        
        logger.info(f"No summary found in database for {url}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving summary from database: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            logger.info("Closing database connection")
            conn.close()

def save_summary_to_db(url: str, summary_content: str) -> bool:
    """
    Save a URL's summary to the database
    
    Args:
        url: The URL that was parsed
        summary_content: The extracted summary content
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Saving summary to database for URL: {url}")
    # No need to format summary content as JSON as it's already a string
    logger.info(f"Full summary content to save: {summary_content}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert or replace the summary
        cursor.execute(
            "INSERT OR REPLACE INTO link_summaries (url, summary_content, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (url, summary_content)
        )
        
        conn.commit()
        logger.info(f"Summary for {url} successfully saved to database")
        return True
    except Exception as e:
        logger.error(f"Error saving summary to database: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if conn:
            logger.info("Closing database connection")
            conn.close()

async def extract_summary_from_link(url: str, instruction_type: str = DEFAULT_INSTRUCTION, debug_mode: bool = False) -> Dict[str, Any]:
    """
    Extract a summary from a given URL using specified instruction type.
    
    Args:
        url: The URL to extract content from
        instruction_type: The type of instruction to use (default: "summary")
        debug_mode: Whether to enable LiteLLM debug mode
        
    Returns:
        A dictionary containing the extracted content
    """
    logger.info(f"Extracting summary from URL: {url}")
    logger.info(f"Using instruction type: {instruction_type}")
    logger.info(f"Debug mode: {debug_mode}")
    
    # Enable debug mode if requested
    if debug_mode:
        litellm._turn_on_debug()
        logger.info("LiteLLM debug mode enabled")
    
    # Get the appropriate instruction
    if instruction_type not in INSTRUCTIONS:
        logger.warning(f"Instruction type '{instruction_type}' not found. Using default.")
        instruction_text = INSTRUCTIONS[DEFAULT_INSTRUCTION]
    else:
        instruction_text = INSTRUCTIONS[instruction_type]
    
    # Format the instruction with the URL
    instruction_text = instruction_text.format(url)
    logger.info(f"Using instruction: {instruction_text}")

    # 1. Define the LLM extraction strategy - keeping exact same settings
    logger.info("Configuring LLM extraction strategy")
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="gemini/gemini-2.0-flash", api_token=os.getenv('GEMINI_API_KEY')),
        schema=Article.schema_json(), # Or use model_json_schema()
        extraction_type="schema",
        instruction=instruction_text,
        chunk_token_threshold=1000,
        overlap_rate=0.0,
        apply_chunking=True,
        input_format="html",   # or "html", "fit_markdown"
        extra_args={"temperature": 0.0, "max_tokens": 800}
    )

    # 2. Build the crawler config
    logger.info("Configuring crawler run config")
    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS
    )

    # 3. Create a browser config
    logger.info("Configuring browser")
    browser_cfg = BrowserConfig(headless=True)

    try:
        logger.info(f"Starting crawl for URL: {url}")
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            # 4. Crawl the page
            logger.info("Executing crawler run")
            result = await crawler.arun(
                url=url,
                config=crawl_config
            )

            if result.success:
                # 5. Return the extracted content
                logger.info(f"Crawl successful for URL: {url}")
                data = json.loads(result.extracted_content)
                logger.info(f"Extracted content: {format_json(data)}")
                
                # Add the URL to the result for use in the processing function
                if isinstance(data, dict):
                    data["url"] = url
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item["url"] = url
                
                return data
            else:
                logger.error(f"Crawl failed for URL: {url}")
                logger.error(f"Error message: {result.error_message}")
                return {"error": result.error_message}
    except Exception as e:
        logger.error(f"Exception during crawl for URL {url}: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}

def process_extraction_result(result: Any, url: str = None) -> Dict[str, Any]:
    """
    Process the extraction result to extract summarized_content and determine success.
    Handles various result formats including nested JSON arrays and objects.
    Selects the item with the longest summarized_content where error is false.
    Saves the final selected content to the database.
    
    Args:
        result: The extraction result to process
        url: The URL the content was extracted from
        
    Returns:
        A dictionary with:
        - success: 1 if successful, 0 if error
        - content: The extracted content as a string
    """
    logger.info(f"Processing extraction result: {format_json(result)}")
    final_content = ""
    success = 0
    
    try:
        # Handle JSON array format (from schema extraction)
        if isinstance(result, list):
            # Filter items where error is false
            valid_items = [item for item in result 
                          if isinstance(item, dict) 
                          and item.get("error") is False
                          and "summarized_content" in item]
            
            logger.info(f"Found {len(valid_items)} valid items with error=false")
            
            if valid_items:
                # Find the item with the longest summarized_content
                longest_item = max(valid_items, 
                                   key=lambda x: len(x.get("summarized_content", "")) 
                                   if isinstance(x.get("summarized_content"), str) else 0)
                
                final_content = longest_item.get("summarized_content", "")
                # Get the URL from the item if available
                if url is None and "url" in longest_item:
                    url = longest_item["url"]
                    
                logger.info(f"Selected item with longest summarized_content ({len(final_content)} chars)")
                logger.info(f"Selected content: {final_content}")
                success = 1
        
        # Handle dict with summarized_content key
        elif isinstance(result, dict) and not result.get("error", True) and "summarized_content" in result:
            final_content = result["summarized_content"]
            # Get the URL from the dict if available
            if url is None and "url" in result:
                url = result["url"]
                
            if isinstance(final_content, str) and final_content:
                success = 1
        
        # Handle dict with content key (for backward compatibility)
        elif isinstance(result, dict) and "content" in result and isinstance(result["content"], str):
            final_content = result["content"]
            # Get the URL from the dict if available
            if url is None and "url" in result:
                url = result["url"]
                
            if final_content:
                success = 1
        
        # Save the final content to the database if we have content and a URL
        if success == 1 and final_content and url:
            logger.info(f"Saving final processed content to database for URL: {url}")
            save_summary_to_db(url, final_content)
        elif success == 1 and final_content and not url:
            logger.warning("Content was successfully processed but URL is missing - cannot save to database")
        
        # Return the result
        return {"success": success, "content": final_content}
        
    except Exception as e:
        logger.error(f"Error processing extraction result: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": 0, "content": ""}

def extract_summary(url: str, enable_retries: bool = False, debug_mode: bool = False) -> Dict[str, Any]:
    """
    Synchronous wrapper to extract summary from a URL with optional retry logic.
    First checks if the summary exists in the database before attempting to fetch it.
    
    Args:
        url: The URL to extract content from
        enable_retries: Whether to enable retry logic (up to 5 attempts) or just make a single attempt
        debug_mode: Whether to enable LiteLLM debug mode
        
    Returns:
        A dictionary with:
        - success: 1 if successful, 0 if error
        - content: The extracted content as a string
    """
    logger.info(f"Starting extract_summary for URL: {url}")
    logger.info(f"Retry enabled: {enable_retries}, Debug mode: {debug_mode}")
    
    # First, try to get the summary from the database
    db_result = get_summary_from_db(url)
    if db_result:
        logger.info(f"Found existing summary in database for URL: {url}")
        if "content" in db_result and db_result["content"]:
            return {"success": 1, "content": db_result["content"]}
        else:
            logger.warning(f"Database entry for {url} has invalid format")
            return {"success": 0, "content": ""}
    
    # If not in database, proceed with web extraction
    instruction_type = 'summary'
    logger.info(f"No summary in database, proceeding with web extraction using instruction type: {instruction_type}")
    
    # If retries are not enabled, just make a single attempt
    if not enable_retries:
        try:
            logger.info(f"Making single extraction attempt for URL: {url}")
            result = asyncio.run(extract_summary_from_link(url, instruction_type, debug_mode))
            logger.info(f"Extraction completed for URL: {url}")
            logger.info(f"Extraction result: {format_json(result)}")
            
            # Process the result to extract content
            processed_result = process_extraction_result(result, url)
            logger.info(f"Processed result: {format_json(processed_result)}")
            return processed_result
            
        except Exception as e:
            logger.error(f"Exception during extraction for URL {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return {"success": 0, "content": ""}
    
    # With retries enabled, use the retry logic
    max_attempts = 5
    backoff_time = 1  # Initial backoff time in seconds
    
    logger.info(f"Making up to {max_attempts} extraction attempts for URL: {url}")
    
    for attempt in range(max_attempts):
        try:
            logger.info(f"Attempt {attempt+1} of {max_attempts} to extract summary from {url}")
            result = asyncio.run(extract_summary_from_link(url, instruction_type, debug_mode))
            logger.info(f"Extraction result on attempt {attempt+1}: {format_json(result)}")
            
            # Process the result
            processed_result = process_extraction_result(result, url)
            
            # If successful, return the processed result
            if processed_result["success"] == 1 and processed_result["content"]:
                logger.info(f"Successfully extracted content on attempt {attempt+1}")
                return processed_result
                
            # If we got a result but it was not valid, retry if we have attempts left
            if attempt < max_attempts - 1:
                logger.info(f"Invalid result on attempt {attempt+1}, retrying in {backoff_time} seconds")
                time.sleep(backoff_time)
                backoff_time *= 1.5  # Exponential backoff
                
        except Exception as e:
            logger.error(f"Exception on attempt {attempt+1}: {str(e)}")
            logger.error(traceback.format_exc())
            if attempt < max_attempts - 1:
                logger.info(f"Retrying in {backoff_time} seconds")
                time.sleep(backoff_time)
                backoff_time *= 1.5
    
    # If we've exhausted all attempts
    logger.error(f"Failed to extract content after {max_attempts} attempts for URL: {url}")
    return {"success": 0, "content": ""}

if __name__ == "__main__":
    # Example usage
    import sys
    
    logger.info("Parser running in main mode")
    
    # if len(sys.argv) > 1:
    if True:
        # url = sys.argv[1]
        url = 'https://thedefiant.io/news/markets/five-fartcoin-holders-generate-nearly-usd9-million-in-profits-as-token-rallies'
        logger.info(f"Processing URL: {url}")
        
        instruction_type = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INSTRUCTION
        logger.info(f"Using instruction type: {instruction_type}")
        
        # Check for --debug flag
        # debug_mode = "--debug" in sys.argv
        debug_mode = False
        logger.info(f"Debug mode: {debug_mode}")

        # Check for --retry flag 
        # enable_retries = "--retry" in sys.argv
        enable_retries = False
        logger.info(f"Retry mode: {enable_retries}")
        
        summary = extract_summary(url, enable_retries=enable_retries, debug_mode=debug_mode)
        logger.info("Summary extraction complete")
        logger.info(f"Full summary result: {format_json(summary)}")
        print(json.dumps(summary, indent=2))
    else:
        logger.info("No URL provided, showing usage information")
        print("Usage: python parser.py <url> [instruction_type] [--debug] [--retry]")
        print(f"Available instruction types: {', '.join(INSTRUCTIONS.keys())}")
        print("  --debug: Enable LiteLLM debug mode")
        print("  --retry: Enable retry logic (up to 5 attempts)")
