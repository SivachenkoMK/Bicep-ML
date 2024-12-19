#!/bin/bash

set -e

UTILS_PATH=../utils

# Load environment variables
. $UTILS_PATH/preset-environment-variables.sh

az deployment group create --resource-group $AZURE_RESOURCE_GROUP --template-file ./storage.bicep --parameters storageAccountName=$AZURE_STORAGE_ACCOUNT