#!/bin/bash

# News-Hack Cleanup Script
# This script removes database and log files, then reinitializes the database
# It supports both development and production environments

# Default to development if ENV is not set
ENV=${ENV:-"development"}

echo "Starting cleanup process for $ENV environment..."

# Set file paths based on environment
if [ "$ENV" == "production" ]; then
    DATABASE="sources.db"
    LOG_FILE="log.log"
    TELEGRAM_SESSION="telegram_session"
    echo "Using production files: $DATABASE, $LOG_FILE, $TELEGRAM_SESSION"
else
    DATABASE="sources_dev.db"
    LOG_FILE="log_dev.log"
    TELEGRAM_SESSION="telegram_session_dev"
    echo "Using development files: $DATABASE, $LOG_FILE, $TELEGRAM_SESSION"
fi

# Remove database file
if [ -f $DATABASE ]; then
    echo "Removing database file $DATABASE..."
    rm $DATABASE
    echo "Database file removed."
else
    echo "Database file $DATABASE not found, skipping."
fi

# Remove log file
if [ -f $LOG_FILE ]; then
    echo "Removing log file $LOG_FILE..."
    rm $LOG_FILE
    echo "Log file removed."
else
    echo "Log file $LOG_FILE not found, skipping."
fi



# Initialize the database
echo "Initializing database for $ENV environment..."
ENV=$ENV flask --app app.py initdb
echo "Database initialized."

echo "Cleanup completed successfully for $ENV environment!" 