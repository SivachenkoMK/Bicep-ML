#!/bin/bash

export AZURE_RESOURCE_GROUP=

export AZURE_STORAGE_ACCOUNT=

export AZURE_KEY_VAULT=

export AZURE_MY_OBJECT_ID=

unset EXISTING_DATA_DISK_NAME

export EXISTING_DATA_DISK_NAME=

export AZURE_VM_ADMIN_PASSWORD=

unset EXISTING_DATA_DISK_ID

export EXISTING_DATA_DISK_ID=$(az disk show --name $EXISTING_DATA_DISK_NAME --resource-group $AZURE_RESOURCE_GROUP --query id --output tsv)

export AZURE_STORAGE_KEY=$(az storage account keys list --account-name $AZURE_STORAGE_ACCOUNT --resource-group $AZURE_RESOURCE_GROUP --query "[0].value" -o tsv)

export AZURE_STORAGE_CONNECTION=$(az storage account show-connection-string --name $AZURE_STORAGE_ACCOUNT --resource-group $AZURE_RESOURCE_GROUP --query connectionString -o tsv)