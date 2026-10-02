param location string = 'northeurope'
param appServiceLocation string = 'westeurope'
param jenkinsPrincipalId string

param searchServiceName string = 'search-armen-learning-2026'
param foundryLocation string = 'swedencentral'
param foundryResourceName string = 'foundry-armen-sweden-2026'
param appServicePlanName string = 'plan-azure-learning'
param webAppName string = 'armen-storage-demo-2026'
param pythonVersion string = '3.14'
param storageAccountName string = 'starmenlearning2026'
param containerRegistryName string = 'acrarmenlearning2026'
param blobContainerName string = 'documents'
param blobName string = 'hello.txt'

var cognitiveServicesOpenAIUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

var websiteContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'de139f84-1756-47ae-9be6-808fbbe84772'
)

var searchIndexDataReaderRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '1407120a-92aa-4202-b7e9-c0e197c71c8f'
)

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: containerRegistryName
  location: 'northeurope'

  sku: {
    name: 'Basic'
  }

  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output containerRegistryLoginServer string = containerRegistry.properties.loginServer

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryResourceName
  location: foundryLocation
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: foundryResourceName
    publicNetworkAccess: 'Enabled'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundryAccount
  name: 'gpt-5-mini-learning'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundryAccount
  name: 'embedding-learning'

  dependsOn: [
    chatDeployment
  ]

  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-06-01' = {
  name: 'default'
  parent: storageAccount
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01' = {
  name: blobContainerName
  parent: blobService
}

resource appServicePlan 'Microsoft.Web/serverfarms@2025-03-01' = {
  name: appServicePlanName
  location: appServiceLocation
  sku: {
    name: 'F1'
    tier: 'Free'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2025-03-01' = {
  name: webAppName
  location: appServiceLocation
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      alwaysOn: false
    }
    httpsOnly: true
  }
}

resource webAppSettings 'Microsoft.Web/sites/config@2025-03-01' = {
  name: 'appsettings'
  parent: webApp
  properties: {
    AZURE_STORAGE_ACCOUNT_NAME: storageAccount.name
    AZURE_STORAGE_CONTAINER_NAME: blobContainer.name
    AZURE_STORAGE_BLOB_NAME: blobName

    AZURE_AI_ENDPOINT: 'https://${foundryResourceName}.openai.azure.com/openai/v1/'
    AZURE_AI_DEPLOYMENT: 'gpt-5-mini-learning'
    AZURE_AI_EMBEDDING_DEPLOYMENT: 'embedding-learning'

    AZURE_SEARCH_ENDPOINT: 'https://${searchServiceName}.search.windows.net'
    AZURE_SEARCH_INDEX: 'rag-documents'

    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
  }
}

resource webAppFoundryInferenceRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, webApp.id, cognitiveServicesOpenAIUserRoleDefinitionId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: cognitiveServicesOpenAIUserRoleDefinitionId
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageBlobDataRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, webApp.id, storageBlobDataContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jenkinsWebsiteContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(webApp.id, jenkinsPrincipalId, websiteContributorRoleDefinitionId)
  scope: webApp
  properties: {
    roleDefinitionId: websiteContributorRoleDefinitionId
    principalId: jenkinsPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource searchService 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
  location: 'northeurope'

  sku: {
    name: 'free'
  }

  properties: {
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false

    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

output searchEndpoint string = 'https://${searchService.name}.search.windows.net'

resource searchReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, webApp.id, 'search-index-data-reader')
  scope: searchService

  properties: {
    roleDefinitionId: searchIndexDataReaderRoleDefinitionId
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
