# Backend Test Scripts

This directory contains scripts to test the backend API endpoints.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure the backend is running:
```bash
# From the project root
python app.py
```

## Scripts

### `test_summaries.py`
Comprehensive test script that runs multiple test cases against the `/summaries` endpoint.

**Usage:**
```bash
python test_summaries.py
```

**Features:**
- Tests different time periods (1d, 2d, 1w)
- Tests with and without source filters
- Checks backend health before running tests
- Provides detailed output with timing and results
- Includes example Telegram channel sources

### `quick_test.py`
Simple script for quick testing with command line arguments.

**Usage:**
```bash
python quick_test.py [period] [sources...]
```

**Examples:**
```bash
# Basic test with default 1 day period
python quick_test.py

# Test with specific period
python quick_test.py 2d

# Test with specific sources
python quick_test.py 1d https://t.me/cointelegraph

# Test with multiple sources
python quick_test.py 1d https://t.me/binance https://t.me/ethereum

# Show help
python quick_test.py --help
```

## Expected Output

Both scripts will:
1. Check if the backend is running
2. Make requests to the `/summaries` endpoint
3. Display response details including:
   - Response status and timing
   - Number of topics returned
   - Topic details (name, importance, message count, category)
   - Insights if available

## API Parameters

The `/summaries` endpoint accepts:
- `period`: Time period to analyze (`1d`, `2d`, `1w`)
- `sources`: Comma-separated list of source URLs (optional)

## Notes

- The backend must be running on `http://localhost:5000`
- These scripts use example Telegram channel URLs that may not exist in your database
- Response times can vary depending on the amount of data being processed
- The scripts include proper error handling for common issues (timeout, connection errors) 