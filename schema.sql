-- Schema for sources.db

-- Store link summaries to avoid re-parsing
CREATE TABLE IF NOT EXISTS link_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    summary_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store reference to all sources (for analytics)
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '', -- Human-readable name for the source
    source_type TEXT NOT NULL DEFAULT 'telegram', -- Type of source: 'telegram', 'rss', etc.
    category TEXT DEFAULT 'Uncategorized',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store messages from various sources (Telegram, etc.)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,  -- URL of the source (e.g., https://t.me/channel)
    source_type TEXT NOT NULL, -- Type of source (e.g., 'telegram', 'twitter', etc.)
    channel_id TEXT,          -- Channel identifier (e.g., telegram channel id)
    message_id TEXT,          -- Message identifier (e.g., telegram message id)
    date TIMESTAMP,           -- Date of the message
    data TEXT,                -- Text content of the message
    summarized_links_content TEXT, -- JSON string containing links and their summaries
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0,
    UNIQUE(source_type, channel_id, message_id) -- Prevent duplicates
);

-- Summaries table stores generated summaries
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    importance INTEGER,
    message_ids TEXT, -- Comma-separated list of message IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feedback table stores user feedback
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL, -- 'feedback', 'question', or 'bug'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Subscribers table stores email subscribers
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    source TEXT, -- Indicates where they subscribed from ('main', 'custom-sources', etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_link_summaries_url ON link_summaries(url);
CREATE INDEX IF NOT EXISTS idx_messages_source_url ON messages(source_url);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date); 