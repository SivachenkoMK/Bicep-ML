#!/bin/bash

set -e

# Function to load or increment DEPLOYMENT_ID
increment_deployment_id() {
    local file="../ops/deployment-id.txt"

    # Check if file exists and read DEPLOYMENT_ID
    if [ -f "$file" ]; then
        DEPLOYMENT_ID=$(cat "$file")
        DEPLOYMENT_ID=$((DEPLOYMENT_ID + 1))
    else
        DEPLOYMENT_ID=1
    fi

    # Save updated DEPLOYMENT_ID to file
    echo "$DEPLOYMENT_ID" > "$file"
    export DEPLOYMENT_ID
}

# Increment DEPLOYMENT_ID
increment_deployment_id
echo "Using DEPLOYMENT_ID: $DEPLOYMENT_ID"

# Load environment variables
. ../utils/preset-environment-variables.sh

# Check files needed for archiving
required_files=("vm-driver-setup.sh" "vm-python-setup.sh" "vm-disk-mount.sh" "training.py" "azure-upload-model.py" "test-gpu-access.py" "config.json")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file '$file' not found."
        exit 1
    fi
done

artifacts_path="../ops/artifacts"

# Ensure ./artifacts directory exists
if [ ! -d "$artifacts_path" ]; then
    echo "Creating $artifacts_path directory"
    mkdir -p $artifacts_path
fi

echo "Creating ZIP archive"
# Create ZIP-archive
zip -qr ${artifacts_path}/${DEPLOYMENT_ID}.zip "${required_files[@]}"

# Load archive to Azure Blob Storage
az storage blob upload \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --container-name scripts \
    --name artifacts-${DEPLOYMENT_ID}.zip \
    --file ${artifacts_path}/${DEPLOYMENT_ID}.zip \
    --overwrite \
    --only-show-errors

chmod +x ../utils/build-url-with-sas.sh
. ../utils/build-url-with-sas.sh $AZURE_STORAGE_ACCOUNT scripts artifacts-${DEPLOYMENT_ID}.zip AZURE_VM_ARTIFACTS_URL

# Shared GPU-VM Bicep path
bicep_path="../shared/vm-gpu.bicep"

# Check existence of Bicep template
if [ ! -f "$bicep_path" ]; then
    echo "Error: Bicep template '$bicep_path' not found."
    exit 1
fi

# Start VM deployment with Bicep
az deployment group create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --template-file "$bicep_path" \
    --parameters \
    adminPassword="$AZURE_VM_ADMIN_PASSWORD" \
    artifactsUrl="$AZURE_VM_ARTIFACTS_URL" \
    keyVaultName="$AZURE_KEY_VAULT" \
    existingDataDiskId="$EXISTING_DATA_DISK_ID" \
    --output json > deploy.json

echo "Deployment completed successfully with DEPLOYMENT_ID: $DEPLOYMENT_ID."