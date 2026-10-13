param location string = 'northeurope'
param aksName string = 'aks-armen-learning-2026'
param kubernetesVersion string = '1.36.3'
param acrResourceId string
param kubeletPrincipalId string
param jenkinsPrincipalId string

param storageAccountName string = 'starmenlearning2026'
param searchServiceName string = 'search-armen-learning-2026'
param foundryAccountName string = 'foundry-armen-sweden-2026'

var acrPushRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)

var aksClusterUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4abbcc35-e782-43d8-92c5-2d3f1bd2253f'
)

var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

var blobDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
)

var searchIndexDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '1407120a-92aa-4202-b7e9-c0e197c71c8f'
)

var openAIUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' existing = {
  name: storageAccountName
}

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchServiceName
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource aks 'Microsoft.ContainerService/managedClusters@2026-02-01' = {
  name: aksName
  location: location

  identity: {
    type: 'SystemAssigned'
  }

  sku: {
    name: 'Base'
    tier: 'Free'
  }

  properties: {
    dnsPrefix: aksName
    kubernetesVersion: kubernetesVersion
    enableRBAC: true
    disableLocalAccounts: true

    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }

    oidcIssuerProfile: {
      enabled: true
    }

    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }

    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: 1
        vmSize: 'Standard_D2s_v3'
        osType: 'Linux'
        osSKU: 'Ubuntu'
        type: 'VirtualMachineScaleSets'
      }
    ]

    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
      outboundType: 'loadBalancer'
    }
  }
}

output aksName string = aks.name
output oidcIssuerUrl string = aks.properties.oidcIssuerProfile.issuerURL
output clusterPrincipalId string = aks.identity.principalId

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-storage-demo-aks'
  location: location
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: workloadIdentity
  name: 'fic-storage-demo'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:storage-demo:storage-demo-sa'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

output workloadIdentityClientId string = workloadIdentity.properties.clientId
output workloadIdentityPrincipalId string = workloadIdentity.properties.principalId

resource acr 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: last(split(acrResourceId, '/'))
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, kubeletPrincipalId, acrPullRoleDefinitionId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: aks.properties.identityProfile.kubeletidentity.objectId
    principalType: 'ServicePrincipal'
  }
}

resource workloadBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, workloadIdentity.id, blobDataReaderRoleId)
  scope: storage
  properties: {
    roleDefinitionId: blobDataReaderRoleId
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workloadSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, workloadIdentity.id, searchIndexDataReaderRoleId)
  scope: search
  properties: {
    roleDefinitionId: searchIndexDataReaderRoleId
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workloadFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, workloadIdentity.id, openAIUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: openAIUserRoleId
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jenkinsAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, jenkinsPrincipalId, acrPushRoleId)
  scope: acr
  properties: {
    roleDefinitionId: acrPushRoleId
    principalId: jenkinsPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource jenkinsClusterUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aks.id, jenkinsPrincipalId, aksClusterUserRoleId)
  scope: aks
  properties: {
    roleDefinitionId: aksClusterUserRoleId
    principalId: jenkinsPrincipalId
    principalType: 'ServicePrincipal'
  }
}
