#!/bin/bash

set -e

echo "---- Creating systemd service for Ghost Host ----"
cat <<'EOF' > /etc/systemd/system/ghosthost.service
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
EOF

echo "---- Creating systemd override for getty auto-login ----"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat <<'EOF' > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ghosthost --noclear %I $TERM
EOF

echo "---- Reloading systemd, enabling and starting ghosthost.service ----"
systemctl daemon-reload
systemctl enable ghosthost.service
systemctl restart ghosthost.service

echo "---- Setup complete! ----"
echo "Ghost Host will now auto-start at boot and auto-login as 'ghosthost' on tty1."
echo "You can check the service status with: sudo systemctl status ghosthost.service"
echo "You can check logs with: tail -f /home/ghosthost/startup.log"
