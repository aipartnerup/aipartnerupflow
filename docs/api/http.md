# API Reference

This document provides a complete reference for the aipartnerupflow API, which implements the **A2A (Agent-to-Agent) Protocol** standard.

## Overview

The aipartnerupflow API server provides:
- **A2A Protocol Server**: Standard agent-to-agent communication protocol
- **Task Management**: Create, read, update, and delete tasks
- **Task Execution**: Execute task trees with dependency management
- **Real-time Streaming**: Progress updates via Server-Sent Events (SSE) and WebSocket
- **JWT Authentication**: Optional token-based authentication

## Base URL

```
http://localhost:8000  # Default development server
```

## Endpoints

### A2A Protocol Endpoints

#### `GET /.well-known/agent-card`

**Description:**  
Retrieves the agent card that describes the service capabilities, available skills, and protocol support. This endpoint follows the A2A Protocol standard for agent discovery.

**Authentication:**  
Not required (public endpoint)

**Request Parameters:**  
None

**Response Format:**  
Returns a JSON object containing agent metadata:

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

**Response Fields:**
- `name` (string): Service name
- `description` (string): Service description
- `url` (string): Base URL of the service
- `version` (string): Service version
- `capabilities` (object): Supported capabilities
  - `streaming` (boolean): Whether streaming mode is supported
  - `push_notifications` (boolean): Whether push notifications are supported
- `skills` (array): List of available skills/operations

**Example Request:**
```bash
curl http://localhost:8000/.well-known/agent-card
```

**Example Response:**
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

**Notes:**
- This endpoint is always public and does not require authentication
- The agent card is used by A2A Protocol clients to discover service capabilities
- The URL in the response should match the actual service URL

#### `POST /`

**Description:**  
Main A2A Protocol RPC endpoint that handles all A2A protocol requests. This endpoint implements the standard A2A Protocol JSON-RPC 2.0 interface for agent-to-agent communication. It supports task tree execution with streaming, push notifications, and real-time progress updates.

**Authentication:**  
Optional (JWT token in `Authorization` header if JWT is enabled)

**Request Format:**  
JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
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
  "id": "request-123",
  "configuration": {
    "push_notification_config": {
      "url": "https://your-server.com/callback",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  },
  "metadata": {
    "stream": true
  }
}
```

**Request Parameters:**
- `jsonrpc` (string, required): JSON-RPC version, must be "2.0"
- `method` (string, required): Method name, currently supports "execute_task_tree"
- `params` (object, required): Method parameters
  - `tasks` (array, required): Array of task objects to execute
- `id` (string/number, required): Request identifier for matching responses
- `configuration` (object, optional): Configuration for push notifications
  - `push_notification_config` (object, optional): Push notification settings
    - `url` (string, required): Callback URL for status updates
    - `headers` (object, optional): HTTP headers for callback requests
    - `method` (string, optional): HTTP method for callbacks (default: "POST")
- `metadata` (object, optional): Additional metadata
  - `stream` (boolean, optional): Enable streaming mode for real-time updates

**Response Format:**  
JSON-RPC 2.0 response with A2A Protocol Task object:

```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "id": "task-execution-id",
    "context_id": "task-abc-123",
    "kind": "task",
    "status": {
      "state": "completed",
      "message": {
        "kind": "message",
        "parts": [
          {
            "kind": "data",
            "data": {
              "protocol": "a2a",
              "status": "completed",
              "progress": 1.0,
              "root_task_id": "task-abc-123",
              "task_count": 2
            }
          }
        ]
      }
    },
    "artifacts": [...],
    "metadata": {
      "protocol": "a2a",
      "root_task_id": "task-abc-123",
      "user_id": "user123"
    }
  }
}
```

**Response Fields:**
- `jsonrpc` (string): JSON-RPC version ("2.0")
- `id` (string/number): Request identifier (matches request)
- `result` (object): A2A Protocol Task object
  - `id` (string): Task execution instance ID
  - `context_id` (string): Task definition ID (root task ID)
  - `kind` (string): Always `"task"` for A2A protocol
  - `status` (object): Task status object
    - `state` (string): Task state ("completed", "working", "failed", etc.)
    - `message` (object): Status message with parts
      - `parts[].data.protocol` (string): Protocol identifier, always `"a2a"` for A2A protocol responses
      - `parts[].data.status` (string): Task status ("completed", "in_progress", "failed", "pending")
      - `parts[].data.progress` (float): Overall progress (0.0 to 1.0)
      - `parts[].data.root_task_id` (string): ID of the root task
      - `parts[].data.task_count` (integer): Number of tasks in the tree
  - `artifacts` (array): Execution artifacts
  - `metadata` (object): Task metadata
    - `protocol` (string): Protocol identifier, always `"a2a"` for A2A protocol responses
    - `root_task_id` (string): ID of the root task
    - `user_id` (string, optional): User ID associated with the task

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": "Error details"
  }
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "execute_task_tree",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "my_task",
          "user_id": "user123",
          "schemas": {"method": "system_info_executor"},
          "inputs": {}
        }
      ]
    },
    "id": "request-123"
  }'
```

**Example with Streaming:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "execute_task_tree",
    "params": {
      "tasks": [...]
    },
    "metadata": {
      "stream": true
    },
    "id": "request-123"
  }'
```

**Example with Push Notifications:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

**Notes:**
- This endpoint implements the A2A Protocol standard
- When `push_notification_config` is provided, the server executes tasks asynchronously and sends updates to the callback URL
- When `metadata.stream` is true, progress updates are sent via EventQueue (SSE/WebSocket). For JSON-RPC `tasks.execute`, use `use_streaming=true` instead.
- Task execution follows dependency order and priority scheduling
- All tasks in a tree must have the same `user_id` (or be accessible by the authenticated user)
- All responses include `protocol: "a2a"` in Task metadata and event data to identify this as an A2A Protocol response
- This differs from JSON-RPC protocol responses (which use `protocol: "jsonrpc"` in the response object)

### Task Management Endpoints

#### `POST /tasks`

**Description:**  
Unified task management endpoint that supports multiple task operations via JSON-RPC 2.0 format. This endpoint handles all task-related operations including creation, retrieval, updates, deletion, querying, and execution. All operations are performed through different `method` values in the JSON-RPC request.

**Authentication:**  
Optional (JWT token in `Authorization` header if JWT is enabled)

**Request Format:**  
JSON-RPC 2.0 format with method-specific parameters:

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

**Supported Methods:**
- `tasks.create` - Create and execute task trees
- `tasks.get` - Get task by ID
- `tasks.update` - Update task properties
- `tasks.delete` - Delete a task
- `tasks.detail` - Get detailed task information
- `tasks.tree` - Get task tree structure
- `tasks.children` - Get child tasks of a parent task
- `tasks.list` - List tasks with filters
- `tasks.running.list` - List currently running tasks
- `tasks.running.status` - Get status of running tasks
- `tasks.running.count` - Get count of running tasks
- `tasks.cancel` / `tasks.running.cancel` - Cancel running tasks
- `tasks.copy` - Copy a task tree for re-execution
- `tasks.execute` - Execute a task by ID

**Request Headers:**
- `Content-Type`: `application/json` (required)
- `Authorization`: `Bearer <token>` (optional, if JWT is enabled)
- `X-LLM-API-KEY`: `<api-key>` or `<provider>:<api-key>` (optional, for LLM tasks)

**Response Format:**  
JSON-RPC 2.0 response format. The `result` field varies by method.

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "Unknown task method: tasks.invalid"
  }
}
```

**Notes:**
- All task operations require proper permissions if JWT is enabled
- Tasks with different `user_id` values cannot be in the same tree
- The `X-LLM-API-KEY` header can be used to provide LLM API keys for tasks that require them
- Task operations are atomic and support transaction rollback on errors

## Task Management Methods

All task management methods use the `/tasks` endpoint with JSON-RPC 2.0 format.

### `tasks.create`

**Description:**  
Creates one or more tasks and automatically executes them as a task tree. This method validates task dependencies, ensures all tasks form a single tree structure, and handles task execution with proper dependency ordering. Tasks can be provided as a single object or an array of objects.

**Method:** `tasks.create`

**Parameters:**
- `tasks` (array or object, required): Array of task objects, or single task object (will be converted to array). All tasks must have the same `user_id` after resolution.

**Task Object Fields:**
- `id` (string, optional): Task ID. If not provided, auto-generated UUID will be used
- `name` (string, required): Task name
- `user_id` (string, optional): User ID for multi-user scenarios
- `parent_id` (string, optional): Parent task ID for task tree structure. **Note**: Parent-child relationships are for **organizational purposes only** and do NOT affect execution order. Use `dependencies` to control execution order.
- `priority` (integer, optional): Priority level (0=urgent, 1=high, 2=normal, 3=low). Default: 1
- `dependencies` (array, optional): Dependency list. Format: `[{"id": "task-id", "required": true}]`. **This determines execution order** - a task executes only when all its required dependencies are satisfied.
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
    "id": "root",
    "name": "Root Task",
    "status": "completed",
    "progress": 1.0,
    "user_id": "user123",
    "children": [
      {
        "id": "child",
        "name": "Child Task",
        "status": "completed",
        "progress": 1.0,
        "parent_id": "root",
        "children": []
      }
    ]
  }
}
```

**Response Fields:**
- `id` (string): Root task ID
- `name` (string): Root task name
- `status` (string): Task status
- `progress` (float): Overall progress (0.0 to 1.0)
- `user_id` (string): User ID
- `children` (array): Array of child task objects (nested structure)

**Validation Rules:**
- All tasks must form a single task tree (exactly one root task)
- No circular dependencies allowed
- All dependent tasks must be included in the input array
- All tasks must be reachable from the root task via `parent_id` chain
- All tasks must have the same `user_id` (or be accessible by authenticated user)

**Error Cases:**
- Circular dependency detected: Returns error with code -32602
- Multiple root tasks: Returns error with code -32602
- Missing required fields: Returns error with code -32602
- Permission denied: Returns error with code -32001

**Notes:**
- Tasks are automatically executed after creation
- **Task execution follows dependency order and priority** - not parent-child relationships
- Parent-child relationships (`parent_id`) are for organizing the task tree structure only
- Dependencies (`dependencies`) determine when tasks execute - a task runs when its dependencies are satisfied
- If a task fails, dependent tasks are not executed
- Task IDs can be auto-generated if not provided

### `tasks.get`

**Description:**  
Retrieves a task by its ID. Returns the complete task object including all fields such as status, progress, inputs, results, and metadata. This is a simple lookup operation that does not include child tasks.

**Method:** `tasks.get`

**Parameters:**
- `task_id` (string, required): Task ID to retrieve. Can also use `id` as an alias.

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
    "user_id": "user123",
    "parent_id": null,
    "priority": 1,
    "dependencies": [],
    "inputs": {"key": "value"},
    "result": {"output": "result"},
    "error": null,
    "schemas": {"method": "executor_id"},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z",
    "started_at": "2024-01-01T00:01:00Z",
    "completed_at": "2024-01-01T00:05:00Z"
  }
}
```

**Response Fields:**
- `id` (string): Task ID
- `name` (string): Task name
- `status` (string): Task status ("pending", "in_progress", "completed", "failed", "cancelled")
- `progress` (float): Progress (0.0 to 1.0)
- `user_id` (string): User ID
- `parent_id` (string, nullable): Parent task ID
- `priority` (integer): Priority level
- `dependencies` (array): Task dependencies
- `inputs` (object): Input parameters
- `result` (object, nullable): Execution result
- `error` (string, nullable): Error message if failed
- `schemas` (object): Task schemas
- `created_at` (string): Creation timestamp (ISO 8601)
- `updated_at` (string): Last update timestamp (ISO 8601)
- `started_at` (string, nullable): Start timestamp (ISO 8601)
- `completed_at` (string, nullable): Completion timestamp (ISO 8601)

**Error Cases:**
- Task not found: Returns `null` in result field
- Permission denied: Returns error with code -32001

**Notes:**
- This method returns only the specified task, not its children
- Use `tasks.tree` to get the full task tree structure
- Task must be accessible by the authenticated user (if JWT is enabled)

### `tasks.update`

**Description:**  
Updates task properties. This method allows partial updates to task fields such as status, progress, inputs, results, and timestamps. Only the fields provided in the request will be updated; other fields remain unchanged.

**Method:** `tasks.update`

**Parameters:**
- `task_id` (string, required): Task ID to update
- `status` (string, optional): New status ("pending", "in_progress", "completed", "failed", "cancelled")
- `inputs` (object, optional): Updated input parameters (replaces entire inputs object)
- `result` (object, optional): Updated result (replaces entire result object)
- `error` (string, optional): Error message (typically set when status is "failed")
- `progress` (float, optional): Progress value (0.0 to 1.0)
- `started_at` (string, optional): Start timestamp (ISO 8601 format)
- `completed_at` (string, optional): Completion timestamp (ISO 8601 format)

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
    "name": "Task 1",
    "status": "in_progress",
    "progress": 0.5,
    "user_id": "user123",
    "inputs": {"key": "value"},
    "updated_at": "2024-01-01T00:03:00Z"
  }
}
```

**Response Fields:**
Returns the complete updated task object with all fields.

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Invalid status value: Returns error with code -32602
- Invalid progress value (not 0.0-1.0): Returns error with code -32602

**Notes:**
- Updates are atomic and immediately persisted to the database
- Status changes may trigger dependent task execution
- Timestamps should be in ISO 8601 format
- Only authenticated users can update their own tasks (or admins can update any task)

### `tasks.delete`

**Description:**  
Deletes a task by marking it as deleted. The task is not physically removed from the database but its status is set to "deleted" and a completion timestamp is recorded. This allows for audit trails and potential recovery.

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

**Response Fields:**
- `success` (boolean): Whether deletion was successful
- `task_id` (string): ID of the deleted task

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Task is currently running: Returns error with code -32602 (should cancel first)

**Notes:**
- Deleted tasks are soft-deleted (status set to "deleted")
- Deleted tasks are excluded from normal queries
- Child tasks are not automatically deleted
- Deletion requires proper permissions (own task or admin role)

### `tasks.copy`

**Description:**  
Creates a new executable copy of an existing task tree for re-execution. This method creates a complete copy of the task tree including the original task, all its children, and all tasks that depend on it (including transitive dependencies). All execution-specific fields are reset to initial values, making the copied tree ready for fresh execution.

**Method:** `tasks.copy`

**What Gets Copied:**
- The original task and all its children (recursive)
- All tasks that depend on the original task (direct and transitive dependencies)
- Task structure (parent-child relationships)
- Task definitions (name, inputs, schemas, params, dependencies)
- User and product associations (user_id, product_id)
- Priority settings

**What Gets Reset:**
- Task IDs (new IDs generated)
- Status (reset to "pending")
- Progress (reset to 0.0)
- Result (reset to null)
- Error (reset to null)
- Execution timestamps (started_at, completed_at)
- Token usage counters (token_success, token_failed)

**What Gets Preserved:**
- Task definitions (name, code, inputs, schemas, params)
- User and product associations (user_id, product_id)
- Priority settings
- Dependencies structure

**Metadata:**
- `original_task_id`: Links copied task to original task's root ID
- `has_copy`: Set to `true` on all original tasks that were copied

**Parameters:**
- `task_id` (string, required): ID of the task to copy. Can be root task or any task in the tree. The method will copy the minimal subtree containing the task and all its dependencies.

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

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001

**Notes:**
- The copied task tree has new task IDs but preserves the original structure
- All execution fields are reset (status="pending", progress=0.0, result=null)
- The original task's `has_copy` flag is set to `true`
- Use the returned task tree's root ID to execute the copied tasks
- Failed leaf nodes are automatically handled (pending dependents are filtered out)
- The copied tree is ready for immediate execution

### `tasks.list`

**Description:**  
Lists all tasks from the database with optional filtering by user ID, status, and pagination support. This method queries the database (not just running tasks) and returns tasks matching the specified filters. Results are sorted by creation time (newest first) and can be paginated using limit and offset.

**Method:** `tasks.list`

**Parameters:**
- `user_id` (string, optional): Filter tasks by user ID. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, returns all tasks.
- `status` (string, optional): Filter by task status. Valid values: "pending", "in_progress", "completed", "failed", "cancelled", "deleted". If not provided, returns tasks with any status.
- `limit` (integer, optional): Maximum number of tasks to return (default: 100, maximum recommended: 1000)
- `offset` (integer, optional): Number of tasks to skip for pagination (default: 0)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.list",
  "params": {
    "user_id": "user123",
    "status": "completed",
    "limit": 50,
    "offset": 0
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
      "status": "completed",
      "progress": 1.0,
      "user_id": "user123",
      "created_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:05:00Z"
    },
    {
      "id": "task-2",
      "name": "Task 2",
      "status": "completed",
      "progress": 1.0,
      "user_id": "user123",
      "created_at": "2024-01-01T00:01:00Z",
      "completed_at": "2024-01-01T00:06:00Z"
    }
  ]
}
```

**Response Fields:**
Returns an array of task objects, each containing:
- All standard task fields (id, name, status, progress, user_id, etc.)
- Tasks are sorted by `created_at` in descending order (newest first)

**Error Cases:**
- Permission denied: Tasks for other users are filtered out (not returned in error)

**Notes:**
- This method queries the database, not just running tasks
- Use `tasks.running.list` to get only currently running tasks
- Results are paginated using limit and offset
- Deleted tasks are excluded from results
- Use pagination for large result sets to avoid performance issues

### `tasks.execute`

**Description:**  
Executes a task by its ID with automatic dependency handling. This method supports two execution modes:
- **Root task execution**: If the specified task is a root task (no parent), the entire task tree is executed.
- **Child task execution**: If the specified task is a child task, the method automatically collects all dependencies (including transitive dependencies) and executes the task along with all required dependencies.

**Task Status Handling:**
- **Pending tasks**: Execute normally (newly created tasks)
- **Failed tasks**: Can be re-executed by calling this method with the failed task's ID
- **Completed tasks**: Skipped unless they are dependencies of a task being re-executed (in which case they are also re-executed)
- **In-progress tasks**: Skipped to avoid conflicts

**Re-execution Behavior:**
When re-executing a failed task, all its dependency tasks are also re-executed (even if they are completed) to ensure consistency. This ensures that the entire execution context is refreshed and results are up-to-date.

The task must exist in the database and must not already be running. Execution follows dependency order and priority scheduling. This unified execution behavior ensures consistent task execution across both A2A Protocol and JSON-RPC endpoints.

**Method:** `tasks.execute`

**Parameters:**
- `task_id` (string, required): Task ID to execute. Can also use `id` as an alias. 
  - If the task is a root task, the entire task tree will be executed.
  - If the task is a child task, the task and all its dependencies (including transitive) will be executed.
- `use_streaming` (boolean, optional): Whether to use streaming mode for real-time progress updates (default: false). If true, the endpoint returns a `StreamingResponse` with Server-Sent Events (SSE) instead of a JSON response.
- `webhook_config` (object, optional): Webhook configuration for push notifications. If provided, task execution updates will be sent to the specified webhook URL via HTTP callbacks. This is similar to A2A Protocol's push notification feature.
  - `url` (string, required): Webhook callback URL where updates will be sent
  - `headers` (object, optional): HTTP headers to include in webhook requests (e.g., `{"Authorization": "Bearer token"}`)
  - `method` (string, optional): HTTP method for webhook requests (default: "POST")
  - `timeout` (float, optional): Request timeout in seconds (default: 30.0)
  - `max_retries` (int, optional): Maximum retry attempts for failed webhook requests (default: 3)

**Example Request (Non-streaming):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "use_streaming": false
  },
  "id": "execute-request-1"
}
```

**Example Request (Streaming mode):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "use_streaming": true
  },
  "id": "execute-request-1"
}
```

**Example Request (Webhook mode):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "webhook_config": {
      "url": "https://example.com/api/task-callback",
      "headers": {
        "Authorization": "Bearer your-api-token",
        "Content-Type": "application/json"
      },
      "method": "POST",
      "timeout": 30.0,
      "max_retries": 3
    }
  },
  "id": "execute-request-1"
}
```

**Example Response (Non-streaming):**
```json
{
  "jsonrpc": "2.0",
  "id": "execute-request-1",
  "result": {
    "success": true,
    "protocol": "jsonrpc",
    "root_task_id": "task-abc-123",
    "task_id": "task-abc-123",
    "status": "started",
    "message": "Task task-abc-123 execution started"
  }
}
```

**Example Response (Streaming mode):**
When `use_streaming=true`, the response is a Server-Sent Events (SSE) stream with `Content-Type: text/event-stream`.

The first event contains the initial JSON-RPC response:
```
data: {"jsonrpc": "2.0", "id": "execute-request-1", "result": {"success": true, "protocol": "jsonrpc", "root_task_id": "task-abc-123", "task_id": "task-abc-123", "status": "started", "streaming": true, "message": "Task task-abc-123 execution started with streaming"}}

```

Subsequent events contain real-time progress updates:
```
data: {"type": "progress", "task_id": "task-abc-123", "status": "in_progress", "progress": 0.5, "message": "Task tree execution started", "timestamp": "2025-11-26T08:00:00"}

data: {"type": "task_completed", "task_id": "task-abc-123", "status": "completed", "result": {...}, "timestamp": "2025-11-26T08:00:05"}

data: {"type": "final", "task_id": "task-abc-123", "status": "completed", "result": {"progress": 1.0}, "final": true, "timestamp": "2025-11-26T08:00:05"}

data: {"type": "stream_end", "task_id": "task-abc-123"}

```

**Note:** When `use_streaming=true`, you must parse the SSE stream format (`data: {...}`) instead of expecting a JSON response.

**Example Response (Webhook mode):**
```json
{
  "jsonrpc": "2.0",
  "id": "execute-request-1",
  "result": {
    "success": true,
    "protocol": "jsonrpc",
    "root_task_id": "task-abc-123",
    "task_id": "task-abc-123",
    "status": "started",
    "streaming": true,
    "message": "Task task-abc-123 execution started with webhook callbacks. Updates will be sent to https://example.com/callback",
    "webhook_url": "https://example.com/callback"
  }
}
```

**Response Fields:**
- `success` (boolean): Whether execution was started successfully
- `protocol` (string): Protocol identifier, always `"jsonrpc"` for this endpoint. Used to distinguish from A2A protocol responses.
- `root_task_id` (string): ID of the root task in the tree
- `task_id` (string): ID of the task that was executed
- `status` (string): Execution status ("started", "already_running", "failed")
- `message` (string): Status message
- `streaming` (boolean, optional): Present when `use_streaming=true` or `webhook_config` is provided. Indicates that streaming/webhook mode is enabled.
- `webhook_url` (string, optional): Present only when `webhook_config` is provided. The webhook URL where updates will be sent.

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Task already running: Returns success=false with status "already_running"

**Webhook Callback Format:**

When `webhook_config` is provided, the server will send HTTP POST requests to your webhook URL with the following payload format:

```json
{
  "protocol": "jsonrpc",
  "root_task_id": "task-abc-123",
  "task_id": "task-abc-123",
  "status": "completed",
  "progress": 1.0,
  "message": "Task execution completed",
  "type": "final",
  "timestamp": "2024-01-01T12:00:00Z",
  "final": true,
  "result": {
    "status": "completed",
    "progress": 1.0,
    "root_task_id": "task-abc-123",
    "task_count": 1
  }
}
```

**Webhook Update Types:**

The server sends different types of updates during task execution:
- `task_start`: Task execution started
- `progress`: Progress update (status, progress percentage)
- `task_completed`: Task completed successfully
- `task_failed`: Task execution failed
- `final`: Final status update (always sent at the end)

**Webhook Retry Behavior:**

- The server automatically retries failed webhook requests up to `max_retries` times
- Retries use exponential backoff (1s, 2s, 4s, ...)
- Client errors (4xx) are not retried
- Server errors (5xx) and network errors are retried
- Webhook failures are logged but do not affect task execution

**Notes:**
- **Root task execution**: If `task_id` refers to a root task, the entire task tree is executed.
- **Child task execution**: If `task_id` refers to a child task, the method automatically collects all dependencies (including transitive dependencies) and executes only the required subtree containing the task and its dependencies.
- **Re-execution support**: Failed tasks can be re-executed by calling this method with the failed task's ID. When re-executing, all dependency tasks are also re-executed to ensure consistency.
- **Execution order**: Task execution follows **dependency order and priority**, not parent-child relationships. Parent-child relationships (`parent_id`) are for organizing the task tree structure only. Dependencies (`dependencies`) determine when tasks execute.
- Task execution is asynchronous - the method returns immediately after starting execution
- The unified execution logic ensures consistent behavior across A2A Protocol and JSON-RPC endpoints
- Only `pending` and `failed` status tasks are executed; `completed` and `in_progress` tasks are skipped unless they are dependencies of a task being re-executed
- Use `tasks.running.status` to check execution progress
- Use `use_streaming=true` to receive real-time progress updates via Server-Sent Events (SSE) - the response will be a streaming response instead of JSON
- The SSE stream includes the initial JSON-RPC response as the first event, followed by real-time progress updates
- Use `webhook_config` to receive updates via HTTP callbacks (independent of response mode)
- `webhook_config` and `use_streaming` can be used together - webhook callbacks will be sent regardless of response mode
- Tasks are executed following dependency order and priority
- All responses include `protocol: "jsonrpc"` field to identify this as a JSON-RPC protocol response
- This differs from A2A Protocol responses (which use `protocol: "a2a"` in metadata and event data)

### `tasks.detail`

**Description:**  
Retrieves detailed task information including all fields. This method is functionally equivalent to `tasks.get` and returns the complete task object with all metadata, inputs, results, and execution history.

**Method:** `tasks.detail`

**Parameters:**
- `task_id` (string, required): Task ID to get details for

**Response Format:**  
Same as `tasks.get` - returns complete task object.

**Notes:**
- This method is an alias for `tasks.get`
- Use this method when you need explicit clarity that you're requesting detailed information
- Returns the same response format as `tasks.get`

### `tasks.children`

**Description:**  
Retrieves all child tasks of a specified parent task. This method returns a flat list of direct children (not a nested tree structure). Useful for getting immediate children without the full tree hierarchy.

**Method:** `tasks.children`

**Parameters:**
- `parent_id` (string, required): Parent task ID to get children for. Can also use `task_id` as an alias.
- `task_id` (string, optional): Alternative parameter name for parent_id (same as `parent_id`)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.children",
  "params": {
    "parent_id": "task-abc-123"
  },
  "id": "children-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "children-request-1",
  "result": [
    {
      "id": "child-task-1",
      "name": "Child Task 1",
      "status": "completed",
      "progress": 1.0,
      "parent_id": "task-abc-123",
      "user_id": "user123"
    },
    {
      "id": "child-task-2",
      "name": "Child Task 2",
      "status": "in_progress",
      "progress": 0.5,
      "parent_id": "task-abc-123",
      "user_id": "user123"
    }
  ]
}
```

**Response Fields:**
Returns an array of task objects, each containing:
- All standard task fields (id, name, status, progress, user_id, parent_id, etc.)
- Each task object represents a direct child of the specified parent
- Tasks are returned in a flat list (not nested)

**Error Cases:**
- Parent task not found: Returns error with code -32602
- Missing parent_id: Returns error with code -32602
- Permission denied: Returns error with code -32001 (for parent task access)
- Child tasks with permission denied are filtered out (not returned, but no error)

**Notes:**
- Returns only direct children, not grandchildren or deeper descendants
- Use `tasks.tree` to get the complete nested tree structure
- Child tasks are filtered by permission - tasks you cannot access are not returned
- Returns an empty array if the parent task has no children
- Useful for pagination or when you only need immediate children

### `tasks.tree`

**Description:**  
Retrieves the complete task tree structure starting from a specified task. If the specified task has a parent, the method automatically finds the root task and returns the entire tree. The response includes nested children in a hierarchical structure.

**Method:** `tasks.tree`

**Parameters:**
- `task_id` (string, optional): Task ID to start from. If the task has a parent, the root task will be found automatically. Either `task_id` or `root_id` is required.
- `root_id` (string, optional): Alternative parameter name for root task ID. Can be used instead of `task_id`.

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
    "status": "completed",
    "progress": 1.0,
    "user_id": "user123",
    "children": [
      {
        "id": "child-task-id",
        "name": "Child Task",
        "status": "completed",
        "progress": 1.0,
        "parent_id": "root-task-id",
        "children": []
      }
    ]
  }
}
```

**Response Fields:**
- Root task object with all fields
- `children` (array): Array of child task objects (recursive structure)
  - Each child includes all task fields
  - Each child may have its own `children` array

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001

**Notes:**
- The tree structure is built recursively from the root task
- All tasks in the tree are included, regardless of status
- The tree structure preserves parent-child relationships
- Use this method to visualize the complete task hierarchy

### `tasks.running.list`

**Description:**  
Lists all currently running tasks from memory. This method queries the in-memory task tracker to find tasks that are actively executing. Tasks are sorted by creation time (newest first) and can be filtered by user ID.

**Method:** `tasks.running.list`

**Parameters:**
- `user_id` (string, optional): Filter tasks by user ID. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, returns all running tasks.
- `limit` (integer, optional): Maximum number of tasks to return (default: 100, maximum recommended: 1000)

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
      "progress": 0.3,
      "user_id": "user123",
      "created_at": "2024-01-01T00:00:00Z",
      "started_at": "2024-01-01T00:01:00Z"
    },
    {
      "id": "task-2",
      "name": "Task 2",
      "status": "in_progress",
      "progress": 0.7,
      "user_id": "user123",
      "created_at": "2024-01-01T00:00:00Z",
      "started_at": "2024-01-01T00:01:00Z"
    }
  ]
}
```

**Response Fields:**
Returns an array of task objects, each containing:
- All standard task fields (id, name, status, progress, user_id, etc.)
- Tasks are sorted by `created_at` in descending order (newest first)

**Error Cases:**
- Permission denied: Tasks for other users are filtered out (not returned in error)

**Notes:**
- This method queries in-memory task tracker, not the database
- Only tasks that are actively running are returned
- Completed or failed tasks are not included
- Use `tasks.list` to query all tasks from the database
- Results are limited to prevent performance issues

### `tasks.running.status`

**Description:**  
Gets the status of one or more tasks. This method checks both the in-memory task tracker (for active execution status) and the database (for persistent status). Returns detailed status information including progress, error messages, and execution timestamps.

**Method:** `tasks.running.status`

**Parameters:**
- `task_ids` (array, required): Array of task IDs to check status for. Can also use `context_ids` as an alias (for A2A Protocol compatibility).
- `context_ids` (array, optional): Alternative parameter name for task IDs (same as `task_ids`)

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

**Description:**  
Gets the count of currently running tasks. This method queries the in-memory task tracker to count tasks that are actively executing. Can be filtered by user ID to get user-specific counts.

**Method:** `tasks.running.count`

**Parameters:**
- `user_id` (string, optional): Filter by user ID. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, returns total count of all running tasks.

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

**Response Fields:**
- `count` (integer): Number of running tasks
- `user_id` (string, optional): User ID filter applied (only present if user_id was specified)

**Error Cases:**
- Permission denied: Returns error with code -32001 (if trying to count another user's tasks without admin role)

**Notes:**
- Count is based on in-memory task tracker, not database
- Only actively running tasks are counted
- Returns 0 if no running tasks match the filter
- Useful for monitoring system load and user activity

### `tasks.cancel` / `tasks.running.cancel`

**Description:**  
Cancels one or more running tasks. This method attempts to gracefully cancel tasks by calling the executor's `cancel()` method if supported. If force is enabled, tasks are immediately marked as cancelled. Returns detailed cancellation results including token usage and partial results if available.

**Method:** `tasks.cancel` or `tasks.running.cancel` (both are equivalent)

**Parameters:**
- `task_ids` (array, required): Array of task IDs to cancel. Can also use `context_ids` as an alias (for A2A Protocol compatibility).
- `context_ids` (array, optional): Alternative parameter name for task IDs
- `force` (boolean, optional): Force immediate cancellation without waiting for graceful shutdown (default: false)
- `error_message` (string, optional): Custom error message for cancellation. If not provided, defaults to "Cancelled by user" or "Force cancelled by user" based on force flag.

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
      "message": "Task cancelled successfully",
      "force": false,
      "token_usage": {
        "total_tokens": 1000,
        "prompt_tokens": 500,
        "completion_tokens": 500
      },
      "result": null
    },
    {
      "task_id": "task-2",
      "status": "cancelled",
      "message": "Task cancelled successfully",
      "force": false,
      "token_usage": null,
      "result": null
    }
  ]
}
```

**Response Fields:**
Returns an array of cancellation result objects, each containing:
- `task_id` (string): Task ID that was cancelled
- `status` (string): Final status ("cancelled" or "failed")
- `message` (string): Cancellation message
- `force` (boolean): Whether force cancellation was used
- `token_usage` (object, nullable): Token usage information if available
- `result` (any, nullable): Partial result if available

**Error Cases:**
- Task not found: Returns status "error" with error message
- Permission denied: Returns status "failed" with "permission_denied" error
- Task already completed: May return status "failed" if task cannot be cancelled

**Notes:**
- Cancellation attempts to call executor's `cancel()` method if supported
- Force cancellation immediately marks task as cancelled without waiting
- Token usage is recorded if available from the executor
- Partial results may be returned if task was partially completed
- Child tasks are not automatically cancelled (cancel parent task to cancel children)

## System Endpoints

### `POST /system`

**Description:**  
Unified system operations endpoint that handles system-level operations via JSON-RPC 2.0 format. This endpoint provides health checks, configuration management, and example data initialization.

**Authentication:**  
Optional (JWT token in `Authorization` header if JWT is enabled)

**Request Format:**  
JSON-RPC 2.0 format with method-specific parameters:

```json
{
  "jsonrpc": "2.0",
  "method": "system.health",
  "params": {},
  "id": "request-123"
}
```

**Supported Methods:**
- `system.health` - Check system health status
- `config.llm_key.set` - Set LLM API key for user
- `config.llm_key.get` - Get LLM API key status
- `config.llm_key.delete` - Delete LLM API key
- `examples.init` - Initialize example data
- `examples.status` - Check example data status

**Response Format:**  
JSON-RPC 2.0 response format. The `result` field varies by method.

**Notes:**
- System operations may require authentication depending on configuration
- Some operations (like LLM key management) require proper permissions

#### `system.health`

**Description:**  
Checks the system health status and returns basic system information including version, uptime, and running tasks count. This endpoint is useful for monitoring and health checks.

**Method:** `system.health`

**Parameters:**  
None

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
    "message": "aipartnerupflow is healthy",
    "version": "0.2.0",
    "timestamp": "2024-01-01T00:00:00Z",
    "running_tasks_count": 0
  }
}
```

**Response Fields:**
- `status` (string): Health status ("healthy" or "unhealthy")
- `message` (string): Health status message
- `version` (string): Service version
- `timestamp` (string): Current timestamp (ISO 8601)
- `running_tasks_count` (integer): Number of currently running tasks

**Notes:**
- This endpoint does not require authentication
- Useful for load balancer health checks
- Returns basic system information for monitoring

#### `config.llm_key.set`

**Description:**  
Sets an LLM API key for a user. This method stores the API key securely for use in LLM-based tasks (e.g., CrewAI tasks). The key is associated with a user ID and optional provider name. Keys are stored securely and never returned in responses.

**Method:** `config.llm_key.set`

**Parameters:**
- `api_key` (string, required): LLM API key to store
- `user_id` (string, optional): User ID to associate the key with. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, raises an error.
- `provider` (string, optional): Provider name (e.g., "openai", "anthropic", "google", "gemini", "mistral", "groq", "cohere", "together"). If not provided, the provider will be auto-detected from the API key format or use "default".

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.llm_key.set",
  "params": {
    "api_key": "sk-your-api-key",
    "user_id": "user123",
    "provider": "openai"
  },
  "id": "set-key-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "set-key-request-1",
  "result": {
    "success": true,
    "user_id": "user123",
    "provider": "openai"
  }
}
```

**Response Fields:**
- `success` (boolean): Whether the key was set successfully
- `user_id` (string): User ID the key is associated with
- `provider` (string): Provider name (or "default" if not specified)

**Error Cases:**
- Missing api_key: Returns error with code -32602
- Missing user_id (and not authenticated): Returns error with code -32602
- Permission denied: Returns error with code -32001
- Extension not available: Returns error if llm-key-config extension is not installed

**Notes:**
- Requires the `llm-key-config` extension to be installed
- Keys are stored securely and never returned in API responses
- Keys are used during task execution and cleared after completion
- Multiple keys can be stored per user (one per provider)
- Keys take precedence over environment variables during task execution

#### `config.llm_key.get`

**Description:**  
Gets the status of LLM API keys for a user. This method checks if keys exist without returning the actual key values (for security). Returns information about which providers have keys configured.

**Method:** `config.llm_key.get`

**Parameters:**
- `user_id` (string, optional): User ID to check keys for. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, uses "default".
- `provider` (string, optional): Provider name to check. If not provided, returns status for all providers.

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.llm_key.get",
  "params": {
    "user_id": "user123",
    "provider": "openai"
  },
  "id": "get-key-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "get-key-request-1",
  "result": {
    "has_key": true,
    "user_id": "user123",
    "provider": "openai",
    "providers": {
      "openai": true,
      "anthropic": false,
      "google": true
    }
  }
}
```

**Response Fields:**
- `has_key` (boolean): Whether a key exists for the specified provider (or any provider if provider not specified)
- `user_id` (string): User ID checked
- `provider` (string, nullable): Provider name checked (or null if checking all)
- `providers` (object): Dictionary of provider names to boolean values indicating key existence

**Error Cases:**
- Permission denied: Returns empty status (graceful degradation)
- Extension not available: Returns empty status (graceful degradation)

**Notes:**
- This method never returns the actual API key values (for security)
- Returns graceful responses even if the extension is not available
- Useful for checking key configuration status before task execution
- Returns false/empty status if extension is not installed (graceful degradation)

#### `config.llm_key.delete`

**Description:**  
Deletes an LLM API key for a user. This method removes the stored API key for a specific provider, or all keys for the user if no provider is specified.

**Method:** `config.llm_key.delete`

**Parameters:**
- `user_id` (string, optional): User ID to delete keys for. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, raises an error.
- `provider` (string, optional): Provider name to delete key for. If not provided, deletes all keys for the user.

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.llm_key.delete",
  "params": {
    "user_id": "user123",
    "provider": "openai"
  },
  "id": "delete-key-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-key-request-1",
  "result": {
    "success": true,
    "user_id": "user123",
    "deleted": true,
    "provider": "openai"
  }
}
```

**Response Fields:**
- `success` (boolean): Whether the operation was successful
- `user_id` (string): User ID the key was deleted for
- `deleted` (boolean): Whether a key was actually deleted (false if key didn't exist)
- `provider` (string): Provider name (or "all" if no provider specified)

**Error Cases:**
- Missing user_id (and not authenticated): Returns error with code -32602
- Permission denied: Returns error with code -32001
- Extension not available: Returns error if llm-key-config extension is not installed

**Notes:**
- Requires the `llm-key-config` extension to be installed
- If provider is not specified, all keys for the user are deleted
- Returns `deleted: false` if the key didn't exist (not an error)
- Keys are permanently deleted and cannot be recovered

#### `examples.init`

**Description:**  
Initializes example data in the database. This method creates example tasks that can be used for testing and demonstration purposes. The method is idempotent - it will not create duplicate examples unless `force` is set to true.

**Method:** `examples.init`

**Parameters:**
- `force` (boolean, optional): If true, re-initializes examples even if they already exist (default: false)

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "examples.init",
  "params": {
    "force": false
  },
  "id": "init-examples-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "init-examples-request-1",
  "result": {
    "success": true,
    "created_count": 5,
    "message": "Successfully initialized 5 example tasks"
  }
}
```

**Response Fields:**
- `success` (boolean): Whether initialization was successful
- `created_count` (integer): Number of example tasks created
- `message` (string): Status message

**Error Cases:**
- Extension not available: Returns error if examples module is not installed
- Database error: Returns error with code -32603

**Notes:**
- Requires the `examples` extension to be installed
- Examples are created with default user_id if not specified
- Use `force=true` to re-initialize examples (may create duplicates)
- Useful for setting up demo environments and testing

#### `examples.status`

**Description:**  
Checks if example data is initialized in the database. This method verifies whether example tasks exist and returns their initialization status.

**Method:** `examples.status`

**Parameters:**  
None

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "examples.status",
  "params": {},
  "id": "status-examples-request-1"
}
```

**Example Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "status-examples-request-1",
  "result": {
    "initialized": true,
    "available": true,
    "message": "Examples data is initialized"
  }
}
```

**Response Fields:**
- `initialized` (boolean): Whether examples are initialized
- `available` (boolean): Whether the examples module is available
- `message` (string): Status message

**Error Cases:**
- Extension not available: Returns `available: false` (graceful degradation)

**Notes:**
- Returns graceful responses even if the extension is not available
- Useful for checking if examples need to be initialized
- Call `examples.init` if `initialized` is false

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

## LLM API Key Headers

For tasks that require LLM API keys (e.g., CrewAI tasks), you can provide keys via request headers.

### X-LLM-API-KEY Header

**Format:**
- Simple: `X-LLM-API-KEY: <api-key>` (provider auto-detected from model name)
- Provider-specific: `X-LLM-API-KEY: <provider>:<api-key>`

**Examples:**
```bash
# OpenAI (auto-detected from model name)
curl -X POST http://localhost:8000/tasks \
  -H "X-LLM-API-KEY: sk-your-openai-key" \
  -H "Content-Type: application/json" \
  -d '{...}'

# OpenAI (explicit provider)
curl -X POST http://localhost:8000/tasks \
  -H "X-LLM-API-KEY: openai:sk-your-openai-key" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Anthropic
curl -X POST http://localhost:8000/tasks \
  -H "X-LLM-API-KEY: anthropic:sk-ant-your-key" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Supported Providers:**
- `openai` - OpenAI (GPT models)
- `anthropic` - Anthropic (Claude models)
- `google` / `gemini` - Google (Gemini models)
- `mistral` - Mistral AI
- `groq` - Groq
- `cohere` - Cohere
- `together` - Together AI
- And more (see provider list in LLM Key Injector)

**Priority Order:**
1. Request header (`X-LLM-API-KEY`) - highest priority
2. User config (if `llm-key-config` extension is installed)
3. Environment variables (automatically read by CrewAI/LiteLLM)

**Note:** LLM keys are never stored in the database. They are only used during task execution and cleared after completion.

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

The API supports real-time progress updates via Server-Sent Events (SSE) and WebSocket. This allows clients to receive live updates about task execution progress without polling.

### Server-Sent Events (SSE) via `tasks.execute`

**Description:**  
When using `tasks.execute` with `use_streaming=true`, the endpoint returns a `StreamingResponse` with Server-Sent Events (SSE). The response stream includes the initial JSON-RPC response followed by real-time progress updates.

**Usage:**
Set `use_streaming=true` in the `tasks.execute` request parameters. The endpoint will return a streaming response with `Content-Type: text/event-stream`.

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "use_streaming": true
  },
  "id": "execute-request-1"
}
```

**Response Format:**
The response is an SSE stream. The first event contains the initial JSON-RPC response:
```
data: {"jsonrpc": "2.0", "id": "execute-request-1", "result": {"success": true, "protocol": "jsonrpc", "root_task_id": "task-abc-123", "task_id": "task-abc-123", "status": "started", "streaming": true, "message": "Task task-abc-123 execution started with streaming"}}

```

Subsequent events contain real-time progress updates:
```
data: {"type": "progress", "task_id": "task-abc-123", "status": "in_progress", "progress": 0.5, "message": "Task tree execution started", "timestamp": "2025-11-26T08:00:00"}

data: {"type": "task_completed", "task_id": "task-abc-123", "status": "completed", "result": {...}, "timestamp": "2025-11-26T08:00:05"}

data: {"type": "final", "task_id": "task-abc-123", "status": "completed", "result": {"progress": 1.0}, "final": true, "timestamp": "2025-11-26T08:00:05"}

data: {"type": "stream_end", "task_id": "task-abc-123"}

```

**Event Types:**
- `progress`: Task progress update
- `task_start`: Task execution started
- `task_completed`: Task completed successfully
- `task_failed`: Task execution failed
- `final`: Final status update (always sent at the end)
- `stream_end`: Stream connection closed

**Notes:**
- Connection remains open until task completes or client disconnects
- Events are sent in real-time as tasks execute
- Must parse SSE format (`data: {...}`) instead of expecting JSON response
- Suitable for web applications and simple client implementations
- Can be combined with `webhook_config` for dual update delivery

### `WebSocket /ws`

**Description:**  
WebSocket endpoint for bidirectional real-time communication. This endpoint supports both receiving task execution updates and sending commands. WebSocket provides lower latency and better performance than SSE for high-frequency updates.

**Authentication:**  
Optional (JWT token in WebSocket handshake headers if JWT is enabled)

**Connection:**
- Protocol: WebSocket (ws:// or wss://)
- URL: `ws://localhost:8000/ws` or `wss://localhost:8000/ws` (secure)
- Headers: Standard WebSocket headers, plus optional `Authorization: Bearer <token>`

**Message Format:**
Messages are sent and received as JSON:

**Incoming Messages (from server):**
```json
{
  "type": "task_progress",
  "task_id": "task-abc-123",
  "context_id": "task-abc-123",
  "data": {
    "progress": 0.5,
    "status": "in_progress"
  }
}
```

**Outgoing Messages (to server):**
```json
{
  "action": "subscribe",
  "task_id": "task-abc-123"
}
```

**Supported Actions:**
- `subscribe`: Subscribe to task updates
  - `task_id` (string, required): Task ID to subscribe to
- `unsubscribe`: Unsubscribe from task updates
  - `task_id` (string, required): Task ID to unsubscribe from
- `ping`: Keep-alive ping (server responds with `pong`)

**Example JavaScript Client:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  // Subscribe to task updates
  ws.send(JSON.stringify({
    action: 'subscribe',
    task_id: 'task-abc-123'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Update:', message);
  
  if (message.type === 'task_progress') {
    console.log(`Task ${message.task_id}: ${message.data.progress * 100}%`);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

**Event Types:**
Similar to SSE streaming in `tasks.execute` (when `use_streaming=true`):
- `task_progress`: Task progress update
- `task_status`: Task status change
- `task_completed`: Task completion notification
- `task_failed`: Task failure notification
- `pong`: Response to ping (keep-alive)

**Notes:**
- WebSocket provides bidirectional communication
- Lower latency than SSE for high-frequency updates
- Supports multiple subscriptions per connection
- Automatic reconnection recommended for production use
- Use secure WebSocket (wss://) in production environments
- Suitable for real-time dashboards and interactive applications

**Comparison: SSE (via tasks.execute) vs WebSocket:**
- **SSE (tasks.execute with use_streaming=true)**: Integrated with task execution, returns StreamingResponse directly, simpler for JSON-RPC clients, unidirectional (server to client)
- **WebSocket (/ws)**: Lower latency, bidirectional communication, better for high-frequency updates, requires custom reconnection logic

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

## Protocol Identification

The API supports two execution protocols, each with distinct response formats. To help clients identify which protocol a response belongs to, all responses include a `protocol` field.

### JSON-RPC Protocol (`/tasks` endpoint)

When using the `/tasks` endpoint with `tasks.execute`, responses include:

```json
{
  "success": true,
  "protocol": "jsonrpc",  // Protocol identifier
  "root_task_id": "...",
  "task_id": "...",
  "status": "started",
  ...
}
```

**Identification:**
- `protocol: "jsonrpc"` field in the response
- `success` field present
- No `kind` field

### A2A Protocol (`/` endpoint)

When using the A2A Protocol endpoint (`/`), responses include:

```json
{
  "id": "...",
  "kind": "task",
  "metadata": {
    "protocol": "a2a",  // Protocol identifier in metadata
    ...
  },
  "status": {
    "message": {
      "parts": [{
        "data": {
          "protocol": "a2a",  // Protocol identifier in event data
          ...
        }
      }]
    }
  }
}
```

**Identification:**
- `protocol: "a2a"` in `metadata` field
- `protocol: "a2a"` in status message parts data
- `kind: "task"` field present
- No `success` field

### How to Distinguish Protocols

**Method 1: Check `protocol` field (Recommended)**
```python
# JSON-RPC response
if response.get("protocol") == "jsonrpc":
    # Handle JSON-RPC response
    pass

# A2A Protocol response
if response.get("metadata", {}).get("protocol") == "a2a":
    # Handle A2A Protocol response
    pass

# Or check in event data
if event_data.get("protocol") == "a2a":
    # Handle A2A Protocol event
    pass
```

**Method 2: Check existing fields (Backward compatible)**
```python
# JSON-RPC response
if "success" in response:
    # Handle JSON-RPC response
    pass

# A2A Protocol response
if "kind" in response and response["kind"] == "task":
    # Handle A2A Protocol response
    pass
```

## CustomA2AStarletteApplication Custom Routes

The `CustomA2AStarletteApplication` extends the standard A2A Starlette Application with additional custom routes for task management and system operations.

### Custom Routes Overview

The custom application adds the following routes:

1. **`POST /tasks`** - Task management endpoint (see [Task Management Endpoints](#task-management-endpoints))
2. **`POST /system`** - System operations endpoint (see [System Endpoints](#system-endpoints))

These routes are enabled by default when using `CustomA2AStarletteApplication`. To disable them, set `enable_system_routes=False` when creating the application.

### Route Handler Architecture

The route handlers are implemented in the `api/routes/` directory as protocol-agnostic modules that can be reused across different protocol implementations (A2A, REST, GraphQL, etc.):

- **`api/routes/base.py`**: Provides `BaseRouteHandler` class with shared functionality for permission checking, user information extraction, and common utilities
- **`api/routes/tasks.py`**: Contains `TaskRoutes` class with handlers for task CRUD operations, execution, and monitoring
- **`api/routes/system.py`**: Contains `SystemRoutes` class with handlers for system operations like health checks, LLM key configuration, and examples management

This architecture allows the same route handlers to be used by different protocol implementations, promoting code reuse and maintainability.

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

**Note:** For JSON-RPC `tasks.execute` endpoint, use `use_streaming=true` parameter instead of `metadata.stream`. The endpoint will return a StreamingResponse with Server-Sent Events directly.

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

