#!/bin/bash
# Script to fix dashboard metrics and API 500 errors

# Set error handling
set -e
set -o pipefail

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting dashboard metrics fix script${NC}"

# Check if we're in the backend directory
if [ ! -d "src" ]; then
    echo -e "${RED}Error: This script must be run from the backend directory.${NC}"
    echo -e "${YELLOW}Please change to the backend directory and try again.${NC}"
    exit 1
fi

# Check database connection
echo -e "${GREEN}Checking database connection...${NC}"
PGPASSWORD="M0v3rGPT_2025!" psql -U movergptuser -h 127.0.0.1 -d movergptdb -c "SELECT version();" || {
    echo -e "${RED}Error: Could not connect to database. Please check your credentials.${NC}"
    exit 1
}

# Backup the main.py file before making changes
echo -e "${GREEN}Creating backup of main.py...${NC}"
cp -f src/main.py src/main.py.bak

# Backup fix_dashboard_issues.py if it exists
if [ -f "src/fix_dashboard_issues.py" ]; then
    echo -e "${GREEN}Creating backup of fix_dashboard_issues.py...${NC}"
    cp -f src/fix_dashboard_issues.py src/fix_dashboard_issues.py.bak
fi

# Run table check script if it exists
if [ -f "src/check_metrics_tables.py" ]; then
    echo -e "${GREEN}Checking database tables...${NC}"
    python3 src/check_metrics_tables.py
fi

# Run chat sessions fix if it exists
if [ -f "src/fix_chat_sessions.py" ]; then
    echo -e "${GREEN}Fixing chat_sessions table if needed...${NC}"
    python3 src/fix_chat_sessions.py
fi

# Run metrics fix if it exists
if [ -f "src/fix_chatbot_metrics.py" ]; then
    echo -e "${GREEN}Testing metrics queries...${NC}"
    python3 src/fix_chatbot_metrics.py
fi

# Update the updated fix_dashboard_issues.py file
echo -e "${GREEN}Updating dashboard fix implementation...${NC}"
# Copy from updated file or create it if needed
if [ ! -f "src/fix_dashboard_issues.py" ]; then
    echo -e "${YELLOW}fix_dashboard_issues.py not found. Creating it...${NC}"
    cp $(dirname "$0")/src/fix_dashboard_issues.py.bak $(dirname "$0")/src/fix_dashboard_issues.py 2>/dev/null || {
        echo -e "${RED}Could not copy fix_dashboard_issues.py. Please check the files.${NC}"
    }
fi

# Fix the duplicate endpoint issue in main.py
echo -e "${GREEN}Checking for endpoint conflicts in main.py...${NC}"

# Check for duplicate get_moving_quote_requests functions
if grep -q "app.add_url_rule.*companies/moving-quote-requests.*get_moving_quote_requests" src/main.py && \
   grep -q "companies_routes_bp.*url_prefix=\"/api/companies\"" src/main.py; then
    echo -e "${YELLOW}Found potential endpoint conflict. Resolving...${NC}"
    
    # Remove any direct route definitions that conflict with the blueprint
    sed -i '/app.add_url_rule.*companies\/moving-quote-requests.*get_moving_quote_requests/d' src/main.py
    
    echo -e "${GREEN}Cleaned up conflicting route definitions.${NC}"
fi

# Add fix_dashboard_issues import to main.py if not already there
if ! grep -q "from fix_dashboard_issues import fix_dashboard_issues" src/main.py; then
    echo -e "${YELLOW}Adding fix_dashboard_issues import to main.py...${NC}"
    cat >> src/main.py << 'EOL'

# Apply dashboard fixes to ensure all endpoints return 200 status
try:
    from fix_dashboard_issues import fix_dashboard_issues
    fix_dashboard_issues(app, db)
    print("Dashboard fixes applied successfully!")
except ImportError:
    print("Dashboard fixes not applied - fix_dashboard_issues.py not found.")
    print("If you're having issues with the dashboard, run:")
    print("python src/fix_chat_sessions.py && python src/fix_chatbot_metrics.py")
EOL
    echo -e "${GREEN}Added fix_dashboard_issues import to main.py${NC}"
fi

# Restart the application
echo -e "${GREEN}Fixes have been applied. Would you like to restart the application? (y/n)${NC}"
read -r answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Restarting application...${NC}"
    if [ -f /etc/systemd/system/chatbot_platform.service ]; then
        sudo systemctl restart chatbot_platform
        echo -e "${GREEN}Application restarted via systemd.${NC}"
    else
        echo -e "${YELLOW}No systemd service found. Please restart the application manually.${NC}"
    fi
fi

echo -e "${GREEN}Script completed. Dashboard metrics should now be working correctly.${NC}"
echo -e "${YELLOW}Please check logs for any remaining errors after restart.${NC}"
echo -e "${GREEN}To verify the fix, visit the dashboard and check if metrics, support tickets, and quote requests are loading.${NC}" 