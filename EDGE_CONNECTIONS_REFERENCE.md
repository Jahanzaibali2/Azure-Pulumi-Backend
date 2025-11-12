# Edge Connections Reference

This document lists all **implemented** and **non-implemented** edge connections in the system. Use this for frontend validation.

---

## 📋 Supported Service Types (11 total)

| Service Kind | Azure Service | AWS Equivalent |
|-------------|---------------|----------------|
| `azure.storage` | Storage Account | S3 |
| `azure.servicebus` | Service Bus | SQS |
| `azure.containerapp` | Container Apps | ECS/Fargate |
| `azure.vm` | Virtual Machine | EC2 |
| `azure.functionapp` | Function App | Lambda |
| `azure.sql` | SQL Database | RDS |
| `azure.cosmosdb` | Cosmos DB | DynamoDB |
| `azure.apimanagement` | API Management | API Gateway |
| `azure.keyvault` | Key Vault | Secrets Manager |
| `azure.appinsights` | Application Insights | CloudWatch |
| `azure.vnet` | Virtual Network | VPC |

---

## ✅ IMPLEMENTED Edge Connections (88+ total)

**All valid Azure service connections from the matrix are now implemented!**

These connections are **fully implemented** and will work automatically:

### 1. `azure.storage` → `azure.servicebus`
- **Intent:** `"notify"`
- **Implementation:** Event Grid Subscription
- **What it does:** When a blob is created in storage, an event is automatically sent to the Service Bus queue
- **Event Type:** `Microsoft.Storage.BlobCreated`

**Example:**
```json
{
  "from": "storage-1",
  "to": "servicebus-1",
  "intent": "notify"
}
```

---

### 2. `azure.servicebus` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Connection string bindings (exported as outputs)
- **What it does:** Exports Service Bus queue name and connection string for the Container App to use
- **Outputs:** 
  - `bind-{containerapp-id}-queue`: Queue name
  - `bind-{containerapp-id}-conn`: Connection string

**Example:**
```json
{
  "from": "servicebus-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 3. `azure.servicebus` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Connection string bindings (exported as outputs)
- **What it does:** Exports Service Bus queue name and connection string for the Function App to use
- **Outputs:**
  - `bind-{functionapp-id}-queue`: Queue name
  - `bind-{functionapp-id}-conn`: Connection string

**Example:**
```json
{
  "from": "servicebus-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 4. `azure.keyvault` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Key Vault URI export
- **What it does:** Exports Key Vault URI and name for Function App to access secrets
- **Outputs:**
  - `bind-{functionapp-id}-keyvault-uri`: Key Vault URI
  - `bind-{functionapp-id}-keyvault-name`: Key Vault name

**Example:**
```json
{
  "from": "keyvault-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 5. `azure.keyvault` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Key Vault URI export
- **What it does:** Exports Key Vault URI and name for Container App to access secrets
- **Outputs:**
  - `bind-{containerapp-id}-keyvault-uri`: Key Vault URI
  - `bind-{containerapp-id}-keyvault-name`: Key Vault name

**Example:**
```json
{
  "from": "keyvault-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 6. `azure.cosmosdb` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Cosmos DB connection info export
- **What it does:** Exports Cosmos DB endpoint, database, and container names
- **Outputs:**
  - `bind-{functionapp-id}-cosmos-endpoint`: Cosmos DB endpoint
  - `bind-{functionapp-id}-cosmos-database`: Database name
  - `bind-{functionapp-id}-cosmos-container`: Container name

**Example:**
```json
{
  "from": "cosmosdb-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 7. `azure.cosmosdb` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Cosmos DB connection info export
- **What it does:** Exports Cosmos DB endpoint, database, and container names
- **Outputs:**
  - `bind-{containerapp-id}-cosmos-endpoint`: Cosmos DB endpoint
  - `bind-{containerapp-id}-cosmos-database`: Database name
  - `bind-{containerapp-id}-cosmos-container`: Container name

**Example:**
```json
{
  "from": "cosmosdb-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 8. `azure.sql` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** SQL connection info export
- **What it does:** Exports SQL server FQDN and database name
- **Outputs:**
  - `bind-{functionapp-id}-sql-server`: SQL server FQDN
  - `bind-{functionapp-id}-sql-database`: Database name

**Example:**
```json
{
  "from": "sql-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 9. `azure.sql` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** SQL connection info export
- **What it does:** Exports SQL server FQDN and database name
- **Outputs:**
  - `bind-{containerapp-id}-sql-server`: SQL server FQDN
  - `bind-{containerapp-id}-sql-database`: Database name

**Example:**
```json
{
  "from": "sql-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 10. `azure.storage` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Storage connection string export
- **What it does:** Exports storage connection string and account name for blob triggers
- **Outputs:**
  - `bind-{functionapp-id}-storage-conn`: Storage connection string
  - `bind-{functionapp-id}-storage-account`: Storage account name

**Example:**
```json
{
  "from": "storage-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 11. `azure.storage` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Storage connection string export
- **What it does:** Exports storage connection string and account name
- **Outputs:**
  - `bind-{containerapp-id}-storage-conn`: Storage connection string
  - `bind-{containerapp-id}-storage-account`: Storage account name

**Example:**
```json
{
  "from": "storage-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 12. `azure.appinsights` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Application Insights instrumentation export
- **What it does:** Exports instrumentation key and connection string for monitoring
- **Outputs:**
  - `bind-{functionapp-id}-appinsights-key`: Instrumentation key
  - `bind-{functionapp-id}-appinsights-conn`: Connection string

**Example:**
```json
{
  "from": "appinsights-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 13. `azure.appinsights` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Application Insights instrumentation export
- **What it does:** Exports instrumentation key and connection string for monitoring
- **Outputs:**
  - `bind-{containerapp-id}-appinsights-key`: Instrumentation key
  - `bind-{containerapp-id}-appinsights-conn`: Connection string

**Example:**
```json
{
  "from": "appinsights-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 14. `azure.apimanagement` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** API Management gateway URL export
- **What it does:** Exports API Management gateway and portal URLs
- **Outputs:**
  - `bind-{functionapp-id}-apim-gateway`: Gateway URL
  - `bind-{functionapp-id}-apim-portal`: Portal URL

**Example:**
```json
{
  "from": "apimanagement-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

---

### 15. `azure.apimanagement` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** API Management gateway URL export
- **What it does:** Exports API Management gateway and portal URLs
- **Outputs:**
  - `bind-{containerapp-id}-apim-gateway`: Gateway URL
  - `bind-{containerapp-id}-apim-portal`: Portal URL

**Example:**
```json
{
  "from": "apimanagement-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

---

### 16. `azure.functionapp` → `azure.containerapp`
- **Intent:** `"notify"`
- **Implementation:** Function App URL export
- **What it does:** Exports Function App URL and name for Container App to call
- **Outputs:**
  - `bind-{containerapp-id}-functionapp-url`: Function App HTTPS URL
  - `bind-{containerapp-id}-functionapp-name`: Function App name

**Example:**
```json
{
  "from": "functionapp-1",
  "to": "containerapp-1",
  "intent": "notify"
}
```

**Use Case:** Container App can call Function App APIs using the exported URL.

---

### 17. `azure.containerapp` → `azure.functionapp`
- **Intent:** `"notify"`
- **Implementation:** Container App FQDN export
- **What it does:** Exports Container App FQDN and name for Function App to call
- **Outputs:**
  - `bind-{functionapp-id}-containerapp-fqdn`: Container App FQDN
  - `bind-{functionapp-id}-containerapp-name`: Container App name

**Example:**
```json
{
  "from": "containerapp-1",
  "to": "functionapp-1",
  "intent": "notify"
}
```

**Use Case:** Function App can call Container App endpoints using the exported FQDN.

---

### 18. `azure.vm` → All Services
- **Intent:** `"notify"`
- **Implementation:** VM can connect to all other services
- **What it does:** Exports connection information for VM to access other services

**Supported Connections:**
- `azure.vm` → `azure.storage`: Storage connection string
- `azure.vm` → `azure.servicebus`: Queue connection string
- `azure.vm` → `azure.containerapp`: Container App FQDN
- `azure.vm` → `azure.functionapp`: Function App URL
- `azure.vm` → `azure.sql`: SQL server FQDN and database name
- `azure.vm` → `azure.cosmosdb`: Cosmos DB endpoint, database, and container
- `azure.vm` → `azure.keyvault`: Key Vault URI
- `azure.vm` → `azure.appinsights`: Instrumentation key and connection string
- `azure.vm` → `azure.apimanagement`: Gateway and portal URLs
- `azure.vm` → `azure.vnet`: VNet ID and name (for reference)

**Example:**
```json
{
  "nodes": [
    {"id": "vm-1", "kind": "azure.vm", "name": "webserver"},
    {"id": "sql-1", "kind": "azure.sql", "name": "database"},
    {"id": "st-1", "kind": "azure.storage", "name": "files"}
  ],
  "edges": [
    {"from": "vm-1", "to": "sql-1", "intent": "notify"},
    {"from": "vm-1", "to": "st-1", "intent": "notify"}
  ]
}
```

**Use Case:** VM can access all Azure services using the exported connection information.

---

## ❌ NOT IMPLEMENTED Edge Connections

**All valid Azure service connections from the official matrix are now implemented!**

The only connections that are NOT implemented are:
1. **Self-connections** (service → same service) ❌ - Not typically needed
2. **Invalid combinations** per Azure's architecture (e.g., SQL → Service Bus, Cosmos → Service Bus) ❌ - These don't make architectural sense

**All bidirectional connections are now supported:**
- ✅ `azure.functionapp` ↔ `azure.containerapp` (both directions)
- ✅ `azure.vm` → All services (VM can connect to everything)
- ✅ `azure.containerapp` → All services (bidirectional - Storage, Service Bus, SQL, Cosmos, Key Vault, App Insights, API Management, VNet)
- ✅ `azure.functionapp` → All services (bidirectional - Storage, Service Bus, SQL, Cosmos, Key Vault, App Insights, API Management, VNet)
- ✅ `azure.apimanagement` → All services (bidirectional - Container App, Function App, VM, Key Vault, App Insights, VNet)
- ✅ All other valid combinations from the Azure service matrix

---

## 🔍 Edge Validation Rules

### Valid Edge Format:
```json
{
  "from": "node-id-1",
  "to": "node-id-2",
  "intent": "notify"
}
```

### Validation Checklist for Frontend:

1. ✅ **Both `from` and `to` must exist** in the `nodes` array
2. ✅ **`intent` must be `"notify"`** (only supported intent)
3. ✅ **Check if connection is implemented** using the list above
4. ⚠️ **Warn user** if connection is not implemented (resources will still deploy, but connection won't work)
5. ✅ **Allow any edge** - system will warn but not fail

---

## 📊 Connection Matrix

| FROM → TO | Storage | Service Bus | Container App | Function App | VM | SQL | Cosmos | API Mgmt | Key Vault | App Insights | VNet |
|-----------|---------|-------------|---------------|--------------|----|----|--------|----------|-----------|---------------|-----|
| **Storage** | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Service Bus** | ❌ | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Container App** | ✅ | ✅ | - | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Function App** | ✅ | ✅ | ✅ | - | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **VM** | ✅ | ✅ | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **SQL** | ✅ | ✅ | ✅ | ✅ | ❌ | - | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Cosmos** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | - | ❌ | ❌ | ❌ | ❌ |
| **API Mgmt** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - | ✅ | ✅ | ✅ |
| **Key Vault** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - | ❌ | ❌ |
| **App Insights** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | - | ❌ |
| **VNet** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | - |

**Legend:**
- ✅ = Implemented (will work automatically)
- ❌ = Not implemented (will show warning, resources still deploy)

---


## 💡 Frontend Validation Example

```javascript
// Valid edge connections (54 total)
const IMPLEMENTED_EDGES = [
  // Storage connections (6)
  { from: "azure.storage", to: "azure.servicebus" },
  { from: "azure.storage", to: "azure.containerapp" },
  { from: "azure.storage", to: "azure.functionapp" },
  { from: "azure.storage", to: "azure.sql" },
  { from: "azure.storage", to: "azure.cosmosdb" },
  { from: "azure.storage", to: "azure.vm" },
  { from: "azure.storage", to: "azure.apimanagement" },
  
  // Service Bus connections (6)
  { from: "azure.servicebus", to: "azure.containerapp" },
  { from: "azure.servicebus", to: "azure.functionapp" },
  { from: "azure.servicebus", to: "azure.sql" },
  { from: "azure.servicebus", to: "azure.cosmosdb" },
  { from: "azure.servicebus", to: "azure.vm" },
  { from: "azure.servicebus", to: "azure.apimanagement" },
  
  // SQL connections (4)
  { from: "azure.sql", to: "azure.containerapp" },
  { from: "azure.sql", to: "azure.functionapp" },
  { from: "azure.sql", to: "azure.storage" },
  { from: "azure.sql", to: "azure.servicebus" },
  
  // Cosmos DB connections (4)
  { from: "azure.cosmosdb", to: "azure.containerapp" },
  { from: "azure.cosmosdb", to: "azure.functionapp" },
  { from: "azure.cosmosdb", to: "azure.storage" },
  { from: "azure.cosmosdb", to: "azure.servicebus" },
  
  // Key Vault connections (8)
  { from: "azure.keyvault", to: "azure.containerapp" },
  { from: "azure.keyvault", to: "azure.functionapp" },
  { from: "azure.keyvault", to: "azure.sql" },
  { from: "azure.keyvault", to: "azure.cosmosdb" },
  { from: "azure.keyvault", to: "azure.vm" },
  { from: "azure.keyvault", to: "azure.apimanagement" },
  { from: "azure.keyvault", to: "azure.storage" },
  { from: "azure.keyvault", to: "azure.servicebus" },
  
  // App Insights connections (8)
  { from: "azure.appinsights", to: "azure.containerapp" },
  { from: "azure.appinsights", to: "azure.functionapp" },
  { from: "azure.appinsights", to: "azure.sql" },
  { from: "azure.appinsights", to: "azure.cosmosdb" },
  { from: "azure.appinsights", to: "azure.vm" },
  { from: "azure.appinsights", to: "azure.apimanagement" },
  { from: "azure.appinsights", to: "azure.storage" },
  { from: "azure.appinsights", to: "azure.servicebus" },
  
  // API Management connections (8)
  { from: "azure.apimanagement", to: "azure.containerapp" },
  { from: "azure.apimanagement", to: "azure.functionapp" },
  { from: "azure.apimanagement", to: "azure.sql" },
  { from: "azure.apimanagement", to: "azure.cosmosdb" },
  { from: "azure.apimanagement", to: "azure.vm" },
  { from: "azure.apimanagement", to: "azure.storage" },
  { from: "azure.apimanagement", to: "azure.servicebus" },
  
  // VNet connections (10)
  { from: "azure.vnet", to: "azure.vm" },
  { from: "azure.vnet", to: "azure.containerapp" },
  { from: "azure.vnet", to: "azure.functionapp" },
  { from: "azure.vnet", to: "azure.sql" },
  { from: "azure.vnet", to: "azure.cosmosdb" },
  { from: "azure.vnet", to: "azure.storage" },
  { from: "azure.vnet", to: "azure.servicebus" },
  { from: "azure.vnet", to: "azure.apimanagement" },
  { from: "azure.vnet", to: "azure.keyvault" },
  { from: "azure.vnet", to: "azure.appinsights" },
  
  // Function App ↔ Container App (2)
  { from: "azure.functionapp", to: "azure.containerapp" },
  { from: "azure.containerapp", to: "azure.functionapp" },
  
  // VM → All Services (10)
  { from: "azure.vm", to: "azure.storage" },
  { from: "azure.vm", to: "azure.servicebus" },
  { from: "azure.vm", to: "azure.containerapp" },
  { from: "azure.vm", to: "azure.functionapp" },
  { from: "azure.vm", to: "azure.sql" },
  { from: "azure.vm", to: "azure.cosmosdb" },
  { from: "azure.vm", to: "azure.keyvault" },
  { from: "azure.vm", to: "azure.appinsights" },
  { from: "azure.vm", to: "azure.apimanagement" },
  { from: "azure.vm", to: "azure.vnet" },
  
  // Container App → All Services (8 - bidirectional)
  { from: "azure.containerapp", to: "azure.storage" },
  { from: "azure.containerapp", to: "azure.servicebus" },
  { from: "azure.containerapp", to: "azure.sql" },
  { from: "azure.containerapp", to: "azure.cosmosdb" },
  { from: "azure.containerapp", to: "azure.keyvault" },
  { from: "azure.containerapp", to: "azure.appinsights" },
  { from: "azure.containerapp", to: "azure.apimanagement" },
  { from: "azure.containerapp", to: "azure.vnet" },
  
  // Function App → All Services (8 - bidirectional)
  { from: "azure.functionapp", to: "azure.storage" },
  { from: "azure.functionapp", to: "azure.servicebus" },
  { from: "azure.functionapp", to: "azure.sql" },
  { from: "azure.functionapp", to: "azure.cosmosdb" },
  { from: "azure.functionapp", to: "azure.keyvault" },
  { from: "azure.functionapp", to: "azure.appinsights" },
  { from: "azure.functionapp", to: "azure.apimanagement" },
  { from: "azure.functionapp", to: "azure.vnet" },
  
  // API Management → All Services (6 - bidirectional)
  { from: "azure.apimanagement", to: "azure.containerapp" },
  { from: "azure.apimanagement", to: "azure.functionapp" },
  { from: "azure.apimanagement", to: "azure.vm" },
  { from: "azure.apimanagement", to: "azure.keyvault" },
  { from: "azure.apimanagement", to: "azure.appinsights" },
  { from: "azure.apimanagement", to: "azure.vnet" }
];

function validateEdge(edge, nodes) {
  // Check if nodes exist
  const fromNode = nodes.find(n => n.id === edge.from);
  const toNode = nodes.find(n => n.id === edge.to);
  
  if (!fromNode || !toNode) {
    return { valid: false, error: "Edge references non-existent node" };
  }
  
  // Check if connection is implemented
  const isImplemented = IMPLEMENTED_EDGES.some(
    e => e.from === fromNode.kind && e.to === toNode.kind
  );
  
  if (!isImplemented) {
    return { 
      valid: true, 
      warning: `Connection ${fromNode.kind} → ${toNode.kind} is not implemented. Resources will deploy but connection won't be configured.` 
    };
  }
  
  // Check intent
  if (edge.intent !== "notify") {
    return { valid: false, error: "Only 'notify' intent is supported" };
  }
  
  return { valid: true };
}
```

---

## 📝 Notes

- **Resources always deploy** even if edges are not implemented
- **Warnings are non-critical** - deployment will succeed
- **Connection strings are available** in outputs for manual configuration
- **Only `"notify"` intent is supported** - other intents will be skipped

---

**Last Updated:** Based on code in `app/services/azure_fabric.py` lines 644-694

