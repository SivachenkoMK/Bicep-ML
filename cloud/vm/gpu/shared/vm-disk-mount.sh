#!/bin/bash

# Configuration
MOUNT_POINT="/mnt/data"
LOG_FILE="/var/log/setup-script.log"
DATA_DISK="/dev/sdc"
PARTITION="${DATA_DISK}1"

# Start Logging
sudo touch $LOG_FILE && sudo chmod 644 $LOG_FILE
echo "$(date) - Starting data disk setup" | tee -a $LOG_FILE

# Check if the disk is available
if [ ! -b "$DATA_DISK" ]; then
    echo "$(date) - $DATA_DISK not found. Exiting." | tee -a $LOG_FILE
    exit 1
fi

echo "$(date) - Detected data disk: $DATA_DISK" | tee -a $LOG_FILE

# Check if the disk has any partition
if ! lsblk -no PARTTYPE $DATA_DISK | grep -q .; then
    echo "$(date) - No partitions found. Partitioning $DATA_DISK." | tee -a $LOG_FILE
    sudo parted $DATA_DISK --script mklabel gpt mkpart primary ext4 0% 100%
    sudo partprobe $DATA_DISK
    sudo udevadm settle
else
    echo "$(date) - Partitions detected on $DATA_DISK. Skipping partitioning." | tee -a $LOG_FILE
fi

# Verify the partition exists
if [ ! -e "$PARTITION" ]; then
    echo "$(date) - Partition $PARTITION does not exist after partitioning attempt. Retrying partition initialization." | tee -a $LOG_FILE
    sudo partprobe $DATA_DISK
    sudo udevadm settle
    if [ ! -e "$PARTITION" ]; then
        echo "$(date) - Failed to detect partition $PARTITION. Exiting." | tee -a $LOG_FILE
        exit 1
    fi
fi

# Check filesystem
if ! sudo blkid $PARTITION &>/dev/null; then
    echo "$(date) - No filesystem detected. Formatting the partition: $PARTITION" | tee -a $LOG_FILE
    sudo mkfs.ext4 $PARTITION
elif ! sudo fsck -n $PARTITION &>/dev/null; then
    echo "$(date) - Corrupted filesystem detected on $PARTITION. Manual intervention required." | tee -a $LOG_FILE
    # sudo mkfs.ext4 /dev/sdc1 - format disk in case of filesystem corruption.
    exit 1
else
    echo "$(date) - Valid filesystem detected on $PARTITION. Skipping reformatting." | tee -a $LOG_FILE
fi

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    echo "$(date) - Creating mount point: $MOUNT_POINT" | tee -a $LOG_FILE
    sudo mkdir -p $MOUNT_POINT
fi

# Mount the disk
sudo mount $PARTITION $MOUNT_POINT
if [ $? -eq 0 ]; then
    echo "$(date) - Mounted $PARTITION to $MOUNT_POINT" | tee -a $LOG_FILE
else
    echo "$(date) - Failed to mount $PARTITION" | tee -a $LOG_FILE
    exit 1
fi

# Update /etc/fstab for persistent mounting
if ! grep -qs "$PARTITION" /etc/fstab; then
    echo "$(date) - Adding $PARTITION to /etc/fstab" | tee -a $LOG_FILE
    echo "$PARTITION $MOUNT_POINT ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
fi

# Set permissions
sudo chmod 777 $MOUNT_POINT

echo "$(date) - Data disk setup completed successfully." | tee -a $LOG_FILE