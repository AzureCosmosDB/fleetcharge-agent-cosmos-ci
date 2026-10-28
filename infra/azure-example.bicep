// EXAMPLE ONLY: companion infrastructure for the disabled Azure CD mock-up.
// This does not deploy code or make the unchanged emulator/Ollama app cloud-ready.
// No Phi model, emulator, Ollama server or Foundry model is provisioned here.
// The reader supplies an existing Foundry endpoint/model and grants this app's
// runtimePrincipalId the appropriate inference role on that existing resource.
// Public HTTPS endpoints are used for simplicity; configure request authentication,
// network restrictions and operational controls before using this beyond an example.
// Creating the role assignments requires additional role-assignment permissions;
// the GitHub deployment identity deliberately cannot provision this infrastructure.
// Reference: https://learn.microsoft.com/azure/app-service/deploy-github-actions

targetScope = 'resourceGroup'

@description('Example resource location; choose a region supporting the selected services.')
param location string = resourceGroup().location

@description('Lowercase alphanumeric resource prefix, optionally containing internal hyphens.')
@minLength(3)
@maxLength(16)
param namePrefix string = 'fleetcharge'

@description('Reader-owned GitHub repository in owner/repository form, not a personal token.')
@minLength(3)
param githubRepository string

@description('Create and protect this GitHub environment separately; restrict it to main.')
param githubEnvironment string = 'azure-example'

type FoundryConfiguration = {
  @description('Existing HTTPS OpenAI-compatible Foundry endpoint; no default account.')
  @minLength(1)
  endpoint: string
  @description('Reader-selected existing model deployment; no default model.')
  @minLength(1)
  modelDeployment: string
}

@description('Existing Foundry configuration only; this template never creates a model.')
param foundry FoundryConfiguration

@description('Example Cosmos database; all containers are precreated, not provisioned by runtime code.')
param cosmosDatabaseName string = 'fleetcharge'

var suffix = uniqueString(resourceGroup().id, namePrefix)
var tags = {
  purpose: 'deployment-example-only'
}
var partitions = {
  depots: 'depotId'
  routes: 'depotId'
  vehicles: 'depotId'
  chargers: 'depotId'
  telemetry: 'vehicleId'
  recommendations: 'depotId'
  dispatchUpdates: 'depotId'
}

resource plan 'Microsoft.Web/serverfarms@2025-03-01' = {
  name: 'asp-${namePrefix}-${suffix}'
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2026-03-15' = {
  name: 'cosmos-${namePrefix}-${suffix}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    minimalTlsVersion: 'Tls12'
    publicNetworkAccess: 'Enabled'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: [
      { name: 'EnableServerless' }
    ]
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2026-03-15' = {
  parent: cosmos
  name: cosmosDatabaseName
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
  }
}

resource containers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2026-03-15' = [for partition in items(partitions): {
  parent: database
  name: partition.key
  properties: {
    resource: {
      id: partition.key
      partitionKey: {
        paths: [ '/${partition.value}' ]
        kind: 'Hash'
        version: 2
      }
    }
  }
}]

resource webApp 'Microsoft.Web/sites@2025-03-01' = {
  name: 'app-${namePrefix}-${suffix}'
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'uvicorn app.api:app --host 0.0.0.0 --port 8000'
      alwaysOn: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
        { name: 'COSMOS_DATABASE', value: cosmosDatabaseName }
        { name: 'COSMOS_MODE', value: 'azure' }
        { name: 'AGENT_MODEL_MODE', value: 'foundry' }
        { name: 'FOUNDRY_ENDPOINT', value: foundry.endpoint }
        { name: 'FOUNDRY_MODEL_DEPLOYMENT', value: foundry.modelDeployment }
      ]
    }
  }
}

resource ftpPublishingPolicy 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = {
  parent: webApp
  name: 'ftp'
  properties: {
    allow: false
  }
}

resource scmPublishingPolicy 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = {
  parent: webApp
  name: 'scm'
  properties: {
    allow: false
  }
}

// Cosmos data-plane access is separate from Azure resource-management roles.
resource cosmosDataAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2026-03-15' = {
  parent: cosmos
  name: guid(cosmos.id, webApp.id, cosmosDatabaseName, 'data-contributor')
  properties: {
    principalId: webApp.identity.principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: '${cosmos.id}/dbs/${cosmosDatabaseName}'
  }
  dependsOn: [ database ]
}

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-${namePrefix}-github-${suffix}'
  location: location
  tags: tags
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: githubIdentity
  name: 'github-environment'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepository}:environment:${githubEnvironment}'
    audiences: [ 'api://AzureADTokenExchange' ]
  }
}

resource websiteContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'de139f84-1756-47ae-9be6-808fbbe84772'
}

resource githubDeploymentAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: webApp
  name: guid(webApp.id, githubIdentity.id, websiteContributor.id)
  properties: {
    roleDefinitionId: websiteContributor.id
    principalId: githubIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

type GitHubConfiguration = {
  environment: string
  secrets: {
    AZURE_CLIENT_ID: string
    AZURE_TENANT_ID: string
    AZURE_SUBSCRIPTION_ID: string
  }
  variables: {
    AZURE_WEBAPP_NAME: string
  }
}

@description('Copy these identifiers into your protected GitHub environment, not this repository.')
output githubConfiguration GitHubConfiguration = {
  environment: githubEnvironment
  secrets: {
    AZURE_CLIENT_ID: githubIdentity.properties.clientId
    AZURE_TENANT_ID: subscription().tenantId
    AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
  }
  variables: {
    AZURE_WEBAPP_NAME: webApp.name
  }
}

@description('Grant this runtime identity inference access on your existing Foundry resource separately.')
output runtimePrincipalId string = webApp.identity.principalId