import sqlite3
import os
import logging
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
    """Create and return a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def update_source_categories():
    """Update existing sources with category information"""

    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if category column exists
        cursor.execute("PRAGMA table_info(sources)")
        columns = cursor.fetchall()
        has_category = any(column['name'] == 'category' for column in columns)
        
        if not has_category:
            logger.info("Adding category column to sources table")
            cursor.execute("ALTER TABLE sources ADD COLUMN category TEXT DEFAULT 'Web3'")
        
        # # Update categories for known sources
        # update_count = 0
        # for source in sources_with_categories:
        #     cursor.execute(
        #         "UPDATE sources SET category = ? WHERE url = ?",
        #         (source['category'], source['url'])
        #     )
        #     update_count += cursor.rowcount
        
        # conn.commit()
        # logger.info(f"Updated {update_count} sources with categories")
        
        # # Show summary of categories
        # cursor.execute("SELECT category, COUNT(*) as count FROM sources GROUP BY category")
        # categories = cursor.fetchall()
        # logger.info("Category summary:")
        # for category in categories:
        #     logger.info(f"  {category['category']}: {category['count']} sources")
        
    except sqlite3.Error as e:
        logger.error(f"Error updating source categories: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting update of source categories")
    update_source_categories()
    logger.info("Completed update of source categories") 