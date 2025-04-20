import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Determine environment (default to 'development' if not set)
ENV = os.getenv('ENV', 'development')

# Database configuration
if ENV == 'production':
    DATABASE = 'sources.db'
else:  # development or other environments
    DATABASE = 'sources_dev.db'

# Logging configuration
if ENV == 'production':
    LOG_FILE = 'log.log'
else:  # development or other environments
    LOG_FILE = 'log_dev.log'

# Telegram session configuration
if ENV == 'production':
    TELEGRAM_SESSION = 'telegram_session'
else:  # development or other environments
    TELEGRAM_SESSION = 'telegram_session'

# Print configuration for debugging purposes
if __name__ == '__main__':
    print(f"Environment: {ENV}")
    print(f"Database: {DATABASE}")
    print(f"Log file: {LOG_FILE}")
    print(f"Telegram session: {TELEGRAM_SESSION}") 