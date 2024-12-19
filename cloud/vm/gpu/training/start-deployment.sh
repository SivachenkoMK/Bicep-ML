#!/bin/bash

set -e

# Define the path
SHARED_PATH=../shared

# Define the required files
required_files=(
  "$SHARED_PATH/vm-driver-setup.sh"
  "$SHARED_PATH/vm-python-setup.sh"
  "$SHARED_PATH/vm-disk-mount.sh"
  "training.py"
  "azure-upload-model.py"
  "test-gpu-access.py"
  "config.json"
)

# Convert the array to a space-separated string
required_files_string="${required_files[*]}"

# Pass the string to deploy-core.sh
. $SHARED_PATH/deploy-core.sh "$required_files_string"