# Azure Infrastructure Composer

A FastAPI backend service that converts graph-based infrastructure definitions (Intermediate Representation) into Azure resources using Pulumi. Define your infrastructure as nodes and edges, then deploy it to Azure with a single API call.

## 📋 Table of Contents

- [Overview](#overview)
- [Current Status](#current-status)
- [Supported Resources](#supported-resources)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Infrastructure Definition (IR Format)](#infrastructure-definition-ir-format)
- [Resource Connections (Edges)](#resource-connections-edges)
- [Example Payloads](#example-payloads)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## 🎯 Overview

This service provides a REST API that accepts infrastructure definitions in a graph format (nodes representing resources, edges representing connections) and automatically provisions Azure resources using Pulumi Azure Native.

### Key Features

- **Graph-based Infrastructure Definition**: Define infrastructure as a graph of nodes (resources) and edges (connections)
- **11 Azure Resource Types**: Supports Storage, Service Bus, Container Apps, VMs, Function Apps, SQL, Cosmos DB, API Management, Key Vault, Application Insights, and Virtual Networks
- **Automatic Resource Connections**: Automatically configures Event Grid subscriptions and bindings between resources
- **Preview Before Deploy**: Preview infrastructure changes without deploying
- **Enhanced Destroy API**: Delete resources via Pulumi or direct Azure REST API
- **Pulumi Integration**: Uses Pulumi Azure Native for reliable infrastructure provisioning
- **Registry Pattern**: Extensible service creation using a registry pattern

---

## 📊 Current Status

### ✅ What's Working

- **11 Major Services** are fully implemented and tested:
  1. Storage Account (S3 equivalent)
  2. Service Bus (SQS equivalent)
  3. Container App (ECS/Fargate equivalent)
  4. Virtual Machine (EC2 equivalent)
  5. Function App (Lambda equivalent)
  6. SQL Database (RDS equivalent)
  7. Cosmos DB (DynamoDB equivalent)
  8. API Management (API Gateway equivalent)
  9. Key Vault (Secrets Manager equivalent)
  10. Application Insights (CloudWatch equivalent)
  11. Virtual Network (VPC equivalent)

- **Resource Connections**: Storage → Service Bus → Container App/Function App
- **Destroy API**: Enhanced with direct Azure REST API fallback
- **Preview API**: Fully functional for all services

### ❌ Removed Services

The following services were **removed from the codebase** due to deployment failures:
- **App Service** (`azure.appservice`) - Removed due to runtime configuration issues
- **Redis Cache** (`azure.redis`) - Removed due to deployment timeouts

**Note:** These services can be re-added in the future if needed, but are not currently available.

### 🔄 Current State

- **Code Status**: Clean and production-ready with 11 working services
- **Registry Pattern**: Implemented for easy extensibility
- **Error Handling**: Comprehensive error handling and fallback mechanisms
- **Documentation**: Complete API documentation and examples

---

## 🎯 Supported Resources

### Available Services (11 Total)

| Service Kind | Azure Resource | AWS Equivalent | Status |
|--------------|----------------|-----------------|--------|
| `azure.storage` | Storage Account | S3 | ✅ Working |
| `azure.servicebus` | Service Bus Namespace | SQS/SNS | ✅ Working |
| `azure.containerapp` | Container App | ECS/Fargate | ✅ Working |
| `azure.vm` | Virtual Machine | EC2 | ✅ Working |
| `azure.functionapp` | Function App | Lambda | ✅ Working |
| `azure.sql` | SQL Database | RDS | ✅ Working |
| `azure.cosmosdb` | Cosmos DB | DynamoDB | ✅ Working |
| `azure.apimanagement` | API Management | API Gateway | ✅ Working |
| `azure.keyvault` | Key Vault | Secrets Manager | ✅ Working |
| `azure.appinsights` | Application Insights | CloudWatch | ✅ Working |
| `azure.vnet` | Virtual Network | VPC | ✅ Working |

### Resource Properties

Each service supports specific properties. See [Infrastructure Definition](#infrastructure-definition-ir-format) section for details.

### Mix and Match

**You can use ANY combination of services!** You don't need to use all 11 services. Just include the ones you need for your specific use case.

- ✅ Use just 1 service
- ✅ Use any combination
- ✅ Use all 11 services
- ✅ Edges are optional (can be empty `[]`)

---

## 📦 Prerequisites

- Python 3.8+
- [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/) installed and on PATH
- Azure subscription with appropriate permissions
- Azure Service Principal credentials (for deploying resources)

---

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd azure_infra_composer_full
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # Linux/Mac
   source venv/Scripts/activate
   ```

3. **Install dependencies**
   ```bash
   pip install fastapi uvicorn python-dotenv pulumi pulumi-azure-native pydantic requests
   ```

4. **Set up environment variables** (optional)
   
   Create a `.env` file in the project root:
   ```env
   AZURE_LOCATION=westeurope
   CORS_ALLOW_ORIGINS=*
   PULUMI_STATE_DIR=C:\jahanzaib-git\pulumi-state
   PULUMI_HOME=C:\jahanzaib-git\.pulumi-home
   PULUMI_WORK_DIR=pulumi-work
   ```

---

## 🏃 Running the Server

```bash
# Activate virtual environment
.\venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔌 API Endpoints

### `GET /health`
Health check endpoint that returns server status and configuration.

**Response:**
```json
{
  "status": "ok",
  "locationDefault": "westeurope",
  "pulumiOnPath": true,
  "backend": "file://C:/jahanzaib-git/pulumi-state"
}
```

### `POST /preview`
Preview infrastructure changes without deploying.

**Request Body:**
```json
{
  "ir": {
    "project": "my-project",
    "env": "dev",
    "location": "westeurope",
    "nodes": [...],
    "edges": [...]
  },
  "creds": {
    "clientId": "...",
    "clientSecret": "...",
    "tenantId": "...",
    "subscriptionId": "..."
  }
}
```

**Response:** Returns a preview of what will be created/updated/deleted.

### `POST /up`
Deploy infrastructure to Azure.

**Request Body:** Same as `/preview`

**Response:**
```json
{
  "preview": false,
  "outputs": {
    "resourceGroupName": "rg-my-project-dev",
    "fabricOutputs": {
      "storage-mystorage-accountName": "...",
      "storage-mystorage-conn": "...",
      ...
    }
  },
  "summary": {
    "resources": {
      "create": 10,
      "update": 0,
      "delete": 0
    },
    "duration_sec": 45
  }
}
```

### `POST /destroy`
Destroy infrastructure for a given project and environment.

**Enhanced Features:**
- Tries Pulumi destroy first (if stack exists)
- Falls back to direct Azure REST API deletion if Pulumi stack is missing
- Requires Azure credentials for direct deletion

**Request Body:**
```json
{
  "project": "my-project",
  "env": "dev",
  "creds": {
    "clientId": "...",
    "clientSecret": "...",
    "tenantId": "...",
    "subscriptionId": "..."
  }
}
```

**Response:**
```json
{
  "destroyed": true,
  "resources_deleted": 10,
  "message": "Destroyed 10 resources via Pulumi. Deletion may take 5-10 minutes to complete in Azure.",
  "resource_group": "rg-my-project-dev"
}
```

**Note:** If Pulumi stack doesn't exist, the API will attempt direct Azure REST API deletion if credentials are provided.

---

## 📝 Infrastructure Definition (IR Format)

The Intermediate Representation (IR) is a graph-based format for defining infrastructure:

```json
{
  "project": "my-project",
  "env": "dev",
  "location": "westeurope",
  "nodes": [
    {
      "id": "storage1",
      "kind": "azure.storage",
      "name": "mystorage",
      "props": {
        "accountKind": "StorageV2",
        "sku": "Standard_LRS",
        "containerName": "mycontainer"
      }
    }
  ],
  "edges": [
    {
      "from": "storage1",
      "to": "servicebus1",
      "intent": "notify"
    }
  ]
}
```

### Node Properties by Service

#### `azure.storage`
- `accountKind`: Storage account kind (default: "StorageV2")
- `sku`: SKU name (default: "Standard_LRS")
- `containerName`: Optional blob container name

#### `azure.servicebus`
- `sku`: Service Bus SKU (default: "Basic", options: "Basic", "Standard", "Premium")
- `queueName`: Queue name
- `partition`: Enable partitioning (default: false)

#### `azure.containerapp`
- `image`: Container image (default: hello-world image)
- `cpu`: CPU allocation (default: 0.25)
- `memory`: Memory allocation (default: "0.5Gi")
- `env`: Environment variables (object)

#### `azure.vm`
- `vmSize`: VM size (default: "Standard_B1s")
- `adminUsername`: Admin username
- `adminPassword`: Admin password
- `osType`: "Linux" or "Windows" (default: "Linux")

#### `azure.functionapp`
- `sku`: Function App SKU (default: "Y1" for Consumption)

#### `azure.sql`
- `databaseName`: Database name
- `sku`: SKU configuration (e.g., `{"name": "Basic", "tier": "Basic"}`)

#### `azure.cosmosdb`
- `databaseName`: Database name
- `containerName`: Container name
- `partitionKey`: Partition key path (e.g., "/id")

#### `azure.apimanagement`
- `publisherName`: Publisher name
- `publisherEmail`: Publisher email
- `sku`: SKU name (default: "Developer")

#### `azure.keyvault`
- `tenantId`: Azure tenant ID

#### `azure.appinsights`
- No required properties (uses defaults)

#### `azure.vnet`
- `addressSpaces`: Array of address spaces (e.g., `["10.0.0.0/16"]`)
- `subnets`: Array of subnet objects with `name` and `addressPrefix`

---

## 🔗 Resource Connections (Edges)

Edges define relationships between resources. The `edges` array can be:
- **Empty `[]`**: Resources are independent (no automatic connections)
- **Populated**: Resources are connected via Event Grid, bindings, etc.

### Supported Edge Types

#### 1. Storage → Service Bus (`"intent": "notify"`)
- **Creates:** Event Grid subscription
- **Result:** When a blob is created in storage, an event is sent to Service Bus queue

#### 2. Service Bus → Container App (`"intent": "notify"`)
- **Creates:** Connection string bindings
- **Result:** Container app can access queue name and connection string

#### 3. Service Bus → Function App (`"intent": "notify"`)
- **Creates:** Connection string bindings
- **Result:** Function app can access queue name and connection string

### Example with Edges

```json
{
  "nodes": [
    {"id": "st-1", "kind": "azure.storage", "name": "files"},
    {"id": "sb-1", "kind": "azure.servicebus", "name": "events"},
    {"id": "app-1", "kind": "azure.containerapp", "name": "processor"}
  ],
  "edges": [
    {
      "from": "st-1",
      "to": "sb-1",
      "intent": "notify"
    },
    {
      "from": "sb-1",
      "to": "app-1",
      "intent": "notify"
    }
  ]
}
```

**What this does:**
- File uploaded to storage → Event sent to Service Bus → Container App receives notification
- Creates an **event-driven pipeline**

---

## 📋 Example Payloads

### Simple Example: Storage Only

```json
{
  "ir": {
    "project": "simple-storage",
    "env": "dev",
    "location": "westeurope",
    "nodes": [
      {
        "id": "st-1",
        "kind": "azure.storage",
        "name": "mystorage",
        "props": {
          "containerName": "uploads"
        }
      }
    ],
    "edges": []
  },
  "creds": {
    "clientId": "your-client-id",
    "clientSecret": "your-client-secret",
    "subscriptionId": "your-subscription-id",
    "tenantId": "your-tenant-id"
  }
}
```

### Serverless API Example

```json
{
  "ir": {
    "project": "serverless-api",
    "env": "prod",
    "location": "southeastasia",
    "nodes": [
      {
        "id": "func-1",
        "kind": "azure.functionapp",
        "name": "api",
        "props": {
          "sku": "Y1"
        }
      },
      {
        "id": "cosmos-1",
        "kind": "azure.cosmosdb",
        "name": "database",
        "props": {
          "databaseName": "appdb",
          "containerName": "users",
          "partitionKey": "/id"
        }
      },
      {
        "id": "apim-1",
        "kind": "azure.apimanagement",
        "name": "gateway",
        "props": {
          "publisherName": "MyCompany",
          "publisherEmail": "admin@mycompany.com"
        }
      },
      {
        "id": "appi-1",
        "kind": "azure.appinsights",
        "name": "monitoring"
      }
    ],
    "edges": []
  },
  "creds": {
    "clientId": "your-client-id",
    "clientSecret": "your-client-secret",
    "subscriptionId": "your-subscription-id",
    "tenantId": "your-tenant-id"
  }
}
```

### Full Architecture Example (All 11 Services)

```json
{
  "ir": {
    "project": "full-stack-app",
    "env": "prod",
    "location": "southeastasia",
    "nodes": [
      {
        "id": "st-1",
        "kind": "azure.storage",
        "name": "main-storage",
        "props": {
          "containerName": "uploads",
          "sku": "Standard_LRS"
        }
      },
      {
        "id": "sb-1",
        "kind": "azure.servicebus",
        "name": "message-bus",
        "props": {
          "queueName": "tasks",
          "sku": "Standard"
        }
      },
      {
        "id": "app-1",
        "kind": "azure.containerapp",
        "name": "worker",
        "props": {
          "image": "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
          "cpu": 0.5,
          "memory": "1Gi",
          "env": {
            "LOG_LEVEL": "info"
          }
        }
      },
      {
        "id": "vm-1",
        "kind": "azure.vm",
        "name": "webserver",
        "props": {
          "vmSize": "Standard_B1s",
          "adminUsername": "admin",
          "adminPassword": "SecurePass123!",
          "osType": "Linux"
        }
      },
      {
        "id": "func-1",
        "kind": "azure.functionapp",
        "name": "api-functions",
        "props": {
          "sku": "Y1"
        }
      },
      {
        "id": "sql-1",
        "kind": "azure.sql",
        "name": "main-db",
        "props": {
          "databaseName": "appdb",
          "sku": {
            "name": "Basic",
            "tier": "Basic"
          }
        }
      },
      {
        "id": "cosmos-1",
        "kind": "azure.cosmosdb",
        "name": "nosql-db",
        "props": {
          "databaseName": "appdb",
          "containerName": "users",
          "partitionKey": "/id"
        }
      },
      {
        "id": "apim-1",
        "kind": "azure.apimanagement",
        "name": "api-gateway",
        "props": {
          "publisherName": "MyCompany",
          "publisherEmail": "admin@mycompany.com"
        }
      },
      {
        "id": "kv-1",
        "kind": "azure.keyvault",
        "name": "secrets",
        "props": {
          "tenantId": "your-tenant-id"
        }
      },
      {
        "id": "appi-1",
        "kind": "azure.appinsights",
        "name": "monitoring"
      },
      {
        "id": "vnet-1",
        "kind": "azure.vnet",
        "name": "network",
        "props": {
          "addressSpaces": ["10.0.0.0/16"],
          "subnets": [
            {"name": "subnet1", "addressPrefix": "10.0.1.0/24"},
            {"name": "subnet2", "addressPrefix": "10.0.2.0/24"}
          ]
        }
      }
    ],
    "edges": [
      {
        "from": "st-1",
        "to": "sb-1",
        "intent": "notify"
      },
      {
        "from": "sb-1",
        "to": "app-1",
        "intent": "notify"
      },
      {
        "from": "sb-1",
        "to": "func-1",
        "intent": "notify"
      }
    ]
  },
  "creds": {
    "clientId": "your-client-id",
    "clientSecret": "your-client-secret",
    "subscriptionId": "your-subscription-id",
    "tenantId": "your-tenant-id"
  }
}
```

---

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────────┐
│  FastAPI Server │
│   (main.py)     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  PulumiEngine   │
│ (pulumi_engine) │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Program Builder │
│(program_builder) │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Azure Fabric   │
│ (azure_fabric)  │
│  (Registry)     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Pulumi Azure    │
│     Native      │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  Azure Cloud    │
└─────────────────┘
```

### Key Components

1. **FastAPI Server** (`app/main.py`): Handles HTTP requests and routes to appropriate handlers
2. **PulumiEngine** (`app/services/pulumi_engine.py`): Orchestrates Pulumi stack operations (preview, up, destroy)
3. **Program Builder** (`app/services/program_builder.py`): Constructs Pulumi programs from IR
4. **Azure Fabric** (`app/services/azure_fabric.py`): Creates Azure resources using registry pattern
5. **Naming Service** (`app/services/naming.py`): Sanitizes resource names for Azure requirements

### Registry Pattern

The `AzureFabric` class uses a registry pattern for extensible service creation:

```python
self._service_registry: Dict[str, callable] = {
    "azure.storage": self._create_storage,
    "azure.servicebus": self._create_servicebus,
    # ... more services
}
```

To add a new service:
1. Implement `_create_<service>` method
2. Add entry to `_service_registry`
3. Add necessary imports

---

## 📁 Project Structure

```
azure_infra_composer_full/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and endpoints
│   ├── models.py            # Pydantic models for IR and requests
│   └── services/
│       ├── __init__.py
│       ├── azure_fabric.py  # Azure resource creation logic (Registry)
│       ├── program_builder.py  # Pulumi program construction
│       ├── pulumi_engine.py    # Pulumi automation orchestration
│       ├── naming.py           # Resource name sanitization
│       └── utils.py            # Utility functions
├── pulumi-state/            # Pulumi state storage
├── pulumi-work/             # Pulumi working directory
├── venv/                    # Python virtual environment
├── .env                     # Environment variables (optional)
└── README.md                # This file
```

---

## 🔧 Troubleshooting

### Pulumi CLI not found
Ensure Pulumi CLI is installed and available on your PATH:
```bash
pulumi version
```

### Azure authentication errors
Verify your Azure Service Principal credentials are correct and have the necessary permissions:
- Contributor role on the subscription
- Ability to create resource groups

### State directory issues
Ensure the `PULUMI_STATE_DIR` directory exists and is writable.

### Resource name conflicts
Azure resource names must be globally unique. If you get "already taken" errors:
- Use more unique names
- Add random suffixes
- Use different regions

### Destroy API not working
- Ensure the server is running
- Provide valid Azure credentials for direct deletion
- Check that resource groups exist in Azure Portal

### Deployment failures
Common issues:
- **Quota limits**: Check Azure subscription quotas
- **Region availability**: Some services may not be available in all regions
- **SKU restrictions**: Some SKUs may not be available in your subscription
- **Configuration errors**: Check property values match Azure requirements

---

## 🔒 Security Notes

- **Azure credentials** are passed in request bodies and should be transmitted over HTTPS in production
- **The Pulumi passphrase** is set to `local-dev-only` by default - change this in production
- **CORS** is configured to allow all origins by default - restrict this in production
- **Never commit credentials** to version control
- **Rotate secrets** regularly, especially if exposed

### Production Recommendations

1. Use environment variables for Azure credentials
2. Implement authentication/authorization for API endpoints
3. Use HTTPS/TLS for all API communication
4. Restrict CORS to specific origins
5. Use Azure Key Vault for secret management
6. Implement rate limiting
7. Add logging and monitoring
8. Use managed identities where possible

---

## 📚 Additional Resources

- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [Pulumi Azure Native](https://www.pulumi.com/registry/packages/azure-native/)
- [Azure REST API Reference](https://docs.microsoft.com/en-us/rest/api/azure/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🎯 Use Cases

### 1. Simple Static Website
- Use: `azure.storage` with static website hosting
- Or: `azure.vm` with web server

### 2. E-Commerce Backend
- Use: `azure.functionapp`, `azure.cosmosdb`, `azure.redis`, `azure.storage`
- Connect: Function App → Cosmos DB, Storage → Function App

### 3. Microservices Architecture
- Use: Multiple `azure.containerapp`, `azure.servicebus`, `azure.apimanagement`
- Connect: Service Bus → Container Apps, API Management as gateway

### 4. Full-Stack Application
- Use: All 11 services
- Connect: Storage → Service Bus → Container App/Function App
- Network: Virtual Network for isolation

---

## 🚀 Next Steps

1. **Start Small**: Test with 1-3 services first
2. **Add Gradually**: Add more services as needed
3. **Connect Resources**: Use edges to create workflows
4. **Deploy**: Use `/up` API when ready
5. **Monitor**: Use Application Insights to monitor deployments
6. **Extend**: Add new services using the registry pattern

---

## 📝 License

[Add your license here]

---

## 🤝 Contributing

[Add contribution guidelines here]

---

## 📞 Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Azure Portal for resource status
3. Check Pulumi state files for deployment history
4. Review API responses for detailed error messages

---

**Last Updated:** 2025-01-27  
**Version:** 0.2.0  
**Status:** Production Ready (11 Services)
