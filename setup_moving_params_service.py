#!/usr/bin/env python3
import os
import sys
import time
import subprocess

def main():
    """Set up a dedicated moving parameters service"""
    print("🔧 Setting up dedicated moving parameters service...")

    # Path to the dedicated_endpoint.py file on the server
    dedicated_path = '/home/movergpt-app/dedicated_endpoint.py'
    
    # Copy script to server location
    print(f"📝 Copying dedicated_endpoint.py to {dedicated_path}")
    with open('dedicated_endpoint.py', 'r') as f:
        content = f.read()
    
    with open(dedicated_path, 'w') as f:
        f.write(content)
    
    # Make it executable
    os.chmod(dedicated_path, 0o755)
    print("✅ Made dedicated_endpoint.py executable")
    
    # Create a new systemd service file
    service_content = """[Unit]
Description=MoverGPT Moving Parameters Service
After=network.target

[Service]
User=root
WorkingDirectory=/home/movergpt-app
Environment="PYTHONUNBUFFERED=1"
Environment="FLASK_DEBUG=0"
ExecStart=/home/movergpt-app/venv/bin/gunicorn -b 0.0.0.0:5005 dedicated_endpoint:app --workers=3
StandardOutput=journal
StandardError=journal
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    
    # Write the service file
    service_path = '/etc/systemd/system/moving-params.service'
    with open(service_path, 'w') as f:
        f.write(service_content)
    
    print(f"✅ Created systemd service file at {service_path}")
    
    # Reload systemd daemon
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
    print("✅ Reloaded systemd daemon")
    
    # Stop the problematic service
    subprocess.run(['sudo', 'systemctl', 'stop', 'chatbot_platform'])
    print("✅ Stopped chatbot_platform service")
    
    # Enable and start the new service
    subprocess.run(['sudo', 'systemctl', 'enable', 'moving-params'])
    subprocess.run(['sudo', 'systemctl', 'start', 'moving-params'])
    print("✅ Started moving-params service")
    
    # Check the status
    status = subprocess.run(['sudo', 'systemctl', 'status', 'moving-params'], capture_output=True, text=True)
    print("\n=== Service Status ===")
    print(status.stdout)
    
    print("\n✅ Setup complete!")
    print("\nNow you can test the endpoint:")
    print("   https://app.movergpt.com/api/companies/7/moving-parameters")
    print("\nIf you need to manually restart the service:")
    print("   sudo systemctl restart moving-params")
    print("\nTo check the logs:")
    print("   sudo journalctl -u moving-params -f")

if __name__ == "__main__":
    main() 