# explore_endpoints.py
import requests
import json

# Define the base URL of your backend (adjust if your app is running on a different port or address)
BASE_URL = "http://127.0.0.1:5000"  # Default Flask development server address

def explore_sources_endpoint():
    """Fetches and prints the content of the /sources endpoint (GET).
    This endpoint is used by the frontend to populate the source selection UI."""
    url = f"{BASE_URL}/sources"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        print("\n--- /sources Endpoint Content (GET) ---")
        
        if "sources" in data:
            categories = data["sources"]
            print(f"Found {len(categories)} categories of sources:")
            
            for category, sources in categories.items():
                print(f"\nCategory: {category}")
                print(f"  Sources count: {len(sources)}")
                for source in sources[:5]:  # Show up to 5 sources per category
                    print(f"  - {source['url']} (ID: {source['id']})")
                
                if len(sources) > 5:
                    print(f"  ... and {len(sources) - 5} more")
        
        show_full = input("\nDo you want to see the full JSON response? (y/n): ").lower() == 'y'
        if show_full:
            print(json.dumps(data, indent=4))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching /sources (GET): {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response body: {json.dumps(error_data, indent=4)}")
            except json.JSONDecodeError:
                print(f"Could not decode error response: {e.response.text}")
    except json.JSONDecodeError:
        print("Error decoding JSON response from /sources (GET)")


def explore_insights_endpoint():
    """Tests the GET /insights endpoint that provides actionable insights based on time period and sources.
    This is the main endpoint used by the frontend to get aggregated news data."""
    # Define parameters
    print("\n--- Testing /insights Endpoint (GET) ---")
    
    # Let user choose parameters
    print("Available time periods:")
    print("1. Last 24 hours (1d)")
    print("2. Last 2 days (2d)")
    print("3. Last week (1w)")
    period_choice = input("Choose a time period (1-3): ")
    
    if period_choice == '1':
        period = "1d"
    elif period_choice == '2':
        period = "2d"
    elif period_choice == '3':
        period = "1w"
    else:
        period = "1d"  # Default
    
    # Ask for sources
    use_default = input("\nUse default sources? (y/n): ").lower() == 'y'
    if use_default:
        sources = "https://t.me/CoinDeskGlobal,https://t.me/cointelegraph"
    else:
        sources = input("Enter comma-separated list of sources (or leave empty for all sources): ")
    
    # Build URL with query parameters
    url = f"{BASE_URL}/insights?period={period}"
    if sources:
        url += f"&sources={sources}"
    
    print(f"\nRequesting insights for period: {period}")
    if sources:
        print(f"Sources: {sources}")
    else:
        print("Sources: All available sources")
    
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
            print(f"  Based on {message_count} messages")
            
            # Print a summary snippet
            summary = topic.get("summary", "")
            if summary:
                if len(summary) > 100:
                    print(f"  Summary: {summary[:100]}...")
                else:
                    print(f"  Summary: {summary}")
            
            # Print insights summary
            insights = topic.get("insights", {})
            if insights:
                print("  Insights available:")
                for key in insights:
                    if key == "exec_options_long" or key == "exec_options_short":
                        options = insights[key]
                        if options:
                            print(f"    {key}: {len(options)} options")
                    else:
                        print(f"    - {key}")
        
        # Ask if the user wants to see details for a specific topic
        if topic_count > 0:
            show_details = input("\nDo you want to see detailed insights for a specific topic? (y/n): ").lower() == 'y'
            if show_details:
                topic_idx = int(input(f"Enter topic number (1-{topic_count}): ")) - 1
                if 0 <= topic_idx < topic_count:
                    topic = topics[topic_idx]
                    print(f"\nDetailed view of topic: {topic.get('topic', 'Unknown')}")
                    
                    # Print full summary
                    print(f"\nFull Summary:")
                    print(topic.get("summary", "No summary available"))
                    
                    # Print insights
                    insights = topic.get("insights", {})
                    if insights:
                        print("\nInsights:")
                        for key, value in insights.items():
                            if key not in ["exec_options_long", "exec_options_short"]:
                                print(f"\n{key.upper()}:")
                                print(value)
                        
                        # Print execution options
                        exec_options = insights.get("exec_options_long", [])
                        if exec_options:
                            print("\nExecution Options:")
                            for i, option in enumerate(exec_options):
                                print(f"\nOption {i+1}:")
                                print(f"  Text: {option.get('text', 'N/A')}")
                                print(f"  Description: {option.get('description', 'N/A')}")
                                print(f"  Type: {option.get('type', 'N/A')}")
                    else:
                        print("\nNo insights available for this topic.")
                else:
                    print("Invalid topic number.")
        
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

def simulate_frontend_flow():
    """Simulates the typical flow of API calls made by the frontend."""
    print("\n--- Simulating Frontend Flow ---")
    
    # Step 1: Load sources
    print("\nStep 1: Fetching sources (this populates the source selection UI)")
    url = f"{BASE_URL}/sources"
    try:
        response = requests.get(url)
        response.raise_for_status()
        sources_data = response.json()
        
        # Extract sources from the response
        all_sources = []
        if "sources" in sources_data:
            for category, sources in sources_data["sources"].items():
                for source in sources:
                    all_sources.append(source["url"])
        
        print(f"Found {len(all_sources)} sources across all categories")
        
        # Step 2: Select sources and time period (simulating user input)
        print("\nStep 2: Selecting sources and time period (simulating user input)")
        selected_period = "1d"
        
        # Select up to 3 sources if available
        selected_sources = all_sources[:min(3, len(all_sources))]
        print(f"Selected period: {selected_period}")
        print(f"Selected sources: {selected_sources}")
        
        # Step 3: Fetch insights
        print("\nStep 3: Fetching insights based on selected parameters")
        query_params = {
            "period": selected_period
        }
        if selected_sources:
            query_params["sources"] = ",".join(selected_sources)
        
        insights_url = f"{BASE_URL}/insights"
        response = requests.get(insights_url, params=query_params)
        response.raise_for_status()
        insights_data = response.json()
        
        topics = insights_data.get("topics", [])
        print(f"Received {len(topics)} topics with insights")
        
        if topics:
            # Display first topic summary
            first_topic = topics[0]
            print("\nFirst topic summary:")
            print(f"Title: {first_topic.get('topic', 'Unknown')}")
            print(f"Importance: {first_topic.get('importance', 'N/A')}/10")
            print(f"Based on {len(first_topic.get('message_ids', []))} messages")
            
            insights = first_topic.get("insights", {})
            if insights:
                print("\nInsights available:")
                for key in insights:
                    if key == "exec_options_long" or key == "exec_options_short":
                        options = insights[key]
                        if options:
                            print(f"  {key}: {len(options)} options")
                    else:
                        print(f"  - {key}")
        
        print("\nFrontend flow simulation completed successfully")
            
    except requests.exceptions.RequestException as e:
        print(f"Error during frontend flow simulation: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")

if __name__ == "__main__":
    print("Make sure your Flask app is running before executing this script.")
    input("Press Enter to continue...")
    
    # Prompt user to select which endpoint to test
    print("\nAvailable endpoints to test:")
    print("1. /sources (GET) - Fetch all sources with categories")
    print("2. /insights (GET) - Get topics and insights based on time period and sources")
    print("3. Simulate frontend flow (test sequence of API calls)")
    print("4. Test all endpoints")
    
    choice = input("\nEnter your choice (1-4): ")
    
    if choice == '1':
        explore_sources_endpoint()
    elif choice == '2':
        explore_insights_endpoint()
    elif choice == '3':
        simulate_frontend_flow()
    elif choice == '4':
        explore_sources_endpoint()
        explore_insights_endpoint()
        simulate_frontend_flow()
    else:
        print("Invalid choice. Exiting.")