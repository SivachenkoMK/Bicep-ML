#!/bin/bash
# Invoked from start-deployment.sh inside training/testing directories

set -e

OPS_PATH=../ops
UTILS_PATH=../../../utils
SHARED_PATH=../shared

# Read the string containing the paths and convert it back to an array
IFS=" " read -r -a required_files <<< "$1"

# Function to load or increment DEPLOYMENT_ID
increment_deployment_id() {
    local file="$OPS_PATH/deployment-id.txt"

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
. $UTILS_PATH/preset-environment-variables.sh

artifacts_path="$OPS_PATH/artifacts"
temp_dir=$(mktemp -d)

# Ensure all required files exist
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file '$file' not found."
        exit 1
    fi
done

# Ensure artifacts directory exists
if [ ! -d "$artifacts_path" ]; then
    echo "Creating $artifacts_path directory"
    mkdir -p "$artifacts_path"
fi

echo "Copying files to temporary directory"
# Copy files to a temporary directory with a flat structure
for file in "${required_files[@]}"; do
    cp "$file" "$temp_dir"
done

echo "Creating ZIP archive"
# Create ZIP archive from the temporary directory
zip -qr "${artifacts_path}/${DEPLOYMENT_ID}.zip" -j "$temp_dir"/*

# Cleanup temporary directory
rm -rf "$temp_dir"

# Load archive to Azure Blob Storage
az storage blob upload \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --container-name scripts \
    --name artifacts-${DEPLOYMENT_ID}.zip \
    --file ${artifacts_path}/${DEPLOYMENT_ID}.zip \
    --overwrite \
    --only-show-errors

chmod +x $UTILS_PATH/build-url-with-sas.sh
. $UTILS_PATH/build-url-with-sas.sh $AZURE_STORAGE_ACCOUNT scripts artifacts-${DEPLOYMENT_ID}.zip AZURE_VM_ARTIFACTS_URL

# Shared GPU-VM Bicep path
bicep_path="$SHARED_PATH/vm-gpu.bicep"

# Check existence of Bicep template
if [ ! -f "$bicep_path" ]; then
    echo "Error: Bicep template $bicep_path not found."
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
    existingDataDiskName="$EXISTING_DATA_DISK_NAME" \
    --output json > $OPS_PATH/deploy.json

echo "Deployment completed successfully with DEPLOYMENT_ID: $DEPLOYMENT_ID."