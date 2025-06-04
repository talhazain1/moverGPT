#!/bin/bash

# This script connects to PostgreSQL using explicit host parameter
export PGPASSWORD="M0v3rGPT_2025!"
psql -h 127.0.0.1 -U movergptuser -d movergptdb -a -f create_chatbot_configs.sql
unset PGPASSWORD

echo "Script execution completed" 