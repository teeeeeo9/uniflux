# explore_endpoints.py
import requests
import json

# Define the base URL of your backend (adjust if your app is running on a different port or address)
BASE_URL = "http://127.0.0.1:5000"  # Default Flask development server address

def explore_sources_endpoint():
    """Fetches and prints the content of the /sources endpoint (GET)."""
    url = f"{BASE_URL}/sources"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        print("\n--- /sources Endpoint Content (GET) ---")
        print(json.dumps(data, indent=4))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching /sources (GET): {e}")
    except json.JSONDecodeError:
        print("Error decoding JSON response from /sources (GET)")

def explore_process_news_post_endpoint():
    """Sends a POST request to the /process_news endpoint with a mock messages history."""
    url = f"{BASE_URL}/process_news"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "messages_history": [
            {
                "internal_id": 1,
                "telegram_id": 100,
                "channel_url": "https://t.me/channel1",
                "text": "Breaking news: DeFi Protocol Alpha launched with innovative features!",
                "date": "...",
                "links": []
            },
            {
                "internal_id": 2,
                "telegram_id": 101,
                "channel_url": "https://t.me/channel1",
                "text": "More details on DeFi Protocol Alpha's governance mechanism.",
                "date": "...",
                "links": ["https://alpha.xyz/governance"]
            },
            {
                "internal_id": 3,
                "telegram_id": 200,
                "channel_url": "https://t.me/marketupdates",
                "text": "Market analysis shows a bullish trend for BTC and ETH.",
                "date": "...",
                "links": []
            },
            {
                "internal_id": 4,
                "telegram_id": 102,
                "channel_url": "https://t.me/channel1",
                "text": "Community discussion about the risks involved in using DeFi Protocol Alpha.",
                "date": "...",
                "links": []
            },
            {
                "internal_id": 5,
                "telegram_id": 300,
                "channel_url": "https://t.me/web3news",
                "text": "Latest developments in Web3 infrastructure and scalability solutions.",
                "date": "...",
                "links": ["https://web3.info/scalability"]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        print("\n--- /process_news Endpoint Content (POST) ---")
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except requests.exceptions.RequestException as e:
        print(f"Error posting to /process_news: {e}")
        if e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response body: {json.dumps(error_data, indent=4)}")
            except json.JSONDecodeError:
                print(f"Could not decode error response: {e.response.text}")
        else:
            print(f"No response received.")
    except json.JSONDecodeError:
        print("Error decoding JSON response from /process_news (POST)")

def explore_news_all_post_endpoint():
    """Sends a POST request to the /news/all endpoint with a list of Telegram links."""
    url = f"{BASE_URL}/news/all"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "telegram_links": [
            "https://t.me/cointelegraph",
            "https://t.me/binanceannouncements",
            "https://t.me/ethereum_news"
        ]
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        print("\n--- /news/all Endpoint Content (POST) ---")
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except requests.exceptions.RequestException as e:
        print(f"Error posting to /news/all: {e}")
        if e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response body: {json.dumps(error_data, indent=4)}")
            except json.JSONDecodeError:
                print(f"Could not decode error response: {e.response.text}")
        else:
            print(f"No response received.")
    except json.JSONDecodeError:
        print("Error decoding JSON response from /news/all (POST)")

def explore_insights_endpoint():
    """Tests the GET /insights endpoint that provides actionable insights based on time period and sources."""
    # Define parameters
    period = "1d"  # Options: 1d, 2d, 1w
    sources = "https://t.me/the_block_crypto,https://t.me/cointelegraph"  # Comma-separated list of sources
    
    # Build URL with query parameters
    url = f"{BASE_URL}/insights?period={period}&sources={sources}"
    
    print(f"\n--- Testing /insights Endpoint (GET) ---")
    print(f"Requesting insights for period: {period}, sources: {sources}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Get the number of topics
        topics = data.get("topics", [])
        topic_count = len(topics)
        
        print(f"Received {topic_count} topics with insights")
        
        # Print a summary of each topic
        for i, topic in enumerate(topics):
            topic_name = topic.get("topic", "Unknown")
            importance = topic.get("importance", "N/A")
            message_count = len(topic.get("message_ids", []))
            
            print(f"\nTopic {i+1}: {topic_name}")
            print(f"  Importance: {importance}/10")
            print(f"  Messages: {message_count}")
            
            # Print insights summary
            insights = topic.get("insights", {})
            if insights:
                print("  Insights:")
                for key in insights:
                    if key == "exec_options_long" or key == "exec_options_short":
                        options = insights[key]
                        if options:
                            print(f"    {key}: {len(options)} options")
                            for j, option in enumerate(options):
                                print(f"      Option {j+1}:")
                                for opt_key, opt_value in option.items():
                                    print(f"        {opt_key}: {opt_value}")
                    else:
                        content = insights[key]
                        if content:
                            # Display full content without truncation
                            print(f"    {key}: {content}")
        
        # Ask if the user wants to see the full JSON response
        show_full = input("\nDo you want to see the full JSON response? (y/n): ").lower() == 'y'
        if show_full:
            print("\nFull response:")
            print(json.dumps(data, indent=4, ensure_ascii=False))
            
    except requests.exceptions.RequestException as e:
        print(f"Error accessing /insights: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response body: {json.dumps(error_data, indent=4)}")
            except json.JSONDecodeError:
                print(f"Could not decode error response: {e.response.text}")
        else:
            print(f"No response received.")
    except json.JSONDecodeError:
        print("Error decoding JSON response from /insights (GET)")

if __name__ == "__main__":
    print("Make sure your Flask app is running before executing this script.")
    input("Press Enter to continue...")
    
    # Prompt user to select which endpoint to test
    print("\nAvailable endpoints to test:")
    print("1. /sources (GET)")
    print("2. /process_news (POST)")
    print("3. /news/all (POST)")
    print("4. /insights (GET) - NEW!")
    print("5. Test all endpoints")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == '1':
        explore_sources_endpoint()
    elif choice == '2':
        explore_process_news_post_endpoint()
    elif choice == '3':
        explore_news_all_post_endpoint()
    elif choice == '4':
        explore_insights_endpoint()
    elif choice == '5':
        explore_sources_endpoint()
        explore_process_news_post_endpoint()
        explore_news_all_post_endpoint()
        explore_insights_endpoint()
    else:
        print("Invalid choice. Exiting.")