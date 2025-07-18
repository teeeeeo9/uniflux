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
    user_id TEXT DEFAULT NULL, -- User identifier for user-specific sources
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

-- User subscriptions table for TON payment-based access
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id TEXT NOT NULL UNIQUE, -- Telegram user ID from WebApp
    telegram_username TEXT, -- Optional telegram username
    subscription_tier TEXT NOT NULL DEFAULT 'basic', -- 'basic', 'premium', etc.
    payment_amount REAL NOT NULL, -- Amount paid in TON
    payment_tx_hash TEXT, -- TON transaction hash
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP NOT NULL, -- When subscription expires
    is_active INTEGER DEFAULT 1, -- 1 = active, 0 = inactive
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment transactions table for tracking all payments
CREATE TABLE IF NOT EXISTS payment_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id TEXT NOT NULL,
    payment_id TEXT NOT NULL UNIQUE, -- Unique payment identifier
    amount REAL NOT NULL, -- Amount in TON
    ton_address TEXT NOT NULL, -- TON wallet address that made payment
    tx_hash TEXT, -- Transaction hash on TON blockchain
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'confirmed', 'failed', 'expired'
    network TEXT NOT NULL DEFAULT 'testnet', -- 'mainnet' or 'testnet'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP, -- When payment was confirmed
    expires_at TIMESTAMP NOT NULL -- When payment expires if not confirmed
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_link_summaries_url ON link_summaries(url);
CREATE INDEX IF NOT EXISTS idx_messages_source_url ON messages(source_url);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_telegram_user_id ON user_subscriptions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expiry_date ON user_subscriptions(expiry_date);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_telegram_user_id ON payment_transactions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_payment_id ON payment_transactions(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON payment_transactions(status);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_tx_hash ON payment_transactions(tx_hash); 