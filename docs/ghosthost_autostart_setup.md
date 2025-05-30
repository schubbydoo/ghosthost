# Ghost Host Auto-Start Setup Guide

This guide explains how to configure your Raspberry Pi to automatically start the Ghost Host system (including the web interface, AP mode manager, and main animatronic logic) upon boot, with auto-login for the `ghosthost` user.

---

## 1. Prerequisites
- The `ghosthost` user exists and owns the project files in `/home/ghosthost`.
- The Python virtual environment is set up at `/home/ghosthost/venv`.
- The main startup script is at `/home/ghosthost/startup.sh` and is executable.

---

## 2. Create the Startup Script

Ensure `/home/ghosthost/startup.sh` contains:

```bash
#!/bin/bash

LOGFILE="/home/ghosthost/startup.log"
echo "Starting Ghost Host Project at $(date)" >> "$LOGFILE" 2>&1

cd /home/ghosthost || { echo "Failed to cd to /home/ghosthost" >> "$LOGFILE" 2>&1; exit 1; }
source venv/bin/activate
echo "Virtual environment activated." >> "$LOGFILE" 2>&1

mkdir -p /home/ghosthost/logs

# Start ap_mode_manager.py
python3 /home/ghosthost/web_interface/src/ap_mode_manager.py >> /home/ghosthost/logs/ap_mode_manager.log 2>&1 &

# Start Flask web interface
python3 /home/ghosthost/web_interface/app.py >> /home/ghosthost/logs/web_interface.log 2>&1 &

# Start main.py
python3 /home/ghosthost/main.py >> /home/ghosthost/logs/main.log 2>&1 &

echo "All Ghost Host processes started at $(date)" >> "$LOGFILE" 2>&1

wait
```

Make it executable:
```bash
chmod +x /home/ghosthost/startup.sh
```

---

## 3. Create the Systemd Service

Create `/etc/systemd/system/ghosthost.service` with:

```ini
[Unit]
Description=Ghost Host Startup Service
After=network.target

[Service]
Type=simple
User=ghosthost
WorkingDirectory=/home/ghosthost
ExecStart=/home/ghosthost/startup.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 4. Enable Auto-Login for ghosthost on tty1

Create `/etc/systemd/system/getty@tty1.service.d/override.conf` with:

```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ghosthost --noclear %I $TERM
```

---

## 5. Enable and Start the Service

Reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ghosthost.service
sudo systemctl start ghosthost.service
```

---

## 6. Reboot and Test

Reboot your Pi:
```bash
sudo reboot
```

After reboot:
- The `ghosthost` user should auto-login on tty1.
- The Ghost Host system should start automatically.
- Logs are available in `/home/ghosthost/logs/` and `/home/ghosthost/startup.log`.

Check service status:
```bash
sudo systemctl status ghosthost.service
```

---

## 7. Troubleshooting
- Ensure all paths and permissions are correct.
- Check logs in `/home/ghosthost/logs/` and `/home/ghosthost/startup.log` for errors.
- Use `sudo journalctl -u ghosthost.service` for systemd logs.

---

**This setup ensures Ghost Host is fully operational and hands-off after every boot!** 