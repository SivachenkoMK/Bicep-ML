#!/bin/bash
set -e

USER_LOCATION="/home/mikhail"
# Log file path
LOGFILE="${USER_LOCATION}/setup-script.log"

# Python version variable
PYTHON_VERSION="3.12"

# Function to log messages
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOGFILE"
}

log "Starting setup script."

# Check for Python3 availability
if ! command -v python3 &> /dev/null; then
  log "Error: Python3 is not installed. Please install Python3 manually."
  exit 1
fi

sudo apt update && sudo apt install python${PYTHON_VERSION}-venv -y | tee -a "$LOGFILE"
log "python${PYTHON_VERSION}-venv installed successfully."

# Ensure pip is installed
if ! python3 -m pip --version &> /dev/null; then
  log "pip is not installed. Installing pip..."
  sudo apt update && sudo apt install -y python3-pip | tee -a "$LOGFILE"
  log "pip installed successfully."
fi

# Set the working directory
WORKDIR="${USER_LOCATION}/workdir"
if [ ! -d "$WORKDIR" ]; then
  mkdir -p "$WORKDIR"
  log "Created working directory at $WORKDIR."
else
  log "Working directory $WORKDIR already exists."
fi

cd "$WORKDIR"

# Create a Python virtual environment if not already created
if [ ! -d "myenv" ]; then
  log "Creating Python virtual environment..."
  if python3 -m venv myenv; then
    log "Virtual environment created successfully."
  else
    log "Error: Failed to create virtual environment."
    exit 1
  fi
else
  log "Virtual environment already exists. Skipping creation."
fi

# Check if the virtual environment exists before attempting to activate it
if [ -f "myenv/bin/activate" ]; then
  log "Activating virtual environment and installing packages..."
  source myenv/bin/activate
  pip install --upgrade pip | tee -a "$LOGFILE"
  pip install tensorflow[and-cuda] numpy scipy matplotlib azure-identity azure-storage-blob azure-keyvault-secrets | tee -a "$LOGFILE"
  echo "Creating training.log" | tee -a "$LOGFILE"
  touch training.log 2>&1 | tee -a "$LOGFILE"
  echo "Setting permissions on training.log" | tee -a "$LOGFILE"
  chmod 666 training.log 2>&1 | tee -a "$LOGFILE"
  deactivate
  log "Packages installed successfully and log file prepared."
else
  log "Error: Virtual environment activation script not found."
  exit 1
fi

log "Setup completed successfully."

