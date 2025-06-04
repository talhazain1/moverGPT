#!/bin/bash
# Script to run the API key fix

# Change to the script directory
cd "$(dirname "$0")"

# Set environment variables if needed
export DATABASE_URL="postgresql://myuser@localhost:5432/chatbotdb"

# Run the fix script
echo "Running API key fix script..."
python fix_api_key_issues.py

# Check if the script was successful
if [ $? -eq 0 ]; then
  echo "API key fix completed successfully."
  exit 0
else
  echo "API key fix failed. Check the logs for details."
  exit 1
fi 