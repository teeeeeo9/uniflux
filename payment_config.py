"""
TON Payment Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# TON Network Configuration
TON_NETWORK = os.getenv('TON_NETWORK', 'testnet')  # 'mainnet' or 'testnet'
TON_RPC_ENDPOINT = os.getenv('TON_RPC_ENDPOINT', 'https://testnet.toncenter.com/api/v2/')
TON_API_KEY = os.getenv('TON_API_KEY', '')  # Optional API key for TonCenter

# Payment Configuration
PAYMENT_WALLET_ADDRESS = os.getenv('PAYMENT_WALLET_ADDRESS', '')  # Your receiving wallet address
PAYMENT_AMOUNT_TON = float(os.getenv('PAYMENT_AMOUNT_TON', '0.1'))  # Amount in TON for subscription
PAYMENT_TIMEOUT_MINUTES = int(os.getenv('PAYMENT_TIMEOUT_MINUTES', '30'))  # Payment timeout
SUBSCRIPTION_DURATION_DAYS = int(os.getenv('SUBSCRIPTION_DURATION_DAYS', '30'))  # Subscription duration

# TON Connect Configuration
TON_CONNECT_MANIFEST_URL = os.getenv('TON_CONNECT_MANIFEST_URL', 'https://your-domain.com/tonconnect-manifest.json')

# Payment monitoring
PAYMENT_CHECK_INTERVAL_SECONDS = int(os.getenv('PAYMENT_CHECK_INTERVAL_SECONDS', '10'))
PAYMENT_CONFIRMATION_BLOCKS = int(os.getenv('PAYMENT_CONFIRMATION_BLOCKS', '1'))

# Subscription tiers
SUBSCRIPTION_TIERS = {
    'basic': {
        'price_ton': PAYMENT_AMOUNT_TON,
        'duration_days': SUBSCRIPTION_DURATION_DAYS,
        'features': ['unlimited_summaries', 'basic_insights']
    },
    'premium': {
        'price_ton': PAYMENT_AMOUNT_TON * 2,
        'duration_days': SUBSCRIPTION_DURATION_DAYS,
        'features': ['unlimited_summaries', 'advanced_insights', 'priority_support']
    }
}

# Validation
if not PAYMENT_WALLET_ADDRESS:
    print("WARNING: PAYMENT_WALLET_ADDRESS not set in environment variables")

print(f"TON Payment Config: Network={TON_NETWORK}, Amount={PAYMENT_AMOUNT_TON} TON, Duration={SUBSCRIPTION_DURATION_DAYS} days") 