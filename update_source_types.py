#!/usr/bin/env python3
import sqlite3
import logging
import sys
import re
from config import DATABASE, LOG_FILE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(funcName)s() - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('update_source_types')

def get_db_connection():
    """Create and return a database connection"""
    logger.debug(f"Opening database connection to {DATABASE}")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    logger.debug("Database connection established")
    return conn

def update_existing_sources():
    """
    Updates existing sources in the database to have appropriate source_type values.
    Telegram URLs will be set to 'telegram', others will be attempted to be parsed as RSS.
    
    Returns:
        The number of updated records
    """
    logger.info("Updating source types for existing sources in the database")
    
    try:
        updated_count = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First, check if any sources have NULL or empty source_type
            cursor.execute("SELECT id, url FROM sources WHERE source_type IS NULL OR source_type = ''")
            results = cursor.fetchall()
            
            if not results:
                logger.info("No sources found with missing source_type")
                return 0
                
            logger.info(f"Found {len(results)} sources with missing source_type")
            
            # Process each source
            for source in results:
                source_id = source['id']
                url = source['url']
                
                # Determine source type based on URL pattern
                if re.match(r'^https?://t\.me/', url):
                    source_type = 'telegram'
                    logger.info(f"Identified source {source_id} as telegram: {url}")
                else:
                    # Default to RSS for now - we can't easily validate without parsing
                    source_type = 'rss'
                    logger.info(f"Assuming source {source_id} is RSS feed: {url}")
                
                # Update the source_type
                cursor.execute(
                    "UPDATE sources SET source_type = ? WHERE id = ?",
                    (source_type, source_id)
                )
                updated_count += 1
            
            conn.commit()
            logger.info(f"Updated {updated_count} sources with appropriate source types")
            return updated_count
            
    except Exception as e:
        logger.error(f"Error updating source types: {str(e)}")
        return 0

def main():
    # Update existing sources
    updated_count = update_existing_sources()
    print(f"Updated {updated_count} sources with appropriate source types")

if __name__ == "__main__":
    main() 