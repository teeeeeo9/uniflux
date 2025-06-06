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
from config import DATABASE, LOG_FILE

# Custom JSON formatter for logs
def format_json(obj):
    """Format an object as pretty JSON if it's a dict or list, otherwise return as string"""
    if isinstance(obj, (dict, list)):
        return "\n" + json.dumps(obj, indent=2)
    return str(obj)

# Configure module-specific logger
logger = logging.getLogger('parser')
logger.setLevel(logging.INFO)  # Set module level to INFO

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

logger.info("Parser module initializing")

# Database file path
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

# Define a global variable to track last API call time for rate limiting
_last_api_call_time = 0
_api_rate_limit_delay = 4  # seconds between API calls

def _respect_rate_limit():
    """
    Helper function to implement rate limiting.
    Sleeps if needed to ensure minimum delay between API calls.
    """
    global _last_api_call_time
    current_time = time.time()
    time_since_last_call = current_time - _last_api_call_time
    
    if time_since_last_call < _api_rate_limit_delay and _last_api_call_time > 0:
        sleep_time = _api_rate_limit_delay - time_since_last_call
        logger.info(f"Rate limiting: Waiting {sleep_time:.2f} seconds before next API call")
        time.sleep(sleep_time)
    
    _last_api_call_time = time.time()

async def extract_summary(url: str, enable_retries: bool = False, debug_mode: bool = False) -> Dict[str, Any]:
    """
    Asynchronous function to extract summary from a URL with optional retry logic.
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
    
    # Apply rate limiting before extraction
    _respect_rate_limit()
    
    # If retries are not enabled, just make a single attempt with browser retry
    if not enable_retries:
        try:
            logger.info(f"Making extraction attempt for URL: {url}")
            # Use the new wrapper function instead of direct call
            result = await extract_with_browser_retry(url, instruction_type, debug_mode)
            logger.info(f"Extraction completed for URL: {url}")
            logger.info(f"Extraction result: {format_json(result)}")
            
            # Process the result to extract content
            processed_result = process_extraction_result(result, url)
            logger.info(f"Processed result: {format_json(processed_result)}")
            
            # If we got content, return it
            if processed_result["success"] == 1 and processed_result["content"]:
                return processed_result
                
            # If the error was a Gemini API error but we still got partial content,
            # the processing step above would have handled it
            
            # If we have no content but no error either, this is strange
            if "error" not in result:
                logger.warning(f"No content extracted but no error reported for URL: {url}")
                
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
            
            # Apply rate limiting before each attempt
            if attempt > 0:
                _respect_rate_limit()
                
            # Use the new wrapper function instead of direct call
            result = await extract_with_browser_retry(url, instruction_type, debug_mode)
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
    
    # Apply rate limiting
    _respect_rate_limit()
    
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
        apply_chunking=False,
        input_format="html",   # or "html", "fit_markdown"
        extra_args={"temperature": 0.0, "max_tokens": 2000}
    )

    # 2. Build the crawler config
    logger.info("Configuring crawler run config")
    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        simulate_user=True,
    )

    # 3. Create a browser config
    logger.info("Configuring browser")
    browser_cfg = BrowserConfig(
        headless=True,
        browser_type="firefox",
        )

    # Define retry parameters for Gemini API errors
    max_gemini_retries = 3
    gemini_retry_delay = 2  # seconds
    gemini_retry_count = 0

    while True:
        try:
            logger.info(f"Starting crawl for URL: {url}")
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                # 4. Crawl the page
                logger.info("Executing crawler run")
                result = await crawler.arun(
                    url=url,
                    config=crawl_config
                )

                logger.warning(f"Result: {result.success}")

                if result.success:
                    # 5. Return the extracted content
                    logger.info(f"Crawl successful for URL: {url}")
                    data = json.loads(result.extracted_content)
                    logger.info(f"Extracted content: {format_json(data)}")
                    
                    # Check if the content contains any error message 
                    # This happens when the crawler successfully runs but there's an error in extraction
                    extraction_error_found = False
                    retry_for_error = False
                    
                    if isinstance(data, list) and len(data) > 0:
                        for item in data:
                            if isinstance(item, dict) and item.get("error") is True:
                                content = item.get("content", "")
                                
                                # Case 1: Check for Gemini API error 499
                                if isinstance(content, str) and "GeminiException" in content and "code\": 499" in content and "The operation was cancelled" in content:
                                    logger.warning("Detected Gemini API error 499 in successful crawler response")
                                    extraction_error_found = True
                                    retry_for_error = gemini_retry_count < max_gemini_retries
                                    if retry_for_error:
                                        gemini_retry_count += 1
                                        logger.warning(f"Gemini API error 499 (operation cancelled) encountered. Retry {gemini_retry_count}/{max_gemini_retries}")
                                        logger.warning(f"Waiting {gemini_retry_delay} seconds before retrying...")
                                        time.sleep(gemini_retry_delay)
                                        gemini_retry_delay *= 2  # Exponential backoff
                                    else:
                                        logger.error(f"Exceeded maximum retries ({max_gemini_retries}) for Gemini API error 499")
                                
                                # Case 2: Check for 'list' object has no attribute 'usage' error
                                elif isinstance(content, str) and "'list' object has no attribute 'usage'" in content:
                                    logger.warning("Detected 'list' object has no attribute 'usage' error in successful crawler response")
                                    extraction_error_found = True
                                    retry_for_error = gemini_retry_count < max_gemini_retries
                                    if retry_for_error:
                                        gemini_retry_count += 1
                                        logger.warning(f"'list' usage attribute error encountered. Retry {gemini_retry_count}/{max_gemini_retries}")
                                        logger.warning(f"Waiting {gemini_retry_delay} seconds before retrying...")
                                        time.sleep(gemini_retry_delay)
                                        gemini_retry_delay *= 2  # Exponential backoff
                                    else:
                                        logger.error(f"Exceeded maximum retries ({max_gemini_retries}) for 'list' usage attribute error")
                                
                                # Case 3: Any other error that might need retrying
                                elif extraction_error_found == False:
                                    logger.warning(f"Detected unknown error in successful crawler response: {content}")
                                    extraction_error_found = True
                    
                    # If a retryable error was found and we still have retries left, try again
                    if extraction_error_found and retry_for_error:
                        # Apply rate limiting before retry
                        _respect_rate_limit()
                        continue
                    
                    # Add the URL to the result for use in the processing function
                    if isinstance(data, dict):
                        data["url"] = url
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                item["url"] = url
                    
                    # Safely show usage stats if available - wrap in try/except to catch any attribute errors
                    try:
                        llm_strategy.show_usage()
                    except AttributeError as e:
                        logger.warning(f"Could not show usage statistics: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Unexpected error showing usage statistics: {str(e)}")
                    
                    return data
                else:
                    logger.error(f"Crawl failed for URL: {url}")
                    logger.error(f"Error message: {result.error_message}")
                    return {"error": result.error_message}
        except litellm.APIConnectionError as e:
            error_str = str(e)
            
            # For rate limit errors, extract the retry delay from the response if available
            if "RESOURCE_EXHAUSTED" in error_str and "code\": 429" in error_str and gemini_retry_count < max_gemini_retries:
                gemini_retry_count += 1
                
                # Try to extract the recommended retry delay
                retry_delay_match = None
                try:
                    # Look for retryDelay in the response
                    if "retryDelay" in error_str:
                        import re
                        retry_delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
                except Exception:
                    logger.warning("Failed to parse retry delay from error response")
                
                # Use the recommended delay if available, otherwise use our default
                if retry_delay_match:
                    extracted_delay = int(retry_delay_match.group(1))
                    logger.warning(f"Gemini API rate limit error encountered. Using recommended retry delay of {extracted_delay}s. Retry {gemini_retry_count}/{max_gemini_retries}")
                    gemini_retry_delay = extracted_delay
                else:
                    logger.warning(f"Gemini API rate limit error encountered. Using default retry delay of {gemini_retry_delay}s. Retry {gemini_retry_count}/{max_gemini_retries}")
                    gemini_retry_delay *= 2  # Exponential backoff if we couldn't extract the value
                
                logger.warning(f"Waiting {gemini_retry_delay} seconds before retrying...")
                time.sleep(gemini_retry_delay)
                
                # Apply rate limiting before retry
                _respect_rate_limit() 
                continue  # Try again
            
            # Check if it's the specific Gemini error 499 (operation cancelled)
            elif "code\": 499" in error_str and "The operation was cancelled" in error_str and gemini_retry_count < max_gemini_retries:
                gemini_retry_count += 1
                logger.warning(f"Gemini API error 499 (operation cancelled) encountered. Retry {gemini_retry_count}/{max_gemini_retries}")
                logger.warning(f"Waiting {gemini_retry_delay} seconds before retrying...")
                time.sleep(gemini_retry_delay)
                gemini_retry_delay *= 2  # Exponential backoff
                # Apply rate limiting before retry
                _respect_rate_limit() 
                continue  # Try again
            else:
                # Either it's a different error or we've exceeded retries
                logger.error(f"Gemini API error: {error_str}")
                
                if gemini_retry_count >= max_gemini_retries:
                    logger.error(f"Exceeded maximum retries ({max_gemini_retries}) for Gemini API error")
                return {"error": f"Gemini API error: {error_str}"}
        except Exception as e:
            error_str = str(e)
            # Check for the 'list' object has no attribute 'usage' error
            if "'list' object has no attribute 'usage'" in error_str and gemini_retry_count < max_gemini_retries:
                gemini_retry_count += 1
                logger.warning(f"'list' usage attribute error encountered. Retry {gemini_retry_count}/{max_gemini_retries}")
                logger.warning(f"Waiting {gemini_retry_delay} seconds before retrying...")
                time.sleep(gemini_retry_delay)
                gemini_retry_delay *= 2  # Exponential backoff
                # Apply rate limiting before retry
                _respect_rate_limit()
                continue  # Try again
            else:
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
        # Check for specific error patterns in list results
        if isinstance(result, list):
            # Case 1: Check for Gemini API error 499
            gemini_error_items = []
            usage_error_items = []
            general_error_items = []
            
            for item in result:
                if isinstance(item, dict) and item.get("error") is True:
                    content = item.get("content", "")
                    if isinstance(content, str):
                        if "GeminiException" in content and "code\": 499" in content:
                            gemini_error_items.append(item)
                        elif "'list' object has no attribute 'usage'" in content:
                            usage_error_items.append(item)
                        else:
                            general_error_items.append(item)
            
            # Handle Gemini API error 499
            if len(gemini_error_items) > 0 and len(gemini_error_items) == len(result):
                logger.warning(f"All items in result list contain Gemini API error 499")
                return {"success": 0, "content": "", "error": "Gemini API error 499 (operation cancelled)"}
            
            # Handle 'list' usage attribute error
            if len(usage_error_items) > 0 and len(usage_error_items) == len(result):
                logger.warning(f"All items in result list contain 'list' usage attribute error")
                return {"success": 0, "content": "", "error": "Error: 'list' object has no attribute 'usage'"}
            
            # Handle general errors when all items have errors
            if len(general_error_items) > 0 and len(general_error_items) + len(gemini_error_items) + len(usage_error_items) == len(result):
                error_message = general_error_items[0].get("content", "Unknown error")
                logger.warning(f"All items in result list contain errors. First error: {error_message}")
                return {"success": 0, "content": "", "error": f"Error: {error_message}"}
        
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
        
        # Handle explicit error case
        elif isinstance(result, dict) and result.get("error"):
            error_msg = result.get("error")
            logger.warning(f"Result contains explicit error: {error_msg}")
            return {"success": 0, "content": "", "error": error_msg}
        
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

async def extract_with_browser_retry(url: str, instruction_type: str, debug_mode: bool) -> Dict[str, Any]:
    """
    Wrapper function that attempts extraction and handles browser closed errors by
    retrying multiple times with waits between attempts.
    
    Args:
        url: The URL to extract content from
        instruction_type: The type of instruction to use
        debug_mode: Whether to enable LiteLLM debug mode
        
    Returns:
        The extraction result
    """
    logger.info(f"Attempting extraction with browser retry for URL: {url}")
    
    max_browser_retries = 3
    for retry_num in range(max_browser_retries):
        try:
            # Apply rate limiting before each retry attempt after the first one
            if retry_num > 0:
                _respect_rate_limit()
                
            result = await extract_summary_from_link(url, instruction_type, debug_mode)
            
            # Check for the specific browser error
            if isinstance(result, dict) and isinstance(result.get("error"), str) and "BrowserType.launch: Target page, context or browser has been closed" in result.get("error", ""):
                if retry_num < max_browser_retries - 1:
                    logger.warning(f"Detected browser closed error, retry {retry_num+1}/{max_browser_retries}, waiting 5 seconds before retrying")
                    time.sleep(10)
                    continue
                else:
                    logger.error(f"Exhausted all {max_browser_retries} browser retries for URL: {url}")
            
            # Check for Gemini API error - we already handled retries in extract_summary_from_link
            if isinstance(result, dict) and isinstance(result.get("error"), str) and "Gemini API error" in result.get("error", ""):
                logger.info("Gemini API error already handled in extract_summary_from_link, passing through")
                return result
            
            # If we reach here, either no error or we're out of retries
            return result
            
        except Exception as e:
            if retry_num < max_browser_retries - 1:
                logger.error(f"Exception during extraction retry {retry_num+1}/{max_browser_retries}: {str(e)}")
                logger.error(traceback.format_exc())
                logger.info(f"Waiting 5 seconds before retry attempt {retry_num+2}")
                time.sleep(5)
            else:
                logger.error(f"Exception on final browser retry attempt: {str(e)}")
                logger.error(traceback.format_exc())
                return {"error": str(e)}
    
    # This should not happen but just in case
    return {"error": "Exhausted all browser retries with no success"}

if __name__ == "__main__":
    # Example usage
    import sys
    
    logger.info("Parser running in main mode")
    
    # if len(sys.argv) > 1:
    if True:
        # url = sys.argv[1]
        # url = 'https://thedefiant.io/news/markets/five-fartcoin-holders-generate-nearly-usd9-million-in-profits-as-token-rallies'
        url = 'https://www.coindesk.com/markets/2025/04/19/trump-s-official-memecoin-surges-despite-massive-usd320-million-unlock-in-thin-holiday-trading'
        url = 'https://www.coindesk.com/markets/2025/04/20/xrp-resembles-a-compressed-spring-poised-for-a-significant-move-as-key-volatility-indicator-mirrors-late-2024-pattern'
        url = 'https://cointelegraph.com/news/revolut-doubles-profit-user-growth-crypto-trading?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound'
        url = 'https://cointelegraph.com/news/forget-bull-or-bear-bitcoin-s-in-a-new-era-says-market-analyst-james-check?utm_source=rss_feed&'
        url = 'https://cointelegraph.com/news/prosecutors-over-200-victim-impact-statements-in-alex-mashinsky?utm_source=rss_feed&utm_medium=rss&'
        url = 'https://cointelegraph.com/news/kucoin-crypto-exchange-enters-crowded-thailand-market?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound'
        url = 'https://energywatch.com/EnergyNews/Utilities/article18111280.ece'
        
        
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
        
        # Run the async function
        summary = asyncio.run(extract_summary(url, enable_retries=enable_retries, debug_mode=debug_mode))
        logger.info("Summary extraction complete")
        logger.info(f"Full summary result: {format_json(summary)}")
        print(json.dumps(summary, indent=2))
        
        # Ensure logs are flushed
        for handler in logger.handlers:
            handler.flush()
            
    else:
        logger.info("No URL provided, showing usage information")
        print("Usage: python parser.py <url> [instruction_type] [--debug] [--retry]")
        print(f"Available instruction types: {', '.join(INSTRUCTIONS.keys())}")
        print("  --debug: Enable LiteLLM debug mode")
        print("  --retry: Enable retry logic (up to 5 attempts)")
