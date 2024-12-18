@secure()
param storageAccountName string

@description('The location of the storage account')
param location string = resourceGroup().location

@description('Access tier for the storage account (Hot or Cool)')
param accessTier string = 'Hot'

@description('Allow public access to blobs')
param allowBlobPublicAccess bool = false

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {}
}

resource datasetsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'datasets'
  properties: {
    publicAccess: 'None'
  }
}

resource scriptsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'scripts'
  properties: {
    publicAccess: 'None'
  }
}

resource modelsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'models'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountName string = storageAccount.name
output datasetsContainerUrl string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}/datasets'
output scriptsContainerUrl string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}/scripts'
output modelsContainerUrl string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}/models'
