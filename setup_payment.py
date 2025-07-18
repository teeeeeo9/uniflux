#!/usr/bin/env python3
"""
Setup script for TON payment system
"""
import os
import sqlite3
from pathlib import Path

def setup_database():
    """Initialize the database with payment tables"""
    print("Setting up database...")
    
    # Read schema file
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        print("❌ schema.sql not found!")
        return False
    
    try:
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        # Connect to database
        conn = sqlite3.connect('sources.db')
        cursor = conn.cursor()
        
        # Execute schema
        cursor.executescript(schema)
        conn.commit()
        conn.close()
        
        print("✅ Database initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def create_env_template():
    """Create .env template file"""
    env_template = """# Telegram Bot Configuration
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id

# Database Configuration
DATABASE=sources.db

# TON Payment Configuration
TON_NETWORK=testnet
TON_RPC_ENDPOINT=https://testnet.toncenter.com/api/v2/
TON_API_KEY=your_ton_api_key_optional
PAYMENT_WALLET_ADDRESS=your_receiving_wallet_address
PAYMENT_AMOUNT_TON=0.1
PAYMENT_TIMEOUT_MINUTES=30
SUBSCRIPTION_DURATION_DAYS=30

# TON Connect Configuration
TON_CONNECT_MANIFEST_URL=https://your-domain.com/tonconnect-manifest.json

# Payment Processing
PAYMENT_CHECK_INTERVAL_SECONDS=10
PAYMENT_CONFIRMATION_BLOCKS=1
"""
    
    env_path = Path(__file__).parent / ".env.example"
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_template)
        
        print("✅ .env.example created")
        print("📝 Please copy .env.example to .env and configure your settings")
        return True
        
    except Exception as e:
        print(f"❌ Error creating .env.example: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")
    
    required_packages = [
        ('pytoniq-core', 'pytoniq_core'),
        ('requests', 'requests'),
        ('flask', 'flask'),
        ('flask-cors', 'flask_cors'),
        ('python-dotenv', 'dotenv')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print(f"💡 Install with: pip install {' '.join(missing_packages)}")
        return False
    else:
        print("✅ All dependencies installed")
        return True

def main():
    """Main setup function"""
    print("🚀 Setting up TON Payment System for Uniflux")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Setup failed: Missing dependencies")
        return
    
    # Setup database
    if not setup_database():
        print("\n❌ Setup failed: Database initialization error")
        return
    
    # Create environment template
    if not create_env_template():
        print("\n❌ Setup failed: Could not create .env template")
        return
    
    print("\n✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Copy .env.example to .env")
    print("2. Configure your TON wallet address and Telegram bot settings in .env")
    print("3. Get TON testnet tokens from https://t.me/testgiver_ton_bot")
    print("4. Start the Flask backend: python app.py")
    print("5. Start the frontend: cd tma-example && npm run dev")
    print("\n🎉 Your TON payment system is ready!")

if __name__ == "__main__":
    main() 