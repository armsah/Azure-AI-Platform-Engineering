targetScope = 'subscription'

param location string = 'northeurope'
param resourceGroupName string = 'rg-azure-learning'

resource rg 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: resourceGroupName
  location: location
}

output resourceGroupName string = rg.name
