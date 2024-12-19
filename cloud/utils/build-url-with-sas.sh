#!/bin/bash

set -e

# Input parameters
STORAGE_ACCOUNT=${AZURE_STORAGE_ACCOUNT:-} # Storage account name from environment variable (required)
SCRIPTS_CONTAINER=${2:-scripts}           # Scripts container name (optional, default: 'scripts')
SCRIPT_NAME=${3:-setup-script.sh}         # Script name (optional, default: 'setup-script.sh')
ENV_VAR_NAME=${4:-AZURE_VM_TRAINING_URL}  # Environment variable name to store the URL (optional, default: 'AZURE_VM_TRAINING_URL')

# Validate required inputs
if [[ -z "$STORAGE_ACCOUNT" ]]; then
  echo "Error: Storage account name must be set in AZURE_STORAGE_ACCOUNT environment variable."
  exit 1
fi

# Generate SAS token
SAS_TOKEN=$(az storage blob generate-sas \
    --account-name "$STORAGE_ACCOUNT" \
    --container-name "$SCRIPTS_CONTAINER" \
    --name "$SCRIPT_NAME" \
    --permissions r \
    --expiry "$(date -u -d "+7 days" '+%Y-%m-%dT%H:%M:%SZ')" \
    --output tsv)

if [[ -z "$SAS_TOKEN" ]]; then
  echo "Error: Failed to generate SAS token."
  exit 1
fi

# Build the setup script URL
SCRIPT_URL="https://${STORAGE_ACCOUNT}.blob.core.windows.net/${SCRIPTS_CONTAINER}/${SCRIPT_NAME}?${SAS_TOKEN}"

# Export as an environment variable
declare "$ENV_VAR_NAME=$SCRIPT_URL"

export "$ENV_VAR_NAME"

# Print the URL and confirmation
echo "$ENV_VAR_NAME"
echo "Exported to the environment as $ENV_VAR_NAME."