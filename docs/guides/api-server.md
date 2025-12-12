# API Server Usage Guide

This guide explains how to use the aipartnerupflow API server for remote task execution and integration.

## Overview

The API server provides:
- **A2A Protocol Server**: Standard agent-to-agent communication protocol (default)
- **MCP Server**: Model Context Protocol server exposing task orchestration as MCP tools and resources
- **HTTP API**: RESTful endpoints for task management
- **Real-time Streaming**: Progress updates via SSE/WebSocket
- **Multi-user Support**: User isolation and authentication

## Starting the API Server

### Basic Startup

```bash
# Start server on default port (8000) with A2A Protocol (default)
aipartnerupflow serve

# Or use the server command
aipartnerupflow-server

# Or use Python module
python -m aipartnerupflow.api.main
```

### Protocol Selection

You can choose which protocol to use via the `AIPARTNERUPFLOW_API_PROTOCOL` environment variable:

```bash
# A2A Protocol Server (default)
export AIPARTNERUPFLOW_API_PROTOCOL=a2a
python -m aipartnerupflow.api.main

# MCP Server
export AIPARTNERUPFLOW_API_PROTOCOL=mcp
python -m aipartnerupflow.api.main
```

**Supported Protocols:**
- `a2a` (default): A2A Protocol Server for agent-to-agent communication
- `mcp`: MCP (Model Context Protocol) Server exposing task orchestration as MCP tools and resources

### Advanced Options

```bash
# Custom host and port
aipartnerupflow serve --host 0.0.0.0 --port 8080

# Enable auto-reload (development)
aipartnerupflow serve --reload

# Multiple workers (production)
aipartnerupflow serve --workers 4

# Custom configuration
aipartnerupflow serve --config config.yaml
```

## API Endpoints

### Protocol Selection

The API server supports multiple protocols:

1. **A2A Protocol** (default): Standard agent-to-agent communication protocol
2. **MCP Protocol**: Model Context Protocol for tool and resource access

### A2A Protocol Endpoints

The API server implements the A2A (Agent-to-Agent) Protocol standard when `AIPARTNERUPFLOW_API_PROTOCOL=a2a` (default).

#### Get Agent Card

```bash
curl http://localhost:8000/.well-known/agent-card
```

Returns agent capabilities and available skills.

#### Execute Task Tree (A2A Protocol)

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "my_task",
          "user_id": "user123",
          "inputs": {"key": "value"}
        }
      ]
    },
    "id": "request-123"
  }'
```

**Note:** The method `execute_task_tree` is still supported for backward compatibility, but `tasks.execute` is the recommended standard method name.

### Task Management via A2A Protocol

All task management operations are now fully supported through the A2A Protocol `/` route:

- **Task Execution**: `tasks.execute` (or `execute_task_tree` for backward compatibility)
- **Task CRUD**: `tasks.create`, `tasks.get`, `tasks.update`, `tasks.delete`
- **Task Query**: `tasks.detail`, `tasks.tree`, `tasks.list`, `tasks.children`
- **Running Tasks**: `tasks.running.list`, `tasks.running.status`, `tasks.running.count`
- **Task Control**: `tasks.cancel`, `tasks.copy`
- **Task Generation**: `tasks.generate` (generate task tree from natural language using LLM)

All methods follow the same A2A Protocol JSON-RPC format and return A2A Protocol Task objects with real-time status updates.

### Task Management Endpoints (Legacy JSON-RPC)

#### Create Tasks

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": {
      "tasks": [...]
    },
    "id": "request-123"
  }'
```

#### Get Task Status

```bash
curl http://localhost:8000/tasks/{task_id}/status
```

#### List Tasks

```bash
curl http://localhost:8000/tasks?user_id=user123
```

## Streaming Support

### Server-Sent Events (SSE)

Use `tasks.execute` with `use_streaming=true` to receive real-time updates via SSE:

```bash
curl -N -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tasks.execute", "params": {"task_id": "task-123", "use_streaming": true}, "id": 1}' \
  http://localhost:8000/tasks
```

The response will be a Server-Sent Events stream with real-time progress updates.

### Copy Before Execution

Use `tasks.execute` with `copy_execution=true` to copy the task before execution, preserving the original task's execution history:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tasks.execute", "params": {"task_id": "task-123", "copy_execution": true}, "id": 1}'
```

To also copy child tasks with their dependencies:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tasks.execute", "params": {"task_id": "task-123", "copy_execution": true, "copy_children": true}, "id": 1}'
```

The response will include both `task_id` (the copied task) and `original_task_id` (the original task).

### WebSocket

Connect via WebSocket for bidirectional communication:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Progress:', update.progress);
};
```

## Client Integration

### Python Client Example

```python
import httpx
import json

# Execute task via API
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/",
        json={
            "jsonrpc": "2.0",
            "method": "tasks.execute",
            "params": {
                "tasks": [
                    {
                        "id": "task1",
                        "name": "my_task",
                        "user_id": "user123",
                        "inputs": {"key": "value"}
                    }
                ]
            },
            "id": "request-123"
        }
    )
    result = response.json()
    print(result)
```

### JavaScript Client Example

```javascript
// Execute task via API
const response = await fetch('http://localhost:8000/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'tasks.execute',
    params: {
      tasks: [
        {
          id: 'task1',
          name: 'my_task',
          user_id: 'user123',
          inputs: { key: 'value' }
        }
      ]
    },
    id: 'request-123'
  })
});

const result = await response.json();
console.log(result);
```

## Authentication

### JWT Authentication (Optional)

The API supports JWT authentication via headers or cookies. You can generate tokens using the `generate_token()` function:

```python
from aipartnerupflow.api.a2a.server import generate_token

# Generate JWT token
payload = {"user_id": "user123", "roles": ["admin"]}
secret_key = "your-secret-key"
token = generate_token(payload, secret_key, expires_in_days=30)
```

**Using Token in Requests:**

```bash
# Method 1: Authorization header (recommended)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Method 2: Cookie (for browser-based clients)
curl -X POST http://localhost:8000/ \
  -H "Cookie: Authorization={token}" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Note:** Authorization header takes priority over cookie if both are present.

## LLM API Key Management

The API server supports dynamic LLM API key injection for CrewAI tasks. Keys can be provided via request headers or user configuration.

### Request Header (Demo/One-time Usage)

For demo or one-time usage, you can provide LLM API keys via the `X-LLM-API-KEY` header:

```bash
# Simple format (auto-detects provider from model)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: sk-your-openai-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": {
      "tasks": [{
        "id": "task1",
        "name": "CrewAI Task",
        "schemas": {"method": "crewai_executor"},
        "params": {
          "works": {
            "agents": {
              "researcher": {
                "role": "Research Analyst",
                "llm": "openai/gpt-4"
              }
            }
          }
        }
      }]
    }
  }'

# Provider-specific format (explicit provider)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: openai:sk-your-openai-key" \
  -d '{...}'

# Anthropic example
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: anthropic:sk-ant-your-key" \
  -d '{...}'
```

**Header Format:**
- Simple: `X-LLM-API-KEY: <api-key>` (provider auto-detected from model name)
- Provider-specific: `X-LLM-API-KEY: <provider>:<api-key>` (e.g., `openai:sk-xxx`, `anthropic:sk-ant-xxx`)

**Supported Providers:**
- `openai` - OpenAI (GPT models)
- `anthropic` - Anthropic (Claude models)
- `google` / `gemini` - Google (Gemini models)
- `mistral` - Mistral AI
- `groq` - Groq
- And more (see LLM Key Injector documentation)

**Priority:**
1. Request header (`X-LLM-API-KEY`) - highest priority
2. User config (if `llm-key-config` extension is installed)
3. Environment variables (automatically read by CrewAI/LiteLLM)

### User Configuration (Multi-user Scenarios)

For production multi-user scenarios, use the `llm-key-config` extension:

```bash
# Install extension
pip install aipartnerupflow[llm-key-config]
```

Then configure keys programmatically:

```python
from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager

# Set user's LLM key
config_manager = LLMKeyConfigManager()
config_manager.set_key(user_id="user123", api_key="sk-xxx", provider="openai")

# Set provider-specific keys
config_manager.set_key(user_id="user123", api_key="sk-xxx", provider="openai")
config_manager.set_key(user_id="user123", api_key="sk-ant-xxx", provider="anthropic")
```

**Note:** Keys are stored in memory (not in database). For production multi-server scenarios, consider using Redis.

### Environment Variables (Fallback)

If no header or user config is provided, CrewAI/LiteLLM will automatically use provider-specific environment variables:

```bash
export OPENAI_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"
export GOOGLE_API_KEY="xxx"
```

### Examples Auto-initialization ⚠️ DEPRECATED

> **Note:** Examples auto-initialization has been removed from aipartnerupflow core library.
> The `_auto_init_examples_if_needed()` function in `api/main.py` is now deprecated and does nothing.
> 
> **Migration:** For demo task initialization, please use the **aipartnerupflow-demo** project instead.
> See [aipartnerupflow-demo](https://github.com/aipartnerup/aipartnerupflow-demo) for complete demo task management.

The examples module and CLI command have been removed. The API server no longer auto-initializes examples on startup.

## Configuration

### Environment Variables

```bash
# Server configuration
export AIPARTNERUPFLOW_HOST=0.0.0.0
export AIPARTNERUPFLOW_PORT=8000

# Database configuration
export AIPARTNERUPFLOW_DATABASE_URL=postgresql://user:pass@localhost/db

# Authentication
export AIPARTNERUPFLOW_JWT_SECRET=your-secret-key
```

### Configuration File

Create `config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4

database:
  url: postgresql://user:pass@localhost/db

auth:
  enabled: true
  jwt_secret: your-secret-key
```

## Production Deployment

### Using Uvicorn Directly

```bash
uvicorn aipartnerupflow.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

### Using Docker

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install aipartnerupflow[a2a]
CMD ["aipartnerupflow-server", "--host", "0.0.0.0", "--port", "8000"]
```

### Using Systemd

Create `/etc/systemd/system/aipartnerupflow.service`:

```ini
[Unit]
Description=aipartnerupflow API Server
After=network.target

[Service]
Type=simple
User=apflow
WorkingDirectory=/opt/aipartnerupflow
ExecStart=/usr/local/bin/aipartnerupflow-server --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
curl http://localhost:8000/metrics
```

## Troubleshooting

### Server Won't Start

- Check if port is already in use
- Verify database connection
- Check logs for errors

### Tasks Not Executing

- Verify executor is registered
- Check task name matches executor ID
- Review server logs

### Connection Issues

- Verify firewall settings
- Check network connectivity
- Ensure server is accessible

## MCP Server

When started with `AIPARTNERUPFLOW_API_PROTOCOL=mcp`, the API server exposes task orchestration capabilities as MCP tools and resources.

### MCP Tools

The MCP server provides 8 tools for task orchestration:

- `execute_task` - Execute tasks or task trees
- `create_task` - Create new tasks or task trees
- `get_task` - Get task details by ID
- `update_task` - Update existing tasks
- `delete_task` - Delete tasks (if all pending)
- `list_tasks` - List tasks with filtering
- `get_task_status` - Get status of running tasks
- `cancel_task` - Cancel running tasks

### MCP Resources

The MCP server provides 2 resource types:

- `task://{task_id}` - Access individual task data
- `tasks://` - Access task list with query parameters (e.g., `tasks://?status=running&limit=10`)

### MCP Endpoints

**HTTP Mode:**
```bash
# POST /mcp - JSON-RPC endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

**stdio Mode:**
```bash
# Run as standalone process
python -m aipartnerupflow.api.mcp.server
```

### MCP Usage Example

```python
# List available tools
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

# Call a tool
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "execute_task",
    "arguments": {
      "task_id": "task-123"
    }
  }
}

# Read a resource
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "task://task-123"
  }
}
```

## Programmatic Usage

For library usage in external projects (e.g., aipartnerupflow-demo), you can import functions from the modular API components:

### Extension Management

```python
from aipartnerupflow.api.extensions import initialize_extensions

# Initialize extensions before creating the app
initialize_extensions(
    include_stdio=True,
    include_crewai=True,
    # ... other extension flags
)
```

### Protocol Management

```python
from aipartnerupflow.api.protocols import (
    get_protocol_from_env,
    check_protocol_dependency,
    get_supported_protocols,
)

# Get protocol from environment or default
protocol = get_protocol_from_env()

# Check if protocol dependencies are installed
check_protocol_dependency(protocol)

# Get list of supported protocols
protocols = get_supported_protocols()  # ['a2a', 'mcp']
```

### Application Creation

```python
from aipartnerupflow.api.app import (
    create_app_by_protocol,
    create_a2a_server,
    create_mcp_server,
)

# Create app with automatic extension initialization
app = create_app_by_protocol(
    protocol="a2a",
    auto_initialize_extensions=True,
    task_routes_class=MyCustomTaskRoutes,  # Optional: custom TaskRoutes
)

# Or create specific server directly
a2a_app = create_a2a_server(
    jwt_secret_key="your-secret",
    base_url="http://localhost:8000",
    auto_initialize_extensions=True,  # New: auto-initialize extensions
    task_routes_class=MyCustomTaskRoutes,  # Optional: custom TaskRoutes
)
```

### Custom TaskRoutes

You can extend `TaskRoutes` functionality without monkey patching:

```python
from aipartnerupflow.api.routes.tasks import TaskRoutes

class MyCustomTaskRoutes(TaskRoutes):
    async def handle_task_create(self, params, request, request_id):
        # Add custom logic before parent implementation
        result = await super().handle_task_create(params, request, request_id)
        # Add custom logic after parent implementation
        return result

# Use custom TaskRoutes when creating the app
app = create_app_by_protocol(
    protocol="a2a",
    task_routes_class=MyCustomTaskRoutes,
)
```

## Next Steps

- See [HTTP API Reference](../api/http.md) for complete endpoint documentation
- Check [Examples](../examples/basic_task.md) for integration examples
- See [Custom Tasks Guide](./custom-tasks.md) for MCP executor usage

