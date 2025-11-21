# API Reference

This document provides a complete reference for the aipartnerupflow API, which implements the **A2A (Agent-to-Agent) Protocol** standard.

## Overview

The aipartnerupflow API server provides:
- **A2A Protocol Server**: Standard agent-to-agent communication protocol
- **Task Management**: Create, read, update, and delete tasks
- **Task Execution**: Execute task trees with dependency management
- **Real-time Streaming**: Progress updates via EventQueue (SSE/WebSocket)
- **JWT Authentication**: Optional token-based authentication

## Base URL

```
http://localhost:8000  # Default development server
```

## Endpoints

### A2A Protocol Endpoints

#### `GET /.well-known/agent-card`

Get the agent card describing the service capabilities.

**Response:**
```json
{
  "name": "aipartnerupflow",
  "description": "Agent workflow orchestration and execution platform",
  "url": "http://localhost:8000",
  "version": "0.2.0",
  "capabilities": {
    "streaming": true,
    "push_notifications": true
  },
  "skills": [
    {
      "id": "execute_task_tree",
      "name": "Execute Task Tree",
      "description": "Execute a complete task tree with multiple tasks",
      "tags": ["task", "orchestration", "workflow"]
    }
  ]
}
```

#### `POST /`

Main A2A Protocol RPC endpoint. Handles all A2A protocol requests.

**Request Format:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {
    "tasks": [...]
  },
  "id": "request-123"
}
```

**Response Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "status": "completed",
    "root_task_id": "task-abc-123",
    "progress": 1.0
  }
}
```

### Task Management Endpoints

#### `POST /tasks`

Task management endpoint. Supports multiple task operations via JSON-RPC 2.0 format.

**Request Format:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.create",
  "params": {
    "tasks": [
      {
        "id": "task1",
        "name": "Task 1",
        "user_id": "user123",
        "schemas": {
          "method": "executor_id"
        },
        "inputs": {
          "key": "value"
        }
      }
    ]
  },
  "id": "request-123"
}
```

## Task Management Methods

All task management methods use the `/tasks` endpoint with JSON-RPC 2.0 format.

### `tasks.create`

Create one or more tasks and execute them.

**Method:** `tasks.create`

**Parameters:**
- `tasks` (array, required): Array of task objects, or single task object (will be converted to array)

**Task Object Fields:**
- `id` (string, optional): Task ID. If not provided, auto-generated UUID will be used
- `name` (string, required): Task name
- `user_id` (string, optional): User ID for multi-user scenarios
- `parent_id` (string, optional): Parent task ID for task tree structure
- `priority` (integer, optional): Priority level (0=urgent, 1=high, 2=normal, 3=low). Default: 1
- `dependencies` (array, optional): Dependency list. Format: `[{"id": "task-id", "required": true}]`
- `inputs` (object, optional): Execution-time input parameters
- `schemas` (object, optional): Task schemas. Must include `method` field with executor ID
- `params` (object, optional): Executor initialization parameters
- Custom fields: Any additional fields supported by your TaskModel

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.create",
  "params": [
    {
      "id": "root",
      "name": "Root Task",
      "user_id": "user123",
      "schemas": {
        "method": "my_executor"
      },
      "inputs": {
        "data": "test"
      }
    },
    {
      "id": "child",
      "name": "Child Task",
      "user_id": "user123",
      "parent_id": "root",
      "schemas": {
        "method": "another_executor"
      },
      "inputs": {}
    }
  ],
  "id": "create-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "create-request-1",
  "result": {
    "status": "completed",
    "root_task_id": "root",
    "progress": 1.0,
    "task_count": 2
  }
}
```

### `tasks.get`

Get task details by ID.

**Method:** `tasks.get`

**Parameters:**
- `task_id` (string, required): Task ID to retrieve

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.get",
  "params": {
    "task_id": "task-abc-123"
  },
  "id": "get-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "get-request-1",
  "result": {
    "id": "task-abc-123",
    "name": "Task 1",
    "status": "completed",
    "progress": 1.0,
    "inputs": {...},
    "result": {...},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z"
  }
}
```

### `tasks.update`

Update task properties.

**Method:** `tasks.update`

**Parameters:**
- `task_id` (string, required): Task ID to update
- `status` (string, optional): New status
- `inputs` (object, optional): Updated input parameters
- `result` (object, optional): Updated result
- `error` (string, optional): Error message
- `progress` (float, optional): Progress (0.0 to 1.0)
- `started_at` (string, optional): Start timestamp (ISO format)
- `completed_at` (string, optional): Completion timestamp (ISO format)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.update",
  "params": {
    "task_id": "task-abc-123",
    "status": "in_progress",
    "progress": 0.5
  },
  "id": "update-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "update-request-1",
  "result": {
    "id": "task-abc-123",
    "status": "in_progress",
    "progress": 0.5,
    ...
  }
}
```

### `tasks.delete`

Delete a task (marks as deleted).

**Method:** `tasks.delete`

**Parameters:**
- `task_id` (string, required): Task ID to delete

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.delete",
  "params": {
    "task_id": "task-abc-123"
  },
  "id": "delete-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-request-1",
  "result": {
    "success": true,
    "task_id": "task-abc-123"
  }
}
```

### `tasks.copy`

Create a copy of a task tree for re-execution.

This method creates a new executable copy of an existing task tree, including:
- The original task and all its children
- All tasks that depend on the original task (including transitive dependencies)
- Automatically handles failed leaf nodes (filters out pending dependents)

The copied tasks are linked to the original task via `original_task_id` field. All execution-specific fields (status, result, progress, etc.) are reset to initial values.

**Method:** `tasks.copy`

**Parameters:**
- `task_id` (string, required): ID of the task to copy (can be root or any task in tree)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123"
  },
  "id": "copy-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "copy-request-1",
  "result": {
    "id": "task-copy-xyz-789",
    "name": "Original Task Name",
    "original_task_id": "task-abc-123",
    "status": "pending",
    "progress": 0.0,
    "children": [
      {
        "id": "child-copy-456",
        "name": "Child Task",
        "original_task_id": "task-abc-123",
        "status": "pending",
        "progress": 0.0
      }
    ]
  }
}
```

**Notes:**
- The copied task tree has new task IDs but preserves the original structure
- All execution fields are reset (status="pending", progress=0.0, result=null)
- The original task's `has_copy` flag is set to `true`
- Use the returned task tree's root ID to execute the copied tasks

### `tasks.detail`

Get detailed task information (same as `tasks.get`).

**Method:** `tasks.detail`

**Parameters:**
- `task_id` (string, required): Task ID

### `tasks.tree`

Get task tree structure starting from a task.

**Method:** `tasks.tree`

**Parameters:**
- `task_id` (string, optional): Task ID (will find root if task has parent)
- `root_id` (string, optional): Alternative to `task_id`

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.tree",
  "params": {
    "task_id": "child-task-id"
  },
  "id": "tree-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "tree-request-1",
  "result": {
    "id": "root-task-id",
    "name": "Root Task",
    "children": [
      {
        "id": "child-task-id",
        "name": "Child Task",
        "children": []
      }
    ]
  }
}
```

### `tasks.running.list`

List currently running tasks.

**Method:** `tasks.running.list`

**Parameters:**
- `user_id` (string, optional): Filter by user ID
- `limit` (integer, optional): Maximum number of tasks to return (default: 100)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.running.list",
  "params": {
    "user_id": "user123",
    "limit": 50
  },
  "id": "list-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "list-request-1",
  "result": [
    {
      "id": "task-1",
      "name": "Task 1",
      "status": "in_progress",
      "progress": 0.3
    },
    {
      "id": "task-2",
      "name": "Task 2",
      "status": "in_progress",
      "progress": 0.7
    }
  ]
}
```

### `tasks.running.status`

Get status of one or more running tasks.

**Method:** `tasks.running.status`

**Parameters:**
- `task_ids` (array, required): Array of task IDs to check

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.running.status",
  "params": {
    "task_ids": ["task-1", "task-2"]
  },
  "id": "status-request-1"
}
```

### `tasks.running.count`

Get count of running tasks.

**Method:** `tasks.running.count`

**Parameters:**
- `user_id` (string, optional): Filter by user ID

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.running.count",
  "params": {
    "user_id": "user123"
  },
  "id": "count-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "count-request-1",
  "result": {
    "count": 5,
    "user_id": "user123"
  }
}
```

### `tasks.cancel` / `tasks.running.cancel`

Cancel one or more running tasks.

**Method:** `tasks.cancel` or `tasks.running.cancel`

**Parameters:**
- `task_ids` (array, required): Array of task IDs to cancel
- `force` (boolean, optional): Force immediate cancellation (default: false)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.cancel",
  "params": {
    "task_ids": ["task-1", "task-2"],
    "force": false
  },
  "id": "cancel-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "cancel-request-1",
  "result": [
    {
      "task_id": "task-1",
      "status": "cancelled",
      "message": "Task cancelled successfully"
    },
    {
      "task_id": "task-2",
      "status": "cancelled",
      "message": "Task cancelled successfully"
    }
  ]
}
```

## System Endpoints

### `POST /system`

System operations endpoint.

#### `system.health`

Check system health status.

**Method:** `system.health`

**Parameters:** None

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "system.health",
  "params": {},
  "id": "health-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "health-request-1",
  "result": {
    "status": "healthy",
    "version": "0.2.0",
    "uptime": 3600
  }
}
```

## Authentication

### JWT Authentication

The API supports optional JWT authentication. To enable:

1. Set environment variable `AIPARTNERUPFLOW_JWT_SECRET_KEY`
2. Include JWT token in request headers: `Authorization: Bearer <token>`

**Token Format:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Payload:**
```json
{
  "user_id": "user123",
  "roles": ["admin"],
  "exp": 1234567890
}
```

**Permission Checking:**
- If `roles` contains `"admin"`, user can access any task
- Otherwise, user can only access tasks with matching `user_id`
- If no `user_id` in token, permission checking is skipped

## Error Responses

All endpoints return JSON-RPC 2.0 error format on failure:

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": "Error details"
  }
}
```

**Error Codes:**
- `-32600`: Invalid Request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32000`: Server error (custom)

## Streaming Support

The API supports real-time progress updates via A2A Protocol's EventQueue:

- **SSE (Server-Sent Events)**: `/events` endpoint
- **WebSocket**: `ws://localhost:8000/ws`

**Event Format:**
```json
{
  "type": "task_progress",
  "task_id": "task-abc-123",
  "data": {
    "progress": 0.5,
    "status": "in_progress"
  }
}
```

## Examples

### Complete Example: Create and Execute Task Tree

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": [
      {
        "id": "root",
        "name": "Root Task",
        "user_id": "user123",
        "schemas": {"method": "my_executor"},
        "inputs": {"data": "test"}
      },
      {
        "id": "child",
        "name": "Child Task",
        "user_id": "user123",
        "parent_id": "root",
        "schemas": {"method": "another_executor"},
        "inputs": {}
      }
    ],
    "id": "1"
  }'
```

### Example with Authentication

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.get",
    "params": {
      "task_id": "task-abc-123"
    },
    "id": "2"
  }'
```

## CustomA2AStarletteApplication Custom Routes

The `CustomA2AStarletteApplication` extends the standard A2A Starlette Application with additional custom routes for task management and system operations.

### Custom Routes Overview

The custom application adds the following routes:

1. **`POST /tasks`** - Task management endpoint (see [Task Management Endpoints](#task-management-endpoints))
2. **`POST /system`** - System operations endpoint (see [System Endpoints](#system-endpoints))

These routes are enabled by default when using `CustomA2AStarletteApplication`. To disable them, set `enable_system_routes=False` when creating the application.

### Initialization

```python
from aipartnerupflow.api.a2a.server import create_a2a_server

# Create A2A server with custom routes enabled (default)
app = create_a2a_server(
    verify_token_secret_key="your-secret-key",  # Optional: JWT authentication
    base_url="http://localhost:8000",
    enable_system_routes=True  # Enable custom routes (default: True)
)
```

### JWT Authentication

The custom application supports optional JWT authentication via middleware:

```python
from aipartnerupflow.api.a2a.server import create_a2a_server

def verify_token(token: str) -> Optional[dict]:
    """Custom JWT token verification function"""
    # Your token verification logic
    return payload if valid else None

app = create_a2a_server(
    verify_token_func=verify_token,
    enable_system_routes=True
)
```

## A2A Protocol Features

### Push Notification Configuration (Callback Mode)

The A2A protocol supports push notifications via `configuration.push_notification_config`. This allows the server to send task execution updates to a callback URL instead of waiting for polling.

#### How It Works

When `configuration.push_notification_config` is provided in the A2A request, the server will:

1. Execute tasks in **callback mode** (asynchronous)
2. Send task status updates to the configured callback URL
3. Return immediately with an initial response

#### Configuration Format

The `push_notification_config` should be included in the request's `configuration` field:

```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {
    "tasks": [...]
  },
  "configuration": {
    "push_notification_config": {
      "url": "https://your-server.com/callback",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  },
  "id": "request-123"
}
```

#### Push Notification Config Fields

- `url` (string, required): Callback URL where status updates will be sent
- `headers` (object, optional): HTTP headers to include in callback requests
- `method` (string, optional): HTTP method for callback (default: "POST")

#### Callback Payload Format

The server will send POST requests to your callback URL with the following payload:

```json
{
  "task_id": "task-abc-123",
  "context_id": "context-xyz-456",
  "status": {
    "state": "completed",
    "message": {
      "role": "agent",
      "parts": [
        {
          "kind": "data",
          "data": {
            "status": "completed",
            "progress": 1.0,
            "root_task_id": "task-abc-123",
            "task_count": 2
          }
        }
      ]
    }
  },
  "final": true
}
```

#### Example: Using Push Notifications

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {
    "tasks": [
      {
        "id": "task-1",
        "name": "Task 1",
        "user_id": "user123",
        "schemas": {
          "method": "system_info_executor"
        },
        "inputs": {}
      }
    ]
  },
  "configuration": {
    "push_notification_config": {
      "url": "https://my-app.com/api/task-callback",
      "headers": {
        "Authorization": "Bearer my-api-token",
        "Content-Type": "application/json"
      }
    }
  },
  "id": "request-123"
}
```

**Immediate Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "status": "in_progress",
    "root_task_id": "task-1",
    "task_count": 1
  }
}
```

**Callback Request (sent to your URL):**
```json
{
  "task_id": "task-1",
  "context_id": "context-123",
  "status": {
    "state": "completed",
    "message": {
      "role": "agent",
      "parts": [
        {
          "kind": "data",
          "data": {
            "status": "completed",
            "progress": 1.0,
            "root_task_id": "task-1"
          }
        }
      ]
    }
  },
  "final": true
}
```

### Streaming Mode

The A2A protocol also supports streaming mode via `metadata.stream`. When enabled, the server will send multiple status update events through the EventQueue (SSE/WebSocket).

**Request with Streaming:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {
    "tasks": [...]
  },
  "metadata": {
    "stream": true
  },
  "id": "request-123"
}
```

## A2A Client SDK Usage

The A2A protocol provides an official client SDK for easy integration. This section demonstrates how to use the A2A client SDK to interact with aipartnerupflow.

### Installation

```bash
pip install a2a
```

### Basic Usage

```python
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role
import httpx
import uuid

# Create HTTP client
httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")

# Create A2A client config
config = ClientConfig(
    streaming=True,  # Enable streaming mode
    polling=False,
    httpx_client=httpx_client
)

# Create client factory
factory = ClientFactory(config=config)

# Fetch agent card
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
card_response = await httpx_client.get(AGENT_CARD_WELL_KNOWN_PATH)
agent_card = AgentCard(**card_response.json())

# Create A2A client
client = factory.create(card=agent_card)
```

### Executing Tasks

#### Simple Mode (Synchronous)

```python
# Prepare task data
task_data = {
    "id": "task-1",
    "name": "My Task",
    "user_id": "user123",
    "schemas": {
        "method": "system_info_executor"
    },
    "inputs": {}
}

# Create A2A message
data_part = DataPart(kind="data", data={"tasks": [task_data]})
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part]
)

# Send message and get response
responses = []
async for response in client.send_message(message):
    responses.append(response)
    if isinstance(response, Message):
        # Extract result from response
        for part in response.parts:
            if part.kind == "data" and isinstance(part.data, dict):
                result = part.data
                print(f"Task status: {result.get('status')}")
                print(f"Progress: {result.get('progress')}")
```

#### Streaming Mode

```python
# Create message with streaming enabled
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part]
)

# Send message - will receive multiple updates
async for response in client.send_message(message):
    if isinstance(response, Message):
        # Process streaming updates
        for part in response.parts:
            if part.kind == "data":
                update = part.data
                print(f"Update: {update}")
    elif isinstance(response, tuple):
        # Response is (Task, Update) tuple
        task, update = response
        print(f"Task {task.id}: {update}")
```

#### Using Push Notifications (Callback Mode)

```python
from a2a.types import Configuration, PushNotificationConfig

# Create push notification config
push_config = PushNotificationConfig(
    url="https://your-server.com/callback",
    headers={
        "Authorization": "Bearer your-token"
    }
)

# Create configuration
configuration = Configuration(
    push_notification_config=push_config
)

# Create message with configuration
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part],
    configuration=configuration
)

# Send message - server will use callback mode
# Response will be immediate, updates sent to callback URL
async for response in client.send_message(message):
    # Initial response only
    print(f"Initial response: {response}")
    break  # Only expect initial response in callback mode
```

### Task Tree with Dependencies

```python
# Create task tree with dependencies
tasks = [
    {
        "id": "parent-task",
        "name": "Parent Task",
        "user_id": "user123",
        "dependencies": [
            {"id": "child-1", "required": True},
            {"id": "child-2", "required": True}
        ],
        "schemas": {
            "method": "aggregate_results_executor"
        },
        "inputs": {}
    },
    {
        "id": "child-1",
        "name": "Child Task 1",
        "parent_id": "parent-task",
        "user_id": "user123",
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {"resource": "cpu"}
    },
    {
        "id": "child-2",
        "name": "Child Task 2",
        "parent_id": "parent-task",
        "user_id": "user123",
        "dependencies": [{"id": "child-1", "required": True}],
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {"resource": "memory"}
    }
]

# Create message with task tree
data_part = DataPart(kind="data", data={"tasks": tasks})
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part]
)

# Execute task tree
async for response in client.send_message(message):
    # Process responses
    pass
```

### Error Handling

```python
try:
    async for response in client.send_message(message):
        # Process responses
        pass
except Exception as e:
    print(f"Error: {e}")
    # Handle error appropriately
```

### Complete Example

```python
import asyncio
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard
import httpx
import uuid

async def main():
    # Setup
    httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")
    config = ClientConfig(streaming=True, httpx_client=httpx_client)
    factory = ClientFactory(config=config)
    
    # Get agent card
    card_response = await httpx_client.get("/.well-known/agent-card")
    agent_card = AgentCard(**card_response.json())
    client = factory.create(card=agent_card)
    
    # Create task
    task_data = {
        "id": "my-task",
        "name": "My Task",
        "user_id": "user123",
        "schemas": {"method": "system_info_executor"},
        "inputs": {}
    }
    
    # Create message
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[DataPart(kind="data", data={"tasks": [task_data]})]
    )
    
    # Execute and process responses
    async for response in client.send_message(message):
        if isinstance(response, Message):
            for part in response.parts:
                if part.kind == "data":
                    print(f"Result: {part.data}")
    
    await httpx_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
```

## A2A Protocol Documentation

For detailed information about the A2A Protocol, please refer to the official documentation:

- **A2A Protocol Official Documentation**: [https://www.a2aprotocol.org/en/docs](https://www.a2aprotocol.org/en/docs)
- **A2A Protocol Homepage**: [https://www.a2aprotocol.org](https://www.a2aprotocol.org)

These resources provide comprehensive information about:
- A2A Protocol core concepts and architecture
- Protocol specifications and data formats
- Client SDK API reference
- Best practices and examples
- Security and authentication
- Push notifications and streaming

## See Also

- [A2A Protocol Specification](https://github.com/aipartnerup/a2a-protocol)
- [CLI Usage Guide](../guides/cli.md)
- [Architecture Documentation](../architecture/overview.md)

