#!/bin/bash

# News-Hack Environment Switcher
# This script helps you switch between development and production environments

# Check if an argument was provided
if [ -z "$1" ]; then
    echo "Usage: $0 [dev|prod]"
    echo "  dev  - Switch to development environment"
    echo "  prod - Switch to production environment"
    exit 1
fi

# Current .env file
ENV_FILE=".env"

if [ "$1" == "dev" ]; then
    # Switch to development environment
    echo "Switching to development environment..."
    # Update the ENV line in the .env file
    sed -i 's/^ENV=.*/ENV=development/' $ENV_FILE
    echo "Environment switched to development"
    echo "Database: sources_dev.db"
    echo "Log file: log_dev.log"
    echo "Telegram session: telegram_session_dev"
elif [ "$1" == "prod" ]; then
    # Switch to production environment
    echo "Switching to production environment..."
    # Warn the user before switching
    echo "WARNING: This will switch to the production environment!"
    echo "Are you sure you want to continue? (y/n)"
    read confirm
    if [ "$confirm" != "y" ]; then
        echo "Operation cancelled."
        exit 0
    fi
    
    # Update the ENV line in the .env file
    sed -i 's/^ENV=.*/ENV=production/' $ENV_FILE
    echo "Environment switched to production"
    echo "Database: sources.db"
    echo "Log file: log.log" 
    echo "Telegram session: telegram_session"
else
    echo "Invalid argument: $1"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

echo "Done. You can run 'python config.py' to verify the current configuration." 