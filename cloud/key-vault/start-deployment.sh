#!/bin/bash

set -e

UTILS_PATH=../utils

# Load environment variables
. $UTILS_PATH/preset-environment-variables.sh

echo "Creating Key Vault"
az keyvault create \
  --name $AZURE_KEY_VAULT \
  --resource-group $AZURE_RESOURCE_GROUP \
  --sku standard

echo "Self-Assigning Key Vault Administrator role"
az role assignment create \
  --role "Key Vault Administrator" \
  --assignee $AZURE_MY_OBJECT_ID \
  --scope $(az keyvault show --name $AZURE_KEY_VAULT --query id -o tsv)

echo "Setting Key Vault secret"
az keyvault secret set \
  --vault-name $AZURE_KEY_VAULT \
  --name "AzureStorageConnectionString" \
  --value $AZURE_STORAGE_CONNECTION