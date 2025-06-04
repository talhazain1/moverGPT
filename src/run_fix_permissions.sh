#!/bin/bash
# Run Moving Quote Permissions Fix Script
# This script runs the fix_moving_quote_permissions.py script to grant the necessary database permissions

# Set working directory to the script's directory
cd "$(dirname "$0")"

echo "=================================================="
echo "Starting database permissions fix for moving_quote_requests"
echo "=================================================="

# Run the Python script
python fix_moving_quote_permissions.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "=================================================="
    echo "✅ Permission fix completed successfully!"
    echo "=================================================="
else
    echo "=================================================="
    echo "❌ Permission fix failed with exit code: $exit_code"
    echo "=================================================="
    echo "Check the logs for more details."
fi

# Return the exit code from the Python script
exit $exit_code 