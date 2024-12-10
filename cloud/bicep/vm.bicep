metadata description = 'Use Bicep templates to create VM with B1s'
metadata creationDate = '5th Dec 2024'

param deploymentId string = uniqueString(resourceGroup().id)

param location string = resourceGroup().location

param computerName string = 'mikhail'

param adminUsername string = 'mikhail'

param homeDirectory string = '/home/${adminUsername}'

@secure()
param keyVaultName string

@secure()
param setupUrl string

@secure()
param trainingUrl string

@secure()
param adminPassword string

resource publicIPAddress 'Microsoft.Network/publicIPAddresses@2024-03-01' = {
  name: 'ip-${deploymentId}'
  location: location
  properties: {
    publicIPAllocationMethod: 'Dynamic'
    dnsSettings: {
      domainNameLabel: 'mikhail-dns-label'
    }
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
      vmSize: 'Standard_B1s'
    }
    osProfile: {
      computerName: computerName
      adminUsername: adminUsername
      adminPassword: adminPassword
      customData: base64(concat(
        '#!/bin/bash\n',
        'LOG_FILE="/var/log/setup-script.log"\n',
        'echo "$(date) - Setup script URL: ', setupUrl, '" >> $LOG_FILE\n',
        'echo "$(date) - Training script URL: ', trainingUrl, '" >> $LOG_FILE\n',
        '\n',
        '# Download and execute setup script\n',
        'curl -o /tmp/setup-script.sh "', setupUrl, '" >> $LOG_FILE 2>&1\n',
        'chmod +x /tmp/setup-script.sh >> $LOG_FILE 2>&1\n',
        '/tmp/setup-script.sh >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - Setup script completed successfully" >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Setup script failed" >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
        '# Download training script\n',
        'curl -o ', homeDirectory, '/workdir/training.py "', trainingUrl, '" >> $LOG_FILE 2>&1\n',
        'if [ $? -eq 0 ]; then\n',
        '  echo "$(date) - Training script fetched successfully and stored at ', homeDirectory, '/workdir/training.py" >> $LOG_FILE\n',
        'else\n',
        '  echo "$(date) - Failed to fetch training script" >> $LOG_FILE\n',
        '  exit 1\n',
        'fi\n',
        '\n',
        '# Create "saved_models_per_epoch" directory and give all permissions\n',
        'mkdir -p ', homeDirectory, '/workdir/saved_models_per_epoch >> $LOG_FILE 2>&1\n',
        'chmod 777 ', homeDirectory, '/workdir/saved_models_per_epoch >> $LOG_FILE 2>&1\n',
        'echo "$(date) - "saved_models_per_epoch" directory created with full permissions." >> $LOG_FILE\n'
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
