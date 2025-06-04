#!/bin/bash

# Script to apply the complete SQL fix to the database
export PGPASSWORD="M0v3rGPT_2025!"
echo "Connecting to database and applying complete fix..."
psql -h 127.0.0.1 -U movergptuser -d movergptdb -a -f fix_chatbot_configs_complete.sql
unset PGPASSWORD

echo "Complete SQL fix applied. Restarting the application service."
sudo systemctl restart chatbot_platform

echo "Done! Waiting 5 seconds for the service to restart..."
sleep 5

echo "Checking the application logs:"
sudo journalctl -u chatbot_platform -n 20 