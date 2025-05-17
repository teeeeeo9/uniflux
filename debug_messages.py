#!/usr/bin/env python3
import sys
import json
import os
import importlib.util

# Add the current directory to the path so we can import local modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# First import the debug config to set the database path
import debug_config

# Now hack the system to use our config instead of the original
sys.modules['config'] = debug_config

# Now we can import from data_summarizer
from data_summarizer import get_messages
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(funcName)s() - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Specific sources from the log
SOURCES = [
    'tg-channel:1537133444',
    'tg-channel:1456656467',
    'tg-channel:1019770939'
]

def main():
    print(f"Using database: {debug_config.DATABASE}")
    
    # Test with different periods
    periods = ['1d', '3d', '1w']
    
    for period in periods:
        print(f"\n{'='*50}")
        print(f"Fetching messages for period: {period}")
        print(f"{'='*50}")
        
        # Call the get_messages function
        messages = get_messages(period, SOURCES)
        
        # Print summary of results
        print(f"Found {len(messages)} messages")
        
        # Print details of first few messages
        for i, msg in enumerate(messages[:3]):
            print(f"\nMessage {i+1}:")
            print(f"  ID: {msg['id']}")
            print(f"  Source: {msg['source_url']}")
            print(f"  Date: {msg['date']}")
            print(f"  Content: {msg['data'][:100]}..." if len(msg['data']) > 100 else f"  Content: {msg['data']}")
            
            # Check for summarized link content
            if msg['summarized_links_content'] and isinstance(msg['summarized_links_content'], dict):
                print(f"  Links: {len(msg['summarized_links_content'])} links found")
            else:
                print("  Links: None")
        
        # Print message count by source
        source_counts = {}
        for msg in messages:
            source = msg['source_url']
            source_counts[source] = source_counts.get(source, 0) + 1
        
        print("\nMessage count by source:")
        for source, count in source_counts.items():
            print(f"  {source}: {count}")
            
        # Print date range
        if messages:
            dates = [msg['date'] for msg in messages]
            print(f"\nDate range: {min(dates)} to {max(dates)}")
            
if __name__ == "__main__":
    main() 