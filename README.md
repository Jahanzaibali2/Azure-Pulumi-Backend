# Azure Infrastructure Composer

A FastAPI backend service that converts graph-based infrastructure definitions (Intermediate Representation) into Azure resources using Pulumi. Define your infrastructure as nodes and edges, then deploy it to Azure with a single API call.

## Overview

This service provides a REST API that accepts infrastructure definitions in a graph format (nodes representing resources, edges representing connections) and automatically provisions Azure resources using Pulumi Azure Native.

### Key Features

- **Graph-based Infrastructure Definition**: Define infrastructure as a graph of nodes (resources) and edges (connections)
- **Multiple Azure Resource Types**: Supports Storage Accounts, Service Bus, and Container Apps
- **Automatic Resource Connections**: Automatically configures Event Grid subscriptions and bindings between resources
- **Preview Before Deploy**: Preview infrastructure changes without deploying
- **Pulumi Integration**: Uses Pulumi Azure Native for reliable infrastructure provisioning

## Prerequisites

- Python 3.8+
- [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/) installed and on PATH
- Azure subscription with appropriate permissions
- Azure Service Principal credentials (for deploying resources)

## Installation

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
  source ./venv/Scripts/activate
   ```

3. **Install dependencies**
   ```bash
   pip install fastapi uvicorn python-dotenv pulumi pulumi-azure-native pydantic
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

## Running the Server

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

## API Endpoints

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

### `POST /up`
Deploy infrastructure to Azure.

**Request Body:** Same as `/preview`

**Response:**
```json
{
  "preview": false,
  "outputs": {
    "resourceGroupName": "...",
    "fabricOutputs": {...}
  },
  "summary": {
    "resources": {...},
    "duration_sec": 45
  }
}
```

### `POST /destroy`
Destroy infrastructure for a given project and environment.

**Request Body:**
```json
{
  "project": "my-project",
  "env": "dev"
}
```

## Infrastructure Definition (IR Format)

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
    },
    {
      "id": "servicebus1",
      "kind": "azure.servicebus",
      "name": "myservicebus",
      "props": {
        "sku": "Basic",
        "queueName": "myqueue",
        "partition": false
      }
    },
    {
      "id": "containerapp1",
      "kind": "azure.containerapp",
      "name": "myapp",
      "props": {
        "image": "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
        "cpu": 0.25,
        "memory": "0.5Gi",
        "env": {
          "ENV_VAR": "value"
        }
      }
    }
  ],
  "edges": [
    {
      "from": "storage1",
      "to": "servicebus1",
      "intent": "notify"
    },
    {
      "from": "servicebus1",
      "to": "containerapp1",
      "intent": "notify"
    }
  ]
}
```

## Supported Resource Types

### `azure.storage`
Creates an Azure Storage Account with optional Blob Container.

**Properties:**
- `accountKind`: Storage account kind (default: "StorageV2")
- `sku`: SKU name (default: "Standard_LRS")
- `containerName`: Optional blob container name

**Outputs:**
- `storage-{name}-accountName`: Storage account name
- `storage-{name}-conn`: Connection string

### `azure.servicebus`
Creates a Service Bus Namespace with Queue and Authorization Rule.

**Properties:**
- `sku`: Service Bus SKU (default: "Basic")
- `queueName`: Queue name
- `partition`: Enable partitioning (default: false)

**Outputs:**
- `servicebus-{name}-queueName`: Queue name
- `servicebus-{name}-conn`: Connection string

### `azure.containerapp`
Creates an Azure Container App with Managed Environment and Log Analytics.

**Properties:**
- `image`: Container image (default: hello-world image)
- `cpu`: CPU allocation (default: 0.25)
- `memory`: Memory allocation (default: "0.5Gi")
- `env`: Environment variables (object)

**Outputs:**
- `containerapp-{name}-fqdn`: Fully qualified domain name

## Resource Connections (Edges)

Edges define relationships between resources:

### Storage → Service Bus
Creates an Event Grid subscription that sends blob creation events to a Service Bus queue.

### Service Bus → Container App
Exports Service Bus connection details as bindings for the container app.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_LOCATION` | Default Azure region | `westeurope` |
| `CORS_ALLOW_ORIGINS` | CORS allowed origins (comma-separated) | `*` |
| `PULUMI_STATE_DIR` | Pulumi state storage directory | `C:\jahanzaib-git\pulumi-state` |
| `PULUMI_HOME` | Pulumi home directory | `C:\jahanzaib-git\.pulumi-home` |
| `PULUMI_WORK_DIR` | Pulumi working directory | `pulumi-work` |

## Architecture

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
│ (pulumi_engine)  │
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

## Project Structure

```
azure_infra_composer_full/
├── app/
│   ├── main.py              # FastAPI application and endpoints
│   ├── models.py            # Pydantic models for IR and requests
│   └── services/
│       ├── azure_fabric.py  # Azure resource creation logic
│       ├── program_builder.py  # Pulumi program construction
│       ├── pulumi_engine.py    # Pulumi automation orchestration
│       ├── naming.py           # Resource name sanitization
│       └── utils.py            # Utility functions
├── pulumi-state/            # Pulumi state storage
├── pulumi-work/             # Pulumi working directory
└── venv/                    # Python virtual environment
```

## Example Usage

### 1. Check Health
```bash
curl http://localhost:8000/health
```

### 2. Preview Infrastructure
```bash
curl -X POST http://localhost:8000/preview \
  -H "Content-Type: application/json" \
  -d @example-ir.json
```

### 3. Deploy Infrastructure
```bash
curl -X POST http://localhost:8000/up \
  -H "Content-Type: application/json" \
  -d @example-ir.json
```

### 4. Destroy Infrastructure
```bash
curl -X POST http://localhost:8000/destroy \
  -H "Content-Type: application/json" \
  -d '{"project": "my-project", "env": "dev"}'
```

## Security Notes

- Azure credentials are passed in request bodies and should be transmitted over HTTPS in production
- The Pulumi passphrase is set to `local-dev-only` by default - change this in production
- CORS is configured to allow all origins by default - restrict this in production

## Troubleshooting

### Pulumi CLI not found
Ensure Pulumi CLI is installed and available on your PATH:
```bash
pulumi version
```

### Azure authentication errors
Verify your Azure Service Principal credentials are correct and have the necessary permissions.

### State directory issues
Ensure the `PULUMI_STATE_DIR` directory exists and is writable.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

