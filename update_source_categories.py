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
    # Define sources with their categories
    # sources_with_categories = [
    #     # Web3 category
    #     {'url': 'https://t.me/CoinDeskGlobal', 'category': 'Web3'},
    #     {'url': 'https://t.me/cointelegraph', 'category': 'Web3'},
    #     {'url': 'https://t.me/thedailyape', 'category': 'Web3'},
    #     {'url': 'https://t.me/blockchainnewscentral', 'category': 'Web3'},
        
    #     # Crypto Markets category
    #     {'url': 'https://t.me/cryptomarketdaily', 'category': 'Crypto Markets'},
    #     {'url': 'https://t.me/thecryptomerger', 'category': 'Crypto Markets'},
    #     {'url': 'https://t.me/cryptoanalysis', 'category': 'Crypto Markets'},
        
    #     # Energy News category
    #     {'url': 'https://t.me/energynewstoday', 'category': 'Energy'},
    #     {'url': 'https://t.me/energymarkets', 'category': 'Energy'},
    #     {'url': 'https://t.me/climatetech', 'category': 'Energy'}
    # ]
    
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