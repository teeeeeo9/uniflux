# Uniflux News Aggregator

Uniflux is a powerful news aggregation tool that helps you aggregate, summarize, and gain insights from multiple sources, including Telegram channels.

## Features

- **News Summarization**: Generate concise summaries of news from multiple sources
- **Topic Aggregation**: Group related news items into topics
- **Importance Rating**: Rate topics by importance
- **Financial Insights**: Generate actionable insights for financial decision-making
- **Telegram Integration**: Use your own Telegram channels export for summarization

## Using Telegram Export Feature

### Exporting Channels from Telegram

1. Open the Telegram app and click on **Settings** (⚙️)
2. Go to **Privacy and Security** → **Export Telegram Data**
3. Select **Export chats and channels list** (you don't need chat history)
4. Format: **JSON**
5. Click **Export** and download the file

### Uploading to Uniflux

1. Go to the Uniflux web interface
2. Switch to the "Telegram Export" tab
3. Upload your Telegram export JSON file
4. Uniflux will analyze and categorize your channels by topic
5. Select the channels you want to include in your summaries
6. Click "Generate Summaries from Telegram"

The app will then fetch and summarize content from your selected Telegram channels.

## Using Default Sources

If you prefer to use the default sources:

1. Switch to the "Default Sources" tab
2. Select categories or individual sources from the list
3. Choose a time period (1 day or 2 days)
4. Click "Generate Summaries"

## Technical Details

This application consists of:

- A Flask backend for data processing and API endpoints
- A React frontend for user interaction
- Integration with Gemini AI models for summarization and analysis
- SQLite database for storing messages and channel information

## Setup and Installation

See the installation guide in [INSTALL.md](INSTALL.md) for details on setting up the application.

## Environment Variables

The following environment variables are required:

- `GEMINI_API_KEY`: Your Google Gemini API key
- `TELEGRAM_API_ID`: Your Telegram API ID
- `TELEGRAM_API_HASH`: Your Telegram API Hash
- `TELEGRAM_PHONE_NUMBER`: Your Telegram phone number

## License

This project is proprietary software. All rights reserved. 