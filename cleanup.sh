#!/bin/bash

# News-Hack Development Cleanup Script
# This script removes database and log files, then reinitializes the database

echo "Starting cleanup process..."

# Remove database file
if [ -f sources.db ]; then
    echo "Removing database file..."
    rm sources.db
    echo "Database file removed."
else
    echo "Database file not found, skipping."
fi

# Remove log file
if [ -f log.log ]; then
    echo "Removing log file..."
    rm log.log
    echo "Log file removed."
else
    echo "Log file not found, skipping."
fi



# Initialize the database
echo "Initializing database..."
flask --app app.py initdb
echo "Database initialized."

echo "Cleanup completed successfully!" 