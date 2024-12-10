# Introduction

## Environment Variables

We will use many different environment variables.

You get to set them the way you prefer. Some examples are presented in the file.

Here is a complete list of all environment variables:

`AZURE_KEY_VAULT` - Key Vault name

`AZURE_MY_OBJECT_ID` - ObjectId of your user (get from Microsoft Entra ID)

`AZURE_RESOURCE_GROUP` - Resource Group name

`AZURE_STORAGE_ACCOUNT` - Storage Account name

`AZURE_STORAGE_KEY` - Storage Account key

`AZURE_STORAGE_CONNECTION` - Storage Account connection string

`AZURE_VM_SETUP_SCRIPT_URL` - url to the setup script with SAS key (built from script)

`$AZURE_TRAININGPY_URL` - url to the python training script with SAS key (built from script)

`AZURE_VM_ADMIN_PASSWORD` - password for administrator account of your VM

## Create Resource Group

Create Resource Group with command:

`az group create --name $AZURE_RESOURCE_GROUP --location westeurope`

## Lifehacks

When using Azure CLI commands, add the `--output json > result.json` to save the response in a highly readable format, which can be easily formatted (for example in VS Code)

Example:
`az account list --output json > result.json`

Check your deployments:

`az deployment group list --resource-group $AZURE_RESOURCE_GROUP --output table`

## Create Storage Account

**Description**: Creates storage account with two containers (startup scripts and datasets)

* CNN-related  Storage Account
    * scripts container
    * datasets container

Create the storage account with three containers and store the environment variables:

`az deployment group create --resource-group $AZURE_RESOURCE_GROUP --template-file ./cloud/bicep/storage.bicep --parameters storageAccountName=$AZURE_STORAGE_ACCOUNT`

`export AZURE_STORAGE_KEY=$(az storage account keys list --account-name $AZURE_STORAGE_ACCOUNT --resource-group $AZURE_RESOURCE_GROUP --query "[0].value" -o tsv)`

`export AZURE_STORAGE_CONNECTION=$(az storage account show-connection-string --name $AZURE_STORAGE_ACCOUNT --resource-group $AZURE_RESOURCE_GROUP --query connectionString -o tsv)`

Upload VM setup-script to scripts container:

`az storage blob upload \
    --account-name $AZURE_STORAGE_ACCOUNT \
    --container-name scripts \
    --name setup-script.sh \
    --file ./cnn/setup-script.sh`

Upload ML training & testing scripts to scripts container:

`az storage blob upload \
    --account-name $AZURE_STORAGE_ACCOUNT \
    --container-name scripts \
    --name training.py \
    --file ./cnn/ml-code/training.py`

`az storage blob upload \
    --account-name $AZURE_STORAGE_ACCOUNT \
    --container-name scripts \
    --name testing.py \
    --file ./cnn/ml-code/testing.py`

Enable execution for the url-building script:

`chmod +x ./cloud/bash/build-url-with-sas.sh`

Execute the scripts to export the read-access urls to environment variables:

`. cloud/bash/build-url-with-sas.sh $AZURE_STORAGE_ACCOUNT scripts setup-script.sh AZURE_VM_SETUP_SCRIPT_URL`

`. cloud/bash/build-url-with-sas.sh $AZURE_STORAGE_ACCOUNT scripts training.py AZURE_TRAININGPY_URL`

Upload blobs from the dataset to the datasets container:
`az storage blob upload-batch \
    --account-name $AZURE_STORAGE_ACCOUNT \
    --destination datasets \
    --source ./cnn/forest-fire`

## Create Azure Key Vault and manage secrets for VM from there

Create Key Vault:

`az keyvault create \
  --name $AZURE_KEY_VAULT \
  --resource-group $AZURE_RESOURCE_GROUP \
  --sku standard`

Assign yourself to the list of Key Vault administrators with RBAC:

`az role assignment create \
  --role "Key Vault Administrator" \
  --assignee $AZURE_MY_OBJECT_ID \
  --scope $(az keyvault show --name $AZURE_KEY_VAULT --query id -o tsv)`

`az keyvault secret set \
  --vault-name $AZURE_KEY_VAULT \
  --name "AzureStorageConnectionString" \
  --value $AZURE_STORAGE_CONNECTION`

## Create basic VM (vm.bicep):

Execute bicep configuration:

`az deployment group create --resource-group $AZURE_RESOURCE_GROUP --template-file ./cloud/bicep/vm.bicep --parameters adminPassword=$AZURE_VM_ADMIN_PASSWORD setupUrl=$AZURE_VM_SETUP_SCRIPT_URL keyVaultName=$AZURE_KEY_VAULT trainingUrl=$AZURE_TRAININGPY_URL`

## Clean it Up:

Delete RG:

`az group delete --name $AZURE_RESOURCE_GROUP --yes`

Delete all blobs from container (If environment variable is set)

`az storage blob delete-batch --account-name $AZURE_STORAGE_ACCOUNT --source scripts`

Revalidate Storage Account Keys:
`az storage account keys renew --account-name $AZURE_STORAGE_ACCOUNT --key primary`

After killing VM, remove the access policy from IAM for Key Vault
`TODO`

Clean Environment variables like:

`unset AZURE_STORAGE_KEY`

`unset AZURE_STORAGE_ACCOUNT`