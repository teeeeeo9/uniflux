"""
TON Payment Processor
Handles payment creation, verification, and subscription management
"""
import sqlite3
import json
import uuid
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
import logging

from payment_config import (
    TON_NETWORK, TON_RPC_ENDPOINT, TON_API_KEY,
    PAYMENT_WALLET_ADDRESS, PAYMENT_AMOUNT_TON,
    PAYMENT_TIMEOUT_MINUTES, SUBSCRIPTION_DURATION_DAYS,
    SUBSCRIPTION_TIERS, PAYMENT_CHECK_INTERVAL_SECONDS
)
from config import DATABASE

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.db_path = DATABASE
        self.init_database()
    
    def init_database(self):
        """Initialize payment-related database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Read and execute schema
            with open('schema.sql', 'r') as f:
                schema = f.read()
                cursor.executescript(schema)
            
            conn.commit()
            conn.close()
            logger.info("Payment database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing payment database: {e}")
    
    def create_payment_request(self, telegram_user_id: str, telegram_username: str = None, 
                             subscription_tier: str = 'basic') -> Dict[str, Any]:
        """Create a new payment request"""
        try:
            # Validate subscription tier
            if subscription_tier not in SUBSCRIPTION_TIERS:
                raise ValueError(f"Invalid subscription tier: {subscription_tier}")
            
            tier_config = SUBSCRIPTION_TIERS[subscription_tier]
            payment_id = str(uuid.uuid4())
            amount = tier_config['price_ton']
            expires_at = datetime.now() + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert payment transaction
            cursor.execute("""
                INSERT INTO payment_transactions 
                (telegram_user_id, payment_id, amount, ton_address, status, network, expires_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """, (telegram_user_id, payment_id, amount, PAYMENT_WALLET_ADDRESS, TON_NETWORK, expires_at))
            
            conn.commit()
            conn.close()
            
            return {
                'payment_id': payment_id,
                'amount': amount,
                'wallet_address': PAYMENT_WALLET_ADDRESS,
                'network': TON_NETWORK,
                'expires_at': expires_at.isoformat(),
                'subscription_tier': subscription_tier,
                'duration_days': tier_config['duration_days']
            }
            
        except Exception as e:
            logger.error(f"Error creating payment request: {e}")
            raise
    
    def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Check the status of a payment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT telegram_user_id, amount, ton_address, tx_hash, status, network, 
                       created_at, confirmed_at, expires_at
                FROM payment_transactions 
                WHERE payment_id = ?
            """, (payment_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {'status': 'not_found'}
            
            telegram_user_id, amount, ton_address, tx_hash, status, network, created_at, confirmed_at, expires_at = row
            
            # Check if payment has expired
            if datetime.now() > datetime.fromisoformat(expires_at):
                if status == 'pending':
                    self.update_payment_status(payment_id, 'expired')
                    status = 'expired'
            
            return {
                'payment_id': payment_id,
                'telegram_user_id': telegram_user_id,
                'amount': amount,
                'ton_address': ton_address,
                'tx_hash': tx_hash,
                'status': status,
                'network': network,
                'created_at': created_at,
                'confirmed_at': confirmed_at,
                'expires_at': expires_at
            }
            
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def update_payment_status(self, payment_id: str, status: str, tx_hash: str = None):
        """Update payment status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if status == 'confirmed' and tx_hash:
                cursor.execute("""
                    UPDATE payment_transactions 
                    SET status = ?, tx_hash = ?, confirmed_at = ?
                    WHERE payment_id = ?
                """, (status, tx_hash, datetime.now(), payment_id))
            else:
                cursor.execute("""
                    UPDATE payment_transactions 
                    SET status = ?
                    WHERE payment_id = ?
                """, (status, payment_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Payment {payment_id} status updated to {status}")
            
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            raise
    
    def verify_payment_on_blockchain(self, payment_id: str) -> bool:
        """Verify payment on TON blockchain"""
        try:
            payment_info = self.check_payment_status(payment_id)
            if payment_info['status'] != 'pending':
                return payment_info['status'] == 'confirmed'
            
            # Get recent transactions for the wallet
            url = f"{TON_RPC_ENDPOINT}getTransactions"
            params = {
                'address': PAYMENT_WALLET_ADDRESS,
                'limit': 10,
                'archival': True
            }
            
            if TON_API_KEY:
                params['api_key'] = TON_API_KEY
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"Failed to fetch transactions: {response.status_code}")
                return False
            
            data = response.json()
            if not data.get('ok'):
                logger.error(f"TON API error: {data.get('error', 'Unknown error')}")
                return False
            
            transactions = data.get('result', [])
            expected_amount = payment_info['amount']
            
            # Check for matching transaction
            for tx in transactions:
                if tx.get('in_msg') and tx['in_msg'].get('value'):
                    # Convert nanograms to TON
                    tx_amount = int(tx['in_msg']['value']) / 1e9
                    
                    # Check if amount matches (with small tolerance for fees)
                    if abs(tx_amount - expected_amount) < 0.01:
                        tx_hash = tx.get('transaction_id', {}).get('hash', '')
                        
                        # Update payment status
                        self.update_payment_status(payment_id, 'confirmed', tx_hash)
                        
                        # Create or update subscription
                        self.create_subscription(payment_info['telegram_user_id'], expected_amount, tx_hash)
                        
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying payment on blockchain: {e}")
            return False
    
    def create_subscription(self, telegram_user_id: str, payment_amount: float, tx_hash: str):
        """Create or update user subscription"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Determine subscription tier based on payment amount
            subscription_tier = 'basic'
            for tier, config in SUBSCRIPTION_TIERS.items():
                if abs(payment_amount - config['price_ton']) < 0.01:
                    subscription_tier = tier
                    break
            
            tier_config = SUBSCRIPTION_TIERS[subscription_tier]
            expiry_date = datetime.now() + timedelta(days=tier_config['duration_days'])
            
            # Check if user already has subscription
            cursor.execute("""
                SELECT id, expiry_date FROM user_subscriptions 
                WHERE telegram_user_id = ?
            """, (telegram_user_id,))
            
            existing = cursor.fetchone()
            
            if existing:
                # Extend existing subscription
                current_expiry = datetime.fromisoformat(existing[1])
                if current_expiry > datetime.now():
                    # Extend from current expiry
                    new_expiry = current_expiry + timedelta(days=tier_config['duration_days'])
                else:
                    # Start from now
                    new_expiry = expiry_date
                
                cursor.execute("""
                    UPDATE user_subscriptions 
                    SET subscription_tier = ?, payment_amount = ?, payment_tx_hash = ?,
                        payment_date = ?, expiry_date = ?, is_active = 1, updated_at = ?
                    WHERE telegram_user_id = ?
                """, (subscription_tier, payment_amount, tx_hash, datetime.now(), 
                      new_expiry, datetime.now(), telegram_user_id))
            else:
                # Create new subscription
                cursor.execute("""
                    INSERT INTO user_subscriptions 
                    (telegram_user_id, subscription_tier, payment_amount, payment_tx_hash,
                     payment_date, expiry_date, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (telegram_user_id, subscription_tier, payment_amount, tx_hash,
                      datetime.now(), expiry_date))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Subscription created/updated for user {telegram_user_id}")
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise
    
    def check_user_subscription(self, telegram_user_id: str) -> Dict[str, Any]:
        """Check if user has active subscription"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT subscription_tier, payment_amount, payment_date, expiry_date, 
                       is_active, created_at
                FROM user_subscriptions 
                WHERE telegram_user_id = ? AND is_active = 1
            """, (telegram_user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {'has_subscription': False}
            
            subscription_tier, payment_amount, payment_date, expiry_date, is_active, created_at = row
            expiry_datetime = datetime.fromisoformat(expiry_date)
            
            # Check if subscription is still valid
            if expiry_datetime > datetime.now():
                return {
                    'has_subscription': True,
                    'subscription_tier': subscription_tier,
                    'payment_amount': payment_amount,
                    'payment_date': payment_date,
                    'expiry_date': expiry_date,
                    'days_remaining': (expiry_datetime - datetime.now()).days,
                    'created_at': created_at
                }
            else:
                # Subscription expired, deactivate it
                self.deactivate_subscription(telegram_user_id)
                return {'has_subscription': False, 'expired': True}
            
        except Exception as e:
            logger.error(f"Error checking user subscription: {e}")
            return {'has_subscription': False, 'error': str(e)}
    
    def deactivate_subscription(self, telegram_user_id: str):
        """Deactivate expired subscription"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_subscriptions 
                SET is_active = 0, updated_at = ?
                WHERE telegram_user_id = ?
            """, (datetime.now(), telegram_user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error deactivating subscription: {e}")

# Global payment processor instance
payment_processor = PaymentProcessor() 