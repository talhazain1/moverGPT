#!/bin/bash

# Script to run database migrations

# Check if a specific migration was specified
if [ -z "$1" ]; then
    echo "Usage: ./run_migration.sh <migration_script_name>"
    echo "Example: ./run_migration.sh add_metadata_to_booking.py"
    echo "         ./run_migration.sh add_metadata_direct.py"
    exit 1
fi

MIGRATION_SCRIPT="$1"
SCRIPT_PATH="src/migrations/$MIGRATION_SCRIPT"

# Check if the migration script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Migration script '$SCRIPT_PATH' not found"
    exit 1
fi

# Load environment variables if .env file exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file"
    source .env
fi

# Check if DATABASE_URL is set for Flask-based migrations
if [[ "$MIGRATION_SCRIPT" != *"direct"* ]]; then
    if [ -z "$DATABASE_URL" ]; then
        echo "Warning: DATABASE_URL environment variable is not set"
        echo "This may cause issues for Flask-based migrations"
        echo "Consider using add_metadata_direct.py instead, which can prompt for credentials"
    fi
fi

# For direct migrations, check if psycopg2 is installed
if [[ "$MIGRATION_SCRIPT" == *"direct"* ]]; then
    echo "Checking for psycopg2 package..."
    python -c "import psycopg2" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "psycopg2 not found. Installing psycopg2-binary..."
        pip install psycopg2-binary
        if [ $? -ne 0 ]; then
            echo "Failed to install psycopg2-binary. Please install it manually:"
            echo "pip install psycopg2-binary"
            exit 1
        fi
    else
        echo "psycopg2 is already installed."
    fi
fi

# Run the migration script
echo "Running migration: $MIGRATION_SCRIPT"
python "$SCRIPT_PATH"

# Check if the migration was successful
if [ $? -eq 0 ]; then
    echo "Migration completed successfully"
else
    echo "Migration failed"
    exit 1
fi 