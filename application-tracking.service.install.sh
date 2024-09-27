#!/bin/sh

sudo mkdir -p /var/tracking/applications

# sudo cp application-tracking.service.sh /usr/bin/

sudo cat <<SERVICE_DEF > /etc/systemd/system/application-tracking.service
[Unit]
Description=Application Tracking Service

[Service]
ExecStart=/home/alfu64/Development/track-applications/./application-tracking.service.sh
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE_DEF


sudo systemctl enable application-tracking.service
sudo systemctl start application-tracking.service