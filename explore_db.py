#!/usr/bin/env python3
import sqlite3
import json
import sys
from config import DATABASE
from datetime import datetime

# Database file path
conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row  # Return rows as dictionaries

def get_db_connection():
    """Create and return a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_table_info():
    """Get the table structure"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(link_summaries)")
        columns = cursor.fetchall()
        
        print("\n=== Table Structure ===")
        for col in columns:
            print(f"Column: {col['name']}, Type: {col['type']}")

def count_records():
    """Count the total number of records"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM link_summaries")
        result = cursor.fetchone()
        
        print(f"\n=== Record Count ===")
        print(f"Total records in link_summaries: {result['count']}")

def get_recent_records(limit=5):
    """Get the most recent records"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url, summary_content, updated_at 
            FROM link_summaries 
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (limit,))
        
        records = cursor.fetchall()
        
        print(f"\n=== {limit} Most Recent Records ===")
        for i, record in enumerate(records, 1):
            print(f"\nRecord #{i}:")
            print(f"URL: {record['url']}")
            print(f"Updated: {record['updated_at']}")
            
            # Display a preview of the content
            content = record['summary_content']
            if len(content) > 150:
                print(f"Content Preview: {content[:150]}...")
            else:
                print(f"Content: {content}")

def search_by_url(search_term):
    """Search for records by URL"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url, summary_content, updated_at 
            FROM link_summaries 
            WHERE url LIKE ?
        """, (f'%{search_term}%',))
        
        records = cursor.fetchall()
        
        print(f"\n=== Records matching '{search_term}' ===")
        if not records:
            print("No matching records found.")
            return
            
        for i, record in enumerate(records, 1):
            print(f"\nRecord #{i}:")
            print(f"URL: {record['url']}")
            print(f"Updated: {record['updated_at']}")
            print(f"Full Content: {record['summary_content']}")

def get_oldest_and_newest():
    """Get the oldest and newest records"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get oldest
        cursor.execute("""
            SELECT url, updated_at 
            FROM link_summaries 
            ORDER BY updated_at ASC 
            LIMIT 1
        """)
        oldest = cursor.fetchone()
        
        # Get newest
        cursor.execute("""
            SELECT url, updated_at 
            FROM link_summaries 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        newest = cursor.fetchone()
        
        print("\n=== Oldest and Newest Records ===")
        if oldest:
            print(f"Oldest record: {oldest['url']}, Updated: {oldest['updated_at']}")
        if newest:
            print(f"Newest record: {newest['url']}, Updated: {newest['updated_at']}")

def delete_message_by_id():
    """Delete a message record with the specified ID"""
    message_id=1
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"Successfully deleted message with ID: {message_id}")
                return True
            else:
                print(f"No message found with ID: {message_id}")
                return False
    except sqlite3.Error as e:
        print(f"Database error while deleting message: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def list_messages(limit=None):
    """List all messages from the messages table with optional limit"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if limit:
                cursor.execute("""
                    SELECT id, source_url, source_type, channel_id, message_id, 
                           date, data, summarized_links_content, created_at 
                    FROM messages 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT id, source_url, source_type, channel_id, message_id, 
                           date, data, summarized_links_content, created_at 
                    FROM messages 
                    ORDER BY created_at DESC
                """)
            
            messages = cursor.fetchall()
            
            print(f"\n=== Messages {f'(Limited to {limit})' if limit else ''} ===")
            if not messages:
                print("No messages found in the database.")
                return
                
            for i, msg in enumerate(messages, 1):
                print(f"\n----- Message #{i} -----")
                print(f"id: {msg['id']}")
                print(f"source_url: {msg['source_url']}")
                print(f"source_type: {msg['source_type']}")
                print(f"channel_id: {msg['channel_id']}")
                print(f"message_id: {msg['message_id']}")
                print(f"date: {msg['date']}")
                print(f"data: {msg['data']}")
                print(f"summarized_links_content: {msg['summarized_links_content']}")
                print(f"created_at: {msg['created_at']}")
    except sqlite3.Error as e:
        print(f"Database error while listing messages: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Database Explorer for link_summaries")
    
    try:
        # # Show table structure
        # get_table_info()
        
        # # Count records
        # count_records()
        
        # # Show newest and oldest records
        # get_oldest_and_newest()
        
        # Show most recent records
        # get_recent_records(10)
        # delete_message_by_id()
        
        # List messages from the messages table
        list_messages()  # Limit to 10 messages, remove the parameter to show all
        
        # # Allow interactive search
        # search_term = input("\nEnter a term to search in URLs (or press Enter to skip): ")
        # if search_term:
        #     search_by_url(search_term)
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}") 