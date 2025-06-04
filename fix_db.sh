#!/bin/bash

# Script to apply the SQL fixes to the database
export PGPASSWORD="M0v3rGPT_2025!"
echo "Connecting to database and applying fixes..."
psql -h 127.0.0.1 -U movergptuser -d movergptdb -a -f fix_chatbot_configs.sql
unset PGPASSWORD

echo "SQL fixes applied. Restarting the application service."
sudo systemctl restart chatbot_platform

echo "Done! Check the application logs to verify the fix worked."
sudo journalctl -u chatbot_platform -n 20 