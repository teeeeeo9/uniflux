-- Schema for sources.db

-- Store predefined source links
CREATE TABLE IF NOT EXISTS predefined_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store user-added source links
CREATE TABLE IF NOT EXISTS user_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
    UNIQUE(source_type, channel_id, message_id) -- Prevent duplicates
);

-- Store user interaction data for debugging
CREATE TABLE IF NOT EXISTS user_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_identifier TEXT NOT NULL, -- IP address or other identifier
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_type TEXT NOT NULL, -- Type of request made
    time_period TEXT, -- 1d, 1week, etc.
    success BOOLEAN NOT NULL DEFAULT 0,
    response_text TEXT -- Text returned to the user
);

-- Store the relationship between user interactions and the sources they requested
CREATE TABLE IF NOT EXISTS interaction_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    FOREIGN KEY (interaction_id) REFERENCES user_interactions(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_link_summaries_url ON link_summaries(url);
CREATE INDEX IF NOT EXISTS idx_user_interactions_timestamp ON user_interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_source_url ON messages(source_url);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date); 