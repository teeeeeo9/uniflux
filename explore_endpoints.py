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


def explore_summaries_endpoint():
    """Tests the GET /summaries endpoint that provides topic summaries based on time period and sources."""
    print("\n--- Testing /summaries Endpoint (GET) ---")
    
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
    url = f"{BASE_URL}/summaries?period={period}"
    if sources:
        url += f"&sources={sources}"
    
    print(f"\nRequesting summaries for period: {period}")
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
        
        print(f"Received {topic_count} topic summaries")
        
        # Print a summary of each topic
        for i, topic in enumerate(topics):
            topic_name = topic.get("topic", "Unknown")
            importance = topic.get("importance", "N/A")
            message_count = len(topic.get("message_ids", []))
            
            print(f"\nTopic {i+1}: {topic_name}")
            print(f"  Importance: {importance}/10")
            print(f"  Based on {message_count} messages")
            
            # Print the full summary
            summary = topic.get("summary", "")
            if summary:
                print(f"  Summary: {summary}")
        
        # Return the data for further testing with insights
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error accessing /summaries: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response body: {json.dumps(error_data, indent=4)}")
            except json.JSONDecodeError:
                print(f"Could not decode error response: {e.response.text}")
        else:
            print(f"No response received.")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON response from /summaries (GET)")
        return None

def explore_insights_endpoint(summaries_data=None):
    """Tests the POST /insights endpoint that provides actionable insights based on summaries.
    If summaries_data is None, asks the user to first get summaries."""
    print("\n--- Testing /insights Endpoint (POST) ---")
    
    # If no summaries provided, get them first
    if summaries_data is None:
        print("No summaries data provided. Let's first get summaries.")
        summaries_data = explore_summaries_endpoint()
        
        if not summaries_data:
            print("Failed to get summaries data. Cannot test insights endpoint.")
            return
    
    # Let the user know what we're doing
    topics = summaries_data.get("topics", [])
    print(f"\nGenerating insights for {len(topics)} topics from summaries")
    
    # Send the POST request
    url = f"{BASE_URL}/insights"
    try:
        response = requests.post(url, json=summaries_data)
        response.raise_for_status()
        data = response.json()
        
        # Get the topics with insights
        topics_with_insights = data.get("topics", [])
        
        print(f"Received {len(topics_with_insights)} topics with insights")
        
        # Print a summary of each topic with insights
        for i, topic in enumerate(topics_with_insights):
            topic_name = topic.get("topic", "Unknown")
            importance = topic.get("importance", "N/A")
            
            print(f"\nTopic {i+1}: {topic_name}")
            print(f"  Importance: {importance}/10")
            
            # Print insights summary
            insights = topic.get("insights", {})
            if insights:
                print("  Insights:")
                for key, value in insights.items():
                    if key == "exec_options_long" or key == "exec_options_short":
                        options = insights[key]
                        if options:
                            print(f"    {key}:")
                            for option in options:
                                print(f"      - Text: {option.get('text', 'N/A')}")
                                print(f"        Description: {option.get('description', 'N/A')}")
                                print(f"        Type: {option.get('type', 'N/A')}")
                    else:
                        print(f"    {key.upper()}:")
                        print(f"      {value}")
        
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
        print("Error decoding JSON response from /insights (POST)")

def explore_legacy_insights_endpoint():
    """Tests the GET /insights endpoint that provides both summaries and insights.
    This is the legacy endpoint that combines both steps."""
    # Define parameters
    print("\n--- Testing /insights Legacy Endpoint (GET) ---")
    
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
            
            # Print the full summary
            summary = topic.get("summary", "")
            if summary:
                print(f"  Summary: {summary}")
            
            # Print insights summary
            insights = topic.get("insights", {})
            if insights:
                print("  Insights:")
                for key, value in insights.items():
                    if key == "exec_options_long" or key == "exec_options_short":
                        options = insights[key]
                        if options:
                            print(f"    {key}:")
                            for option in options:
                                print(f"      - Text: {option.get('text', 'N/A')}")
                                print(f"        Description: {option.get('description', 'N/A')}")
                                print(f"        Type: {option.get('type', 'N/A')}")
                    else:
                        print(f"    {key.upper()}:")
                        print(f"      {value}")
        
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
    """Simulates the typical flow of API calls made by the frontend using the new separated endpoints."""
    print("\n--- Simulating Frontend Flow (New Separated Endpoints) ---")
    
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
        
        # Step 3: Fetch summaries
        print("\nStep 3: Fetching summaries based on selected parameters")
        query_params = {
            "period": selected_period
        }
        if selected_sources:
            query_params["sources"] = ",".join(selected_sources)
        
        summaries_url = f"{BASE_URL}/summaries"
        response = requests.get(summaries_url, params=query_params)
        response.raise_for_status()
        summaries_data = response.json()
        
        topics = summaries_data.get("topics", [])
        print(f"Received {len(topics)} topic summaries")
        
        # Step 4: Send summaries to get insights
        print("\nStep 4: Sending summaries to get insights")
        insights_url = f"{BASE_URL}/insights"
        response = requests.post(insights_url, json=summaries_data)
        response.raise_for_status()
        insights_data = response.json()
        
        topics_with_insights = insights_data.get("topics", [])
        print(f"Received {len(topics_with_insights)} topics with insights")
        
        if topics_with_insights:
            # Display first topic summary
            first_topic = topics_with_insights[0]
            print("\nFirst topic with insights:")
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
        
        print("\nNew separated endpoints flow simulation completed successfully")
            
    except requests.exceptions.RequestException as e:
        print(f"Error during frontend flow simulation: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")

def simulate_legacy_frontend_flow():
    """Simulates the typical flow of API calls made by the frontend using the legacy endpoint."""
    print("\n--- Simulating Frontend Flow (Legacy Endpoint) ---")
    
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
        
        # Step 3: Fetch insights (combined)
        print("\nStep 3: Fetching insights using legacy endpoint")
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
            print("\nFirst topic with insights:")
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
        
        print("\nLegacy endpoint flow simulation completed successfully")
            
    except requests.exceptions.RequestException as e:
        print(f"Error during legacy frontend flow simulation: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")

if __name__ == "__main__":
    print("Make sure your Flask app is running before executing this script.")
    input("Press Enter to continue...")
    
    # Prompt user to select which endpoint to test
    print("\nAvailable endpoints and flows to test:")
    print("1. /sources (GET) - Fetch all sources with categories")
    print("2. /summaries (GET) - Get topic summaries based on time period and sources")
    print("3. /insights (POST) - Get actionable insights based on summaries")
    print("4. /insights (GET) - Legacy endpoint that combines summaries and insights")
    print("5. Simulate new frontend flow with separated endpoints")
    print("6. Simulate legacy frontend flow")
    print("7. Complete pipeline: summaries then insights")
    print("8. Test all endpoints and flows")
    
    choice = input("\nEnter your choice (1-8): ")
    
    if choice == '1':
        explore_sources_endpoint()
    elif choice == '2':
        explore_summaries_endpoint()
    elif choice == '3':
        print("You need to get summaries first before testing the insights endpoint.")
        summaries_data = explore_summaries_endpoint()
        if summaries_data:
            explore_insights_endpoint(summaries_data)
    elif choice == '4':
        explore_legacy_insights_endpoint()
    elif choice == '5':
        simulate_frontend_flow()
    elif choice == '6':
        simulate_legacy_frontend_flow()
    elif choice == '7':
        summaries_data = explore_summaries_endpoint()
        if summaries_data:
            explore_insights_endpoint(summaries_data)
    elif choice == '8':
        explore_sources_endpoint()
        summaries_data = explore_summaries_endpoint()
        if summaries_data:
            explore_insights_endpoint(summaries_data)
        explore_legacy_insights_endpoint()
        simulate_frontend_flow()
        simulate_legacy_frontend_flow()
    else:
        print("Invalid choice. Exiting.")