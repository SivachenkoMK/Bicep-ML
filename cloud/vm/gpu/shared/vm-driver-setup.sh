#!/bin/bash

# Configuration
LOG_FILE="/var/log/setup-script.log"
NVIDIA_DRIVER_VERSION="535"

echo "$(date) - Installing Nvidia drivers." >> $LOG_FILE
sudo apt-get update >> $LOG_FILE 2>&1
sudo apt-get install -y nvidia-driver-$NVIDIA_DRIVER_VERSION >> $LOG_FILE 2>&1
if [ $? -eq 0 ]; then
  echo "$(date) - Nvidia driver installed successfully, rebooting." >> $LOG_FILE
  sudo reboot
else
  echo "$(date) - Nvidia driver installation failed." >> $LOG_FILE
  exit 1
fi