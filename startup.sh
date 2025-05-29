#!/bin/bash

LOGFILE="/home/ghosthost/startup.log"
echo "Starting Ghost Host Project at $(date)" >> "$LOGFILE" 2>&1

cd /home/ghosthost || { echo "Failed to cd to /home/ghosthost" >> "$LOGFILE" 2>&1; exit 1; }
source venv/bin/activate
echo "Virtual environment activated." >> "$LOGFILE" 2>&1

mkdir -p /home/ghosthost/logs

# Start ap_mode_manager.py
python3 /home/ghosthost/src/network_management/ap_mode_manager.py >> /home/ghosthost/logs/ap_mode_manager.log 2>&1 &

# Start Flask web interface
python3 /home/ghosthost/web_interface/app.py >> /home/ghosthost/logs/web_interface.log 2>&1 &

# Start main.py
python3 /home/ghosthost/main.py >> /home/ghosthost/logs/main.log 2>&1 &

echo "All Ghost Host processes started at $(date)" >> "$LOGFILE" 2>&1

wait 