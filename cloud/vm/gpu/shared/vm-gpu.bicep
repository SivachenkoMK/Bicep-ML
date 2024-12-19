metadata description = 'Use Bicep templates to create N-Series VM with GPU Support'
metadata creationDate = '5th Dec 2024'

param deploymentId string = uniqueString('vm-gpu:${resourceGroup().id}')

param location string = resourceGroup().location

param computerName string = 'mikhail'

param adminUsername string = 'mikhail'

@secure()
param keyVaultName string

@secure()
param existingDataDiskId string = '' // Provide the existing disk ID or leave empty to create a new disk

@secure()
param existingDataDiskName string = ''

@secure()
param artifactsUrl string

param homeDirectory string = '/home/${adminUsername}'

@secure()
param adminPassword string

resource publicIPAddress 'Microsoft.Network/publicIPAddresses@2024-03-01' = {
  name: 'ip-${deploymentId}'
  location: location
  properties: {
    publicIPAllocationMethod: 'Dynamic'
    dnsSettings: {
      domainNameLabel: 'dns-label-${deploymentId}'
    }
  }
}

resource dataDisk 'Microsoft.Compute/disks@2024-03-02' = if (empty(existingDataDiskId)) {
  name: 'data-disk-${deploymentId}'
  location: location
  properties: {
    diskSizeGB: 64
    creationData: {
      createOption: 'Empty'
    }
  }
  sku: {
    name: 'Premium_LRS' // Choose your disk type
  }
}

resource networkInterface 'Microsoft.Network/networkInterfaces@2024-03-01' = {
  name: 'nic-${deploymentId}'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig-${deploymentId}'
        properties: {
          subnet: {
            id: virtualNetwork.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: publicIPAddress.id
          }
        }
      }
    ]
  }
}

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-03-01' = {
  name: 'vnet-${deploymentId}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/24'
      ]
    }
    subnets: [
      {
        name: 'subnet-${deploymentId}'
        properties: {
          addressPrefix: '10.0.0.0/28'
        }
      }
    ]
  }
}

resource Vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: 'vm-${deploymentId}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_NC4as_T4_v3'
    }
    osProfile: {
      computerName: computerName
      adminUsername: adminUsername
      adminPassword: adminPassword
      customData: base64(concat(
        '#!/bin/bash\n',
        'LOG_FILE="/var/log/setup-script.log"\n',
        'echo "$(date) - Artifacts URL: ', artifactsUrl, '" >> $LOG_FILE\n',
        '\n',
      
        '# Update package list and install unzip\n',
        'echo "$(date) - Updating package list." >> $LOG_FILE\n',
        'sudo apt-get update >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - Package list updated successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Failed to update package list." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        'echo "$(date) - Installing unzip." >> $LOG_FILE\n',
        'sudo apt-get install -y unzip >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - unzip installed successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Failed to install unzip." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Download artifacts\n',
        'ARTIFACTS_ARCHIVE="/tmp/artifacts.zip"\n',
        'echo "$(date) - Downloading artifacts from $artifactsUrl to $ARTIFACTS_ARCHIVE" >> $LOG_FILE\n',
        'curl -L -o $ARTIFACTS_ARCHIVE "', artifactsUrl, '" >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - Artifacts downloaded successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Failed to download artifacts from $artifactsUrl" >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Extract artifacts\n',
        'echo "$(date) - Extracting artifacts to ', homeDirectory, '/workdir" >> $LOG_FILE\n',
        'mkdir -p ', homeDirectory, '/workdir >> $LOG_FILE 2>&1\n',
        'sudo chmod 777 ', homeDirectory, '/workdir >> $LOG_FILE 2>&1\n',
        'unzip -o $ARTIFACTS_ARCHIVE -d ', homeDirectory, '/workdir >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - Artifacts extracted successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Failed to extract artifacts." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Execute vm-disk-mount.sh\n',
        'echo "$(date) - Executing vm-disk-mount.sh" >> $LOG_FILE\n',
        'chmod +x ', homeDirectory, '/workdir/vm-disk-mount.sh >> $LOG_FILE 2>&1\n',
        'bash ', homeDirectory, '/workdir/vm-disk-mount.sh >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - vm-disk-mount.sh executed successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - vm-disk-mount.sh execution failed." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Execute vm-python-setup.sh\n',
        'echo "$(date) - Executing vm-python-setup.sh" >> $LOG_FILE\n',
        'chmod +x ', homeDirectory, '/workdir/vm-python-setup.sh >> $LOG_FILE 2>&1\n',
        'bash ', homeDirectory, '/workdir/vm-python-setup.sh >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - vm-python-setup.sh executed successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - vm-python-setup.sh execution failed." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Execute vm-driver-setup.sh\n',
        'echo "$(date) - Executing vm-driver-setup.sh" >> $LOG_FILE\n',
        'chmod +x ', homeDirectory, '/workdir/vm-driver-setup.sh >> $LOG_FILE 2>&1\n',
        'bash ', homeDirectory, '/workdir/vm-driver-setup.sh >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - vm-driver-setup.sh executed successfully." >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - vm-driver-setup.sh execution failed." >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
      
        '# Final log entry\n',
        'echo "$(date) - All setup scripts executed successfully." >> $LOG_FILE\n'
      ))
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        name: 'os-disk-${deploymentId}'
        caching: 'ReadWrite'
        createOption: 'FromImage'
        diskSizeGB: 64
      }
      dataDisks: [
        {
          lun: 0
          name: empty(existingDataDiskName) ? 'data-disk-${deploymentId}' : existingDataDiskName
          createOption: 'Attach'
          managedDisk: {
            id: empty(existingDataDiskId) ? dataDisk.id : existingDataDiskId
          }
          diskSizeGB: 64
        }
      ]
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: networkInterface.id
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: false // Enable for deploying N-series
      }
    }
  }
}


resource vault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

@description('Assign the VM system-assigned identity "Key Vault Secrets User" role')
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, 'KeyVaultSecretsUser', Vm.id)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User Role
    principalId: Vm.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output adminUsername string = adminUsername
output hostname string = publicIPAddress.properties.dnsSettings.fqdn
output sshCommand string = 'ssh ${adminUsername}@${publicIPAddress.properties.dnsSettings.fqdn}'
