#!/bin/bash

# Script to fix the knowledge_base column data type
export PGPASSWORD="M0v3rGPT_2025!"
echo "Fixing knowledge_base column data type..."
psql -h 127.0.0.1 -U movergptuser -d movergptdb -a -f fix_knowledge_base.sql
unset PGPASSWORD

echo "Column fixed. Restarting the application service."
sudo systemctl restart chatbot_platform

echo "Done! Waiting 5 seconds for the service to restart..."
sleep 5

echo "Checking the application logs:"
sudo journalctl -u chatbot_platform -n 20 