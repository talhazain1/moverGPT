#!/bin/bash

# Script to deploy the moving parameters fix to production
echo "=== Deploying fix for moving parameters routes ==="

# Make sure we're in the correct directory
cd "$(dirname "$0")" || exit

# Pull latest changes if using git
if [ -d .git ]; then
  echo "Pulling latest changes from git..."
  git pull
fi

# Restart the Flask app using your production method
# If using gunicorn, systemd, supervisor, etc.
# Uncomment the appropriate line:

# For systemd:
# sudo systemctl restart movergpt

# For supervisor:
# sudo supervisorctl restart movergpt

# For gunicorn directly:
# pkill gunicorn
# gunicorn -b 0.0.0.0:5006 src.main:app --daemon

echo "=== Deployment complete! ==="
echo "You may need to manually restart your production server if none of the above methods apply."
echo "Check the logs to confirm the new routes are registered." 