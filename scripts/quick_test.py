#!/usr/bin/env python3
"""
Quick test script for the /summaries endpoint.
Usage: python quick_test.py [period] [sources...]
"""

import requests
import json
import sys
import time
from datetime import datetime


# Backend configuration
BACKEND_URL = "http://localhost:5000"
SUMMARIES_ENDPOINT = f"{BACKEND_URL}/summaries"


def main():
    """Main function to run a quick test."""
    print("Quick Backend Summaries Test")
    print("=" * 40)
    
    # Parse command line arguments
    period = sys.argv[1] if len(sys.argv) > 1 else "1d"
    sources = sys.argv[2:] if len(sys.argv) > 2 else None
    
    print(f"Period: {period}")
    print(f"Sources: {sources}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Prepare request parameters
    params = {"period": period}
    if sources:
        params["sources"] = ",".join(sources)
    
    # Add request ID for tracking
    headers = {"X-Request-ID": f"quick-test-{int(time.time())}"}
    
    try:
        print(f"\nSending request to: {SUMMARIES_ENDPOINT}")
        print(f"Parameters: {params}")
        
        # Make the request
        start_time = time.time()
        response = requests.get(SUMMARIES_ENDPOINT, params=params, headers=headers, timeout=300)
        end_time = time.time()
        
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Time: {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            # Show full raw JSON response with beautiful formatting
            print(f"\n{'='*60}")
            print("FULL RAW JSON RESPONSE:")
            print(f"{'='*60}")
            
            try:
                # Parse and pretty print the JSON
                data = response.json()
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                print(formatted_json)
                
                # Also show basic summary
                topics = data.get("topics", [])
                print(f"\n{'='*60}")
                print(f"✅ SUCCESS: Received {len(topics)} topics")
                
            except json.JSONDecodeError:
                # If JSON parsing fails, show raw text
                print("(Could not parse as JSON - showing raw response)")
                print(response.text)
                print(f"\n{'='*60}")
                print("✅ SUCCESS: Response received (could not parse JSON for summary)")
                
        else:
            print(f"❌ ERROR: Request failed with status {response.status_code}")
            print(f"\nFull Error Response:")
            print(f"{'='*60}")
            
            try:
                # Try to pretty print error response if it's JSON
                error_data = response.json()
                formatted_error = json.dumps(error_data, indent=2, ensure_ascii=False)
                print(formatted_error)
            except:
                # If not JSON, show raw text
                print(response.text)
                
            print(f"{'='*60}")
                
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend. Is it running?")
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("Usage: python3 quick_test.py [period] [sources...]")
        print("  period: 1d, 2d, or 1w (default: 1d)")
        print("  sources: Optional list of source URLs")
        print("")
        print("Examples:")
        print("  python3 quick_test.py")
        print("  python3 quick_test.py 1d")
        print("  python3 quick_test.py 1d https://t.me/cointelegraph")
        print("  python3 quick_test.py 2d https://t.me/binance https://t.me/ethereum")
        sys.exit(0)
    
    main() 