# explore_endpoints.py
import requests
import json
import sqlite3
from config import DATABASE
import random

# Define the base URL of your backend (adjust if your app is running on a different port or address)
BASE_URL = "http://127.0.0.1:5000"  # Default Flask development server address

def get_message_content(message_id):
    """Fetch message content from database by ID"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT data, source_url, date
            FROM messages
            WHERE id = ?
        """, (message_id,))
        
        result = cursor.fetchone()
        if result:
            return {
                "content": result[0],
                "source": result[1],
                "date": result[2]
            }
        return None
    except Exception as e:
        print(f"Error fetching message {message_id}: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

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
            message_ids = topic.get("message_ids", [])
            
            print(f"\nTopic {i+1}: {topic_name}")
            print(f"  Importance: {importance}/10")
            print(f"  Based on {len(message_ids)} messages")
            
            # Print the full summary
            summary = topic.get("summary", "")
            if summary:
                print(f"  Summary: {summary}")
            
            # Print full message content for each message ID
            print("\n  Source Messages:")
            for msg_id in message_ids:
                msg_content = get_message_content(msg_id)
                if msg_content:
                    print(f"\n    Message ID: {msg_id}")
                    print(f"    Source: {msg_content['source']}")
                    print(f"    Date: {msg_content['date']}")
                    print(f"    Content: {msg_content['content']}")
                else:
                    print(f"    Message ID: {msg_id} - Content not found")
        
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
                
                # Print analysis summary and stance
                if insights.get("analysis_summary"):
                    print(f"    ANALYSIS SUMMARY:")
                    print(f"      {insights['analysis_summary']}")
                
                if insights.get("stance"):
                    print(f"    STANCE: {insights['stance']}")
                
                # Print rationales
                for rationale_type in ["rationale_long", "rationale_short", "rationale_neutral"]:
                    if insights.get(rationale_type):
                        print(f"    {rationale_type.upper()}:")
                        print(f"      {insights[rationale_type]}")
                
                # Print risks and questions as lists
                for list_field in ["risks_and_watchouts", "key_questions_for_user"]:
                    if insights.get(list_field) and len(insights[list_field]) > 0:
                        print(f"    {list_field.upper()}:")
                        for item in insights[list_field]:
                            print(f"      - {item}")
                
                # Print instruments
                for instruments_field in ["suggested_instruments_long", "suggested_instruments_short"]:
                    instruments = insights.get(instruments_field, [])
                    if instruments and len(instruments) > 0:
                        print(f"    {instruments_field.upper()}:")
                        for instrument in instruments:
                            print(f"      - Instrument: {instrument.get('instrument', 'N/A')}")
                            print(f"        Rationale: {instrument.get('rationale', 'N/A')}")
                            print(f"        Type: {instrument.get('type', 'N/A')}")
                
                # Print resources
                resources = insights.get("useful_resources", [])
                if resources and len(resources) > 0:
                    print(f"    USEFUL_RESOURCES:")
                    for resource in resources:
                        print(f"      - URL: {resource.get('url', 'N/A')}")
                        print(f"        Description: {resource.get('description', 'N/A')}")
        
        # Ask if the user wants to see the full JSON response
        show_full = input("\nDo you want to see the full JSON response? (y/n): ").lower() == 'y'
        if show_full:
            print("\nFull response:")
            print(json.dumps(data, indent=4, ensure_ascii=False))
            
        return data
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching insights: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                print(f"Server error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        return None

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
                
                # Print analysis summary and stance
                if insights.get("analysis_summary"):
                    print(f"    ANALYSIS SUMMARY:")
                    print(f"      {insights['analysis_summary']}")
                
                if insights.get("stance"):
                    print(f"    STANCE: {insights['stance']}")
                
                # Print rationales
                for rationale_type in ["rationale_long", "rationale_short", "rationale_neutral"]:
                    if insights.get(rationale_type):
                        print(f"    {rationale_type.upper()}:")
                        print(f"      {insights[rationale_type]}")
                
                # Print risks and questions as lists
                for list_field in ["risks_and_watchouts", "key_questions_for_user"]:
                    if insights.get(list_field) and len(insights[list_field]) > 0:
                        print(f"    {list_field.upper()}:")
                        for item in insights[list_field]:
                            print(f"      - {item}")
                
                # Print instruments
                for instruments_field in ["suggested_instruments_long", "suggested_instruments_short"]:
                    instruments = insights.get(instruments_field, [])
                    if instruments and len(instruments) > 0:
                        print(f"    {instruments_field.upper()}:")
                        for instrument in instruments:
                            print(f"      - Instrument: {instrument.get('instrument', 'N/A')}")
                            print(f"        Rationale: {instrument.get('rationale', 'N/A')}")
                            print(f"        Type: {instrument.get('type', 'N/A')}")
                
                # Print resources
                resources = insights.get("useful_resources", [])
                if resources and len(resources) > 0:
                    print(f"    USEFUL_RESOURCES:")
                    for resource in resources:
                        print(f"      - URL: {resource.get('url', 'N/A')}")
                        print(f"        Description: {resource.get('description', 'N/A')}")
        
        # Ask if the user wants to see the full JSON response
        show_full = input("\nDo you want to see the full JSON response? (y/n): ").lower() == 'y'
        if show_full:
            print("\nFull response:")
            print(json.dumps(data, indent=4, ensure_ascii=False))
            
        return data
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching insights: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                print(f"Server error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        return None

def simulate_frontend_flow():
    """Simulates the typical flow of API calls made by the frontend using the new separated endpoints."""
    print("\n--- Simulating Frontend API Flow ---")
    print("This will simulate how the frontend interacts with the API endpoints.")
    
    # Step 1: Check available sources
    print("\nStep 1: Fetching available sources...")
    try:
        sources_url = f"{BASE_URL}/sources"
        response = requests.get(sources_url)
        response.raise_for_status()
        sources_data = response.json()
        
        categorized_sources = sources_data.get("sources", {})
        source_count = sum(len(sources) for sources in categorized_sources.values())
        print(f"Found {source_count} sources in {len(categorized_sources)} categories")
        
        # Select a random category and source
        if categorized_sources:
            categories = list(categorized_sources.keys())
            selected_category = random.choice(categories)
            sources_in_category = categorized_sources[selected_category]
            
            if sources_in_category:
                selected_source = random.choice(sources_in_category)
                source_url = selected_source.get("url")
                source_name = selected_source.get("name")
                print(f"Selected source: {source_name} ({source_url})")
            else:
                print("No sources available in the selected category")
                source_url = None
        else:
            print("No sources available")
            source_url = None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sources: {e}")
        source_url = None
    
    # Step 2: Generate summaries
    print("\nStep 2: Generating summaries...")
    try:
        # Build query parameters - use 1d period and selected source if available
        period = "1d"
        query_params = f"period={period}"
        if source_url:
            query_params += f"&sources={source_url}"
        
        print(f"Fetching summaries with: {query_params}")
        summaries_url = f"{BASE_URL}/summaries?{query_params}"
        response = requests.get(summaries_url)
        response.raise_for_status()
        summaries_data = response.json()
        
        topics = summaries_data.get("topics", [])
        print(f"Received {len(topics)} topics")
        
        if not topics:
            print("No topics found. Cannot continue flow simulation.")
            return
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching summaries: {e}")
        return
    
    # Step 3: Generate insights for the first topic
    print("\nStep 3: Generating insights for the first topic...")
    try:
        first_topic = topics[0]
        print(f"Selected topic: {first_topic.get('topic', 'Unknown')}")
        
        # Create a request with just the first topic
        insights_request = {"topics": [first_topic]}
        
        insights_url = f"{BASE_URL}/insights"
        response = requests.post(insights_url, json=insights_request)
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
                # Display stance and main insight
                if insights.get("stance"):
                    print(f"  - Stance: {insights['stance']}")
                
                if insights.get("analysis_summary"):
                    print(f"  - Analysis Summary available")
                    
                for field in ["rationale_long", "rationale_short", "rationale_neutral"]:
                    if insights.get(field):
                        print(f"  - {field} available")
                
                # Print counts for array fields
                for field in ["risks_and_watchouts", "key_questions_for_user", "suggested_instruments_long", 
                             "suggested_instruments_short", "useful_resources"]:
                    items = insights.get(field, [])
                    if items:
                        print(f"  - {field}: {len(items)} items")
        
        print("\nNew separated endpoints flow simulation completed successfully")
            
    except requests.exceptions.RequestException as e:
        print(f"Error during frontend flow simulation: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"Response error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response text: {e.response.text}")
        return

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