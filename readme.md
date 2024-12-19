# Introduction

This README provides instructions for setting up and managing the project, which includes creating necessary Azure resources, configuring environment variables, and deploying GPU-based VMs for training and testing machine learning models.

## Environment Variables

We will use several environment variables throughout the setup process.

Please find `preset-environment-variables-sample.sh` file in the `utils` directory. Create a local copy of it with name `preset-environment-variables.sh` and initialize the following environment variables:

`AZURE_RESOURCE_GROUP` - Resource Group name

`AZURE_STORAGE_ACCOUNT` - Storage Account name

`AZURE_KEY_VAULT` - Key Vault name

`AZURE_MY_OBJECT_ID` - ObjectId of your user (get from Microsoft Entra ID)

`EXISTING_DATA_DISK_NAME` - Name of persistent disk, if you already created it

`AZURE_VM_ADMIN_PASSWORD` - Password for the administrator account of VM

## Create Resource Group

Create Resource Group with command:

`az group create --name $AZURE_RESOURCE_GROUP --location westeurope`

## Create Storage Account

**Description**: Creates storage account with two containers (startup scripts and datasets)

* CNN-related Storage Account
    * scripts container
    * datasets container
    * models container

Deployment steps:

`cd /cloud/storage`

`chmod +x ./start-deployment.sh`

`. ./start-deployment.sh`

**If deployment fails, ensure that you provided necessary environment variable names inside `preset-environment-variables.sh`.**

Upload desired dataset to the `datasets` container:

`MANUAL: save dataset to ./desired-dataset-directory`

`chmod +x preset-environment-variables.sh`

`. ./utils/preset-environment-variables.sh`

`az storage blob upload-batch \
    --account-name $AZURE_STORAGE_ACCOUNT \
    --destination datasets \
    --source ./desired-dataset-directory`

## Create Azure Key Vault and manage secrets for VM from there

Deployment steps:

`cd /cloud/key-vault`

`chmod +x ./start-deployment.sh`

`. ./start-deployment.sh`.

**If deployment fails, ensure that you provided necessary environment variable names inside `preset-environment-variables.sh`.**

## Create GPU-Based VM for Training Model (vm-training.bicep):

`cd /cloud/vm/gpu/training`

`. start-deployment.sh`

## Create GPU-Based VM for Testing Model (vm-testing.bicep):

`cd /cloud/vm/gpu/testing`

`. start-deployment.sh`

## Clean it Up:

Delete RG:

`az group delete --name $AZURE_RESOURCE_GROUP --yes`

Delete all blobs from container (If environment variable is set)

`az storage blob delete-batch --account-name $AZURE_STORAGE_ACCOUNT --source scripts`

Revalidate Storage Account Keys:
`az storage account keys renew --account-name $AZURE_STORAGE_ACCOUNT --key primary`

### VM removal:

Unmount disk before deleting VM:
`sudo umount /mnt/data`

Flush pending writes:
`sudo sync`

Shut down VM gracefully:
`sudo shutdown -h now`

Remove the access policy from IAM for Key Vault
`TODO`