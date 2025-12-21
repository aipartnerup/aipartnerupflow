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
      "id": "tasks.execute",
      "name": "Execute Task Tree",
      "description": "Execute a complete task tree with multiple tasks",
      "tags": ["task", "orchestration", "workflow", "execution"]
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
      "id": "tasks.execute",
      "name": "Execute Task Tree",
      "description": "Execute a complete task tree with multiple tasks",
      "tags": ["task", "orchestration", "workflow", "execution"]
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
          "method": "system_info_executor"
        },
        "inputs": {
          "resource": "cpu"
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
- `method` (string, required): Method name. Supports all task management operations:
  - `tasks.execute` (recommended) or `execute_task_tree` (backward compatible): Execute a task tree
  - `tasks.create`: Create new task(s)
  - `tasks.get`: Get task by ID
  - `tasks.update`: Update task
  - `tasks.delete`: Delete task
  - `tasks.detail`: Get full task details
  - `tasks.tree`: Get task tree structure
  - `tasks.list`: List tasks with filters
  - `tasks.children`: Get child tasks
  - `tasks.running.list`: List running tasks
  - `tasks.running.status`: Get running task status
  - `tasks.running.count`: Count running tasks
  - `tasks.cancel`: Cancel running task(s)
  - `tasks.copy`: Copy task tree
- `params` (object, required): Method parameters (varies by method)
  - For `tasks.execute` or `execute_task_tree`: `tasks` (array, required): Array of task objects to execute
- `id` (string/number, required): Request identifier for matching responses
- `configuration` (object, optional): Configuration for push notifications
  - `push_notification_config` (object, optional): Push notification settings
    - `url` (string, required): Callback URL for status updates
    - `headers` (object, optional): HTTP headers for callback requests
    - `method` (string, optional): HTTP method for callbacks (default: "POST")
- `metadata` (object, optional): Additional metadata
  - `stream` (boolean, optional): Enable streaming mode for real-time updates
  - `task_id` (string, optional): Existing task ID to execute. When provided with `copy_execution=true`, the task will be copied before execution.
  - `copy_execution` (boolean, optional): If `true`, copy the task specified by `metadata.task_id` before execution to preserve the original task's execution history. When `true`, creates a copy of the task tree and executes the copy, leaving the original task unchanged. Default: `false`.
  - `copy_children` (boolean, optional): If `true` and `copy_execution=true`, also copy each direct child task of the original task with its dependencies. When copying children, tasks that depend on multiple copied tasks are only copied once (deduplication by task ID). Default: `false`.

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
    "method": "tasks.execute",
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
    "method": "tasks.execute",
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
    "method": "tasks.execute",
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
- All task management operations (CRUD, query, execution, cancellation, copy) are now fully supported through the A2A Protocol `/` route
- Method naming: Use `tasks.execute` (recommended) or `execute_task_tree` (backward compatible) for task execution
- When `push_notification_config` is provided, the server executes tasks asynchronously and sends updates to the callback URL
- When `metadata.stream` is true, progress updates are sent via EventQueue (SSE/WebSocket). For JSON-RPC `tasks.execute`, use `use_streaming=true` instead.
- All task management methods return A2A Protocol Task objects with real-time status updates via `TaskStatusUpdateEvent`
- Task execution follows dependency order and priority scheduling
- All tasks in a tree must have the same `user_id` (or be accessible by the authenticated user)
- All responses include `protocol: "a2a"` in Task metadata and event data to identify this as an A2A Protocol response
- This differs from JSON-RPC protocol responses (which use `protocol: "jsonrpc"` in the response object)

#### `cancel` Method

**Description:**  
Cancels a running task execution. This method is part of the A2A Protocol `AgentExecutor` interface and allows clients to cancel tasks that are currently executing or pending.

**Method:** `cancel`

**Request Format:**
```json
{
  "jsonrpc": "2.0",
  "method": "cancel",
  "params": {},
  "id": "cancel-request-123",
  "task_id": "task-abc-123",
  "context_id": "context-xyz-456",
  "metadata": {
    "error_message": "Cancelled by user",
    "force": false
  }
}
```

**Request Parameters:**
- `jsonrpc` (string, required): JSON-RPC version, must be "2.0"
- `method` (string, required): Method name, must be "cancel"
- `params` (object, optional): Method parameters (currently unused, can be empty)
- `id` (string/number, required): Request identifier for matching responses
- `task_id` (string, optional): Task ID to cancel. Priority: `task_id` > `context_id` > `metadata.task_id` > `metadata.context_id`
- `context_id` (string, optional): Context ID (used as task ID if `task_id` is not provided)
- `metadata` (object, optional): Additional metadata
  - `error_message` (string, optional): Custom error message for cancellation
  - `force` (boolean, optional): Force flag (logged but not used by current implementation)
  - `task_id` (string, optional): Task ID (used as fallback if not in top-level `task_id`)
  - `context_id` (string, optional): Context ID (used as fallback if not in top-level `context_id`)

**Response Format:**
The response is sent via `TaskStatusUpdateEvent` through the EventQueue (SSE/WebSocket streaming):

```json
{
  "jsonrpc": "2.0",
  "id": "cancel-request-123",
  "result": {
    "task_id": "task-abc-123",
    "context_id": "context-xyz-456",
    "status": {
      "state": "canceled",
      "message": {
        "kind": "message",
        "parts": [
          {
            "kind": "data",
            "data": {
              "protocol": "a2a",
              "status": "cancelled",
              "message": "Task cancelled successfully",
              "token_usage": {
                "total_tokens": 1000,
                "prompt_tokens": 500,
                "completion_tokens": 500
              },
              "result": {
                "partial_data": "some result"
              },
              "timestamp": "2024-01-15T10:30:00Z"
            }
          }
        ]
      }
    },
    "final": true
  }
}
```

**Response Fields:**
- `task_id` (string): Task ID that was cancelled
- `context_id` (string): Context ID
- `status` (object): Task status object
  - `state` (string): Task state ("canceled" or "failed")
  - `message` (object): Status message with parts
    - `parts[].data.protocol` (string): Protocol identifier, always `"a2a"`
    - `parts[].data.status` (string): Cancellation status ("cancelled" or "failed")
    - `parts[].data.message` (string): Cancellation message
    - `parts[].data.token_usage` (object, optional): Token usage information if available
    - `parts[].data.result` (any, optional): Partial result if available
    - `parts[].data.error` (string, optional): Error message if cancellation failed
    - `parts[].data.timestamp` (string): ISO 8601 timestamp
- `final` (boolean): Always `true` for cancel operations

**Error Cases:**
- Task ID not found: Returns `TaskStatusUpdateEvent` with `state: "failed"` and error message "Task ID not found in context"
- Task not found: Returns `state: "failed"` with message "Task {task_id} not found"
- Task already completed: Returns `state: "failed"` with message "Task {task_id} is already {status}, cannot cancel"
- Task already cancelled: Returns `state: "failed"` with message "Task {task_id} is already cancelled, cannot cancel"
- Exception during cancellation: Returns `state: "failed"` with error details

**Notes:**
- The `cancel()` method attempts to gracefully cancel tasks by calling the executor's `cancel()` method if supported
- Token usage is preserved if available from the executor
- Partial results may be returned if the task was partially completed before cancellation
- The method sends a `TaskStatusUpdateEvent` through the EventQueue, which is compatible with SSE/WebSocket streaming
- Task ID extraction follows priority: `task_id` > `context_id` > `metadata.task_id` > `metadata.context_id`
- If no task ID is found, an error event is sent with `state: "failed"`

**Example: Cancel a Running Task**

```json
{
  "jsonrpc": "2.0",
  "method": "cancel",
  "params": {},
  "id": "cancel-1",
  "task_id": "my-running-task",
  "metadata": {
    "error_message": "User requested cancellation"
  }
}
```

**Example Response (via EventQueue):**
```json
{
  "task_id": "my-running-task",
  "context_id": "my-running-task",
  "status": {
    "state": "canceled",
    "message": {
      "parts": [{
        "data": {
          "protocol": "a2a",
          "status": "cancelled",
          "message": "Task cancelled successfully",
          "timestamp": "2024-01-15T10:30:00Z"
        }
      }]
    }
  },
  "final": true
}
```

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
          "method": "system_info_executor"
        },
        "inputs": {
          "resource": "cpu"
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
- `tasks.generate` - Generate task tree from natural language requirement
- `tasks.execute` - Execute a task by ID

**Request Headers:**
- `Content-Type`: `application/json` (required)
- `Authorization`: `Bearer <token>` (optional, if JWT is enabled, priority over cookie)
- `X-LLM-API-KEY`: `<api-key>` or `<provider>:<api-key>` (optional, for LLM tasks)

**Request Cookies (Alternative to Header):**
- `Authorization`: `<token>` (optional, if JWT is enabled, fallback if header not present)

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
- `schemas` (object, optional): Task schemas configuration. **If provided, the `method` field is REQUIRED.**
  - `method` (string, required when `schemas` is provided): **Executor ID** that must exactly match the executor's `id` from the extensions registry (registered via `@executor_register()`). This is the primary way to specify which executor should execute the task. Examples: `"system_info_executor"`, `"command_executor"`, `"rest_executor"`, `"crewai_executor"`, etc.
  - `type` (string, optional): Executor type for fallback lookup (e.g., `"stdio"`, `"http"`). Only used if `method` is not a registered executor ID.
  - `input_schema` (object, optional): Input validation schema (JSON Schema format)
  - `model` (string, optional): Model name for AI executors (e.g., `"gpt-4"`, `"claude-3-opus"`)
- `params` (object, optional): Executor initialization parameters. Can include `executor_id` as an alternative way to specify the executor (takes precedence over `schemas.method` if provided).
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
        "method": "system_info_executor"
      },
      "inputs": {
        "resource": "cpu"
      }
    },
    {
      "id": "child",
      "name": "Child Task",
      "user_id": "user123",
      "parent_id": "root",
      "schemas": {
        "method": "command_executor"
      },
      "inputs": {
        "command": "echo 'Processing system info'"
      }
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
    "inputs": {"resource": "cpu"},
    "result": {"system": "Darwin", "brand": "Apple M1 Pro", "cores": 10},
    "error": null,
    "schemas": {"method": "system_info_executor"},
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
Updates task properties with critical field validation. This method allows partial updates to task fields. Critical fields (`parent_id`, `user_id`, `dependencies`) are strictly validated to prevent fatal errors, while other fields can be updated freely without status restrictions.

**Method:** `tasks.update`

**Parameters:**
- `task_id` (string, required): Task ID to update
- `status` (string, optional): New status ("pending", "in_progress", "completed", "failed", "cancelled")
- `inputs` (object, optional): Updated input parameters (replaces entire inputs object)
- `name` (string, optional): Updated task name
- `priority` (integer, optional): Updated priority level
- `params` (object, optional): Updated executor parameters
- `schemas` (object, optional): Updated validation schemas
- `dependencies` (array, optional): Updated dependencies list (see validation rules below)
- `result` (object, optional): Updated result (replaces entire result object)
- `error` (string, optional): Error message (typically set when status is "failed")
- `progress` (float, optional): Progress value (0.0 to 1.0)
- `started_at` (string, optional): Start timestamp (ISO 8601 format)
- `completed_at` (string, optional): Completion timestamp (ISO 8601 format)

**Critical Field Validation Rules:**

1. **`parent_id`** - Always rejected
   - Cannot be modified after task creation
   - Error: "Cannot update 'parent_id': field cannot be modified (task hierarchy is fixed)"

2. **`user_id`** - Always rejected
   - Cannot be modified after task creation
   - Error: "Cannot update 'user_id': field cannot be modified (task ownership is fixed)"

3. **`dependencies`** - Conditional validation (only when updating)
   - **Status check**: Task must be in `pending` status
     - Error: "Cannot update 'dependencies': task status is '{status}' (must be 'pending')"
   - **Reference validation**: All dependency IDs must exist in the same task tree
     - Error: "Dependency reference '{dep_id}' not found in task tree"
   - **Circular dependency detection**: Prevents circular dependencies using DFS algorithm
     - Error: "Circular dependency detected: Task A -> Task B -> Task A"
   - **Execution check**: Prevents updates if dependent tasks are executing
     - Error: "Cannot update dependencies: task '{task_id}' has dependent tasks that are executing: ['task-456']"

**Other Fields:**
- All other fields (`inputs`, `name`, `priority`, `params`, `schemas`, `status`, `result`, `error`, `progress`, timestamps) can be updated freely without status restrictions.

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

**Example Request (Update Multiple Fields):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.update",
  "params": {
    "task_id": "task-abc-123",
    "name": "Updated Task Name",
    "priority": 3,
    "inputs": {"new_key": "new_value"},
    "status": "in_progress",
    "progress": 0.5
  },
  "id": "update-request-2"
}
```

**Example Request (Update Dependencies - Valid):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.update",
  "params": {
    "task_id": "task-abc-123",
    "dependencies": [
      {"id": "task-dep-1", "required": true},
      {"id": "task-dep-2", "required": false}
    ]
  },
  "id": "update-request-3"
}
```

**Example Response (Error - Critical Field Validation):**
```json
{
  "jsonrpc": "2.0",
  "id": "update-request-4",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Update failed:\n- Cannot update 'parent_id': field cannot be modified (task hierarchy is fixed)\n- Cannot update 'dependencies': task status is 'completed' (must be 'pending')"
  }
}
```

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Critical field violation (`parent_id`, `user_id`): Returns error with detailed message
- Dependencies validation failure: Returns error with specific validation failure reason:
  - Task not in `pending` status
  - Invalid dependency reference
  - Circular dependency detected
  - Dependent tasks are executing
- Invalid field values: Returns error with code -32602

**Notes:**
- Updates are atomic and immediately persisted to the database
- Critical fields (`parent_id`, `user_id`, `dependencies`) are validated strictly to prevent fatal errors
- Other fields can be updated from any task status without restrictions
- Dependencies can only be updated for `pending` tasks to ensure data integrity
- All validation errors are collected and returned together in a single error message
- Status changes may trigger dependent task execution
- Timestamps should be in ISO 8601 format
- Only authenticated users can update their own tasks (or admins can update any task)

### `tasks.delete`

**Description:**  
Physically deletes a task from the database with comprehensive validation. The task and all its children are permanently removed if deletion conditions are met. Deletion is only allowed when:
1. All tasks (the task itself + all children recursively) are in `pending` status
2. No other tasks depend on the task being deleted

If all conditions are met, the task and all its children are physically deleted. Otherwise, a detailed error message is returned explaining why deletion is not allowed.

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

**Example Response (Success):**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-request-1",
  "result": {
    "success": true,
    "task_id": "task-abc-123",
    "deleted_count": 4,
    "children_deleted": 3
  }
}
```

**Response Fields (Success):**
- `success` (boolean): Whether deletion was successful
- `task_id` (string): ID of the deleted task
- `deleted_count` (integer): Total number of tasks deleted (including the main task and all children)
- `children_deleted` (integer): Number of child tasks deleted

**Example Response (Error - Non-pending Children):**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-request-1",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Cannot delete task: task has 2 non-pending children: [child-1: in_progress, child-2: completed]"
  }
}
```

**Example Response (Error - Dependent Tasks):**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-request-1",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Cannot delete task: 2 tasks depend on this task: [dependent-1, dependent-2]"
  }
}
```

**Example Response (Error - Mixed Conditions):**
```json
{
  "jsonrpc": "2.0",
  "id": "delete-request-1",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Cannot delete task: task has 1 non-pending children: [child-1: completed]; 1 tasks depend on this task: [dependent-1]"
  }
}
```

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Task has non-pending children: Returns error with code -32602, includes list of non-pending children with their statuses
- Task itself is not pending: Returns error with code -32602, indicates current status
- Other tasks depend on this task: Returns error with code -32602, includes list of dependent task IDs
- Mixed conditions: Returns error with code -32602, includes all blocking conditions

**Deletion Conditions:**
- **All tasks must be pending**: The task itself and all its children (recursively) must be in `pending` status
- **No dependencies**: No other tasks can depend on the task being deleted
- **Recursive deletion**: When deletion is allowed, all child tasks (including grandchildren) are automatically deleted

**Notes:**
- Tasks are **physically deleted** from the database (not soft-deleted)
- Deletion is **atomic**: Either all tasks (task + children) are deleted, or none are deleted
- Child tasks are automatically deleted when the parent task is deleted (if all are pending)
- Deletion requires proper permissions (own task or admin role)
- Error messages provide detailed information about why deletion failed
- To delete a task with non-pending children, first cancel or complete those children
- To delete a task with dependencies, first remove or update the dependent tasks

### `tasks.copy`

**Description:**  
Creates a new executable copy of an existing task tree for re-execution. Supports two copy modes:
- **Minimal mode (default)**: Copies minimal subtree (original_task + children + dependents). All copied tasks are marked as pending for re-execution.
- **Full mode**: Copies complete tree from root. Tasks that need re-execution are marked as pending, unrelated successful tasks are marked as completed with preserved token_usage.

**Method:** `tasks.copy`

**What Gets Copied:**
- The original task and all its children (recursive)
- All tasks that depend on the original task (direct and transitive dependencies)
- Task structure (parent-child relationships)
- Task definitions (name, inputs, schemas, params, dependencies)
- User and product associations (user_id, product_id)
- Priority settings

**What Gets Reset (Minimal Mode):**
- Task IDs (new IDs generated)
- Status (reset to "pending")
- Progress (reset to 0.0)
- Result (reset to null)
- Error (reset to null)
- Execution timestamps (started_at, completed_at)

**What Gets Reset (Full Mode):**
- Task IDs (new IDs generated)
- Status: Tasks needing re-execution → "pending", unrelated tasks → "completed"
- Progress: Re-execution tasks → 0.0, unrelated tasks → 1.0
- Result: Re-execution tasks → null, unrelated tasks → preserved with token_usage
- Error: Re-execution tasks → null, unrelated tasks → preserved
- Execution timestamps: Re-execution tasks → reset, unrelated tasks → preserved

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
- `children` (boolean, optional): If `true`, also copy each direct child task of the original task with its dependencies. When copying children, tasks that depend on multiple copied tasks are only copied once (deduplication by task ID). Default: `false`.
- `copy_mode` (string, optional): Copy mode - `"minimal"` (default), `"full"`, or `"custom"`.
  - `"minimal"`: Copies minimal subtree (original_task + children + dependents). All copied tasks are marked as pending for re-execution.
  - `"full"`: Copies complete tree from root. Tasks that need re-execution are marked as pending, unrelated successful tasks are marked as completed with preserved token_usage.
  - `"custom"`: Copies only specified tasks. Requires `custom_task_ids` parameter.
- `custom_task_ids` (array of strings, optional): List of task IDs to copy. Required when `copy_mode="custom"`. Only tasks with IDs in this list (and their dependencies) will be copied.
- `custom_include_children` (boolean, optional): If `true`, also include all children recursively when using `copy_mode="custom"`. Default: `false`.
- `reset_fields` (array of strings, optional): List of field names to reset during copy. Common fields: `["status", "progress", "result", "error"]`. Default: `null` (uses mode-specific defaults).
- `save` (boolean, optional): If `true` (default), saves copied tasks to database and returns TaskTreeNode. If `false`, returns task array without saving to database (suitable for preview or direct use with `tasks.create`).

**Example Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123",
    "children": false
  },
  "id": "copy-request-1"
}
```

**Example Request with children:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123",
    "children": true
  },
  "id": "copy-request-2"
}
```

**Example Request with full mode:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123",
    "copy_mode": "full"
  },
  "id": "copy-request-3"
}
```

**Example Request with custom mode:**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123",
    "copy_mode": "custom",
    "custom_task_ids": ["task-abc-123", "task-child-456"],
    "custom_include_children": false
  },
  "id": "copy-request-4"
}
```

**Example Request with save=false (returns task array):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.copy",
  "params": {
    "task_id": "task-abc-123",
    "copy_mode": "minimal",
    "save": false
  },
  "id": "copy-request-5"
}
```

**Example Response (save=false):**
```json
{
  "jsonrpc": "2.0",
  "id": "copy-request-5",
  "result": {
    "tasks": [
      {
        "id": "new-uuid-1",
        "name": "Original Task Name",
        "parent_id": null,
        "dependencies": [],
        "status": "pending",
        "progress": 0.0
      },
      {
        "id": "new-uuid-2",
        "name": "Child Task",
        "parent_id": "new-uuid-1",
        "dependencies": [{"id": "new-uuid-1", "required": true}],
        "status": "pending",
        "progress": 0.0
      }
    ],
    "saved": false
  }
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
- The copied task tree has new task IDs (UUIDs) but preserves the original structure
- All execution fields are reset (status="pending", progress=0.0, result=null) unless `reset_fields` is specified
- The original task's `has_copy` flag is set to `true` when `save=true`
- Dependencies correctly reference new task IDs within the copied tree
- When `save=false`, the returned task array is compatible with `tasks.create` API
- Each copied task's `original_task_id` points to its direct original counterpart (not root)
- Failed leaf nodes are automatically handled (pending dependents are filtered out)
- The copied tree is ready for immediate execution

### `tasks.generate`

**Description:**  
Generates a valid task tree JSON array from a natural language requirement using LLM (Large Language Model). This method uses the `generate_executor` to create task structures that conform to the framework's requirements. The generated tasks can optionally be saved directly to the database for immediate execution.

**Method:** `tasks.generate`

**Parameters:**
- `requirement` (string, required): Natural language description of the desired task tree. Should describe the workflow, data flow, and operations needed.
- `user_id` (string, optional): User ID for the generated tasks. If not provided and JWT is enabled, uses authenticated user's ID. If not provided and JWT is disabled, uses default user ID.
- `llm_provider` (string, optional): LLM provider to use. Valid values: `"openai"`, `"anthropic"`. Default: `"openai"` or from environment variable `AIPARTNERUPFLOW_LLM_PROVIDER`.
- `model` (string, optional): Specific LLM model name. Examples: `"gpt-4o"`, `"claude-3-5-sonnet-20241022"`. Default: Provider-specific default or from environment variable `AIPARTNERUPFLOW_LLM_MODEL`.
- `temperature` (float, optional): LLM temperature for generation (0.0 to 2.0). Higher values make output more creative, lower values more deterministic. Default: `0.7`.
- `max_tokens` (integer, optional): Maximum number of tokens in LLM response. Default: `4000`.
- `save` (boolean, optional): If `true`, automatically saves the generated tasks to the database using `TaskCreator.create_task_tree_from_array()`. When `true`, the response includes `root_task_id` of the saved task tree. Default: `false`.

**LLM API Key Configuration:**
- Set `OPENAI_API_KEY` environment variable for OpenAI provider
- Set `ANTHROPIC_API_KEY` environment variable for Anthropic provider
- API keys can also be provided via `.env` file in the project root

**Example Request (Generate Only):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.generate",
  "params": {
    "requirement": "Fetch data from API, process it, and save to database",
    "user_id": "user123"
  },
  "id": "generate-request-1"
}
```

**Example Request (With LLM Configuration):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.generate",
  "params": {
    "requirement": "Create a workflow to fetch user data from REST API, transform it, and store in database",
    "user_id": "user123",
    "llm_provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4000
  },
  "id": "generate-request-2"
}
```

**Example Request (Save to Database):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.generate",
  "params": {
    "requirement": "Fetch data from two APIs in parallel, merge results, and save to database",
    "user_id": "user123",
    "save": true
  },
  "id": "generate-request-3"
}
```

**Example Response (Generate Only):**
```json
{
  "jsonrpc": "2.0",
  "id": "generate-request-1",
  "result": {
    "tasks": [
      {
        "name": "rest_executor",
        "inputs": {
          "url": "https://api.example.com/data",
          "method": "GET"
        },
        "priority": 1
      },
      {
        "name": "command_executor",
        "dependencies": [{"id": "task_1", "required": true}],
        "inputs": {
          "command": "python process_data.py --input /tmp/api_response.json"
        },
        "priority": 2
      },
      {
        "name": "database_executor",
        "dependencies": [{"id": "task_2", "required": true}],
        "inputs": {
          "table": "processed_data",
          "data": "{{task_2.result}}"
        },
        "priority": 2
      }
    ],
    "count": 3,
    "message": "Successfully generated 3 task(s)"
  }
}
```

**Example Response (Save to Database):**
```json
{
  "jsonrpc": "2.0",
  "id": "generate-request-3",
  "result": {
    "tasks": [
      {
        "name": "rest_executor",
        "inputs": {
          "url": "https://api1.example.com/data",
          "method": "GET"
        },
        "priority": 1
      },
      {
        "name": "rest_executor",
        "inputs": {
          "url": "https://api2.example.com/data",
          "method": "GET"
        },
        "priority": 1
      },
      {
        "name": "aggregate_results_executor",
        "dependencies": [
          {"id": "task_1", "required": true},
          {"id": "task_2", "required": true}
        ],
        "inputs": {
          "tasks": ["task_1", "task_2"]
        },
        "priority": 2
      }
    ],
    "count": 3,
    "root_task_id": "generated-root-task-abc-123",
    "message": "Successfully generated 3 task(s) and saved to database (root_task_id: generated-root-task-abc-123)"
  }
}
```

**Response Fields:**
- `tasks` (array): Generated task tree JSON array. Each task object follows the standard task format with `name`, `inputs`, `dependencies`, `priority`, etc.
- `count` (integer): Number of tasks generated
- `root_task_id` (string, optional): Present only when `save=true`. The ID of the root task in the saved task tree.
- `message` (string): Status message describing the generation result

**Error Cases:**
- Missing `requirement`: Returns error with code -32602, message "Requirement is a mandatory input for tasks.generate."
- Missing LLM API key: Returns error with code -32602, message "LLM API key not found. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable or in a .env file."
- LLM generation failed: Returns error with code -32602, includes error details from LLM API
- Validation failed: Returns error with code -32602, includes validation error details
- Permission denied: Returns error with code -32001 (if JWT is enabled and user cannot generate tasks for specified user_id)

**Validation:**
The generated tasks are automatically validated to ensure they conform to `TaskCreator.create_task_tree_from_array()` requirements:
- All tasks have `name` field matching available executor IDs
- Either all tasks have `id` field or none do (no mixing)
- All `parent_id` references exist in the array
- All `dependencies` references exist in the array
- No circular dependencies
- Single root task (task with no `parent_id`)
- All tasks are reachable from the root task

**Notes:**
- The LLM uses framework documentation and available executor information to generate appropriate task structures
- Generated tasks use realistic input parameters based on executor schemas
- For better results, provide detailed requirements describing:
  - Data flow between steps
  - Parallel vs sequential operations
  - Specific operations (API calls, database operations, file processing, etc.)
- When `save=true`, the generated tasks are immediately saved and ready for execution
- Use the returned `tasks` array with `TaskCreator.create_task_tree_from_array()` if you need custom processing before saving
- The method respects permission checks if JWT is enabled
- LLM API keys are never stored in the database, only used during generation
- Generation may take several seconds depending on LLM provider and model

**Tips for Better Generation:**
- Use specific keywords: "parallel", "sequential", "merge", "aggregate" help guide the generation
- Describe data flow: Explain how data moves between steps
- Mention executors: Specify operations like "API", "database", "file", "command" for better executor selection
- Be detailed: More context leads to more accurate task trees
- Example: "Fetch data from two different APIs in parallel, then merge the results and save to database"

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
- `copy_execution` (boolean, optional): If `true`, copy the task before execution to preserve the original task's execution history. Only applies to `task_id` mode. When `true`, creates a copy of the task tree and executes the copy, leaving the original task unchanged. Default: `false`.
- `copy_children` (boolean, optional): If `true` and `copy_execution=true`, also copy each direct child task of the original task with its dependencies. When copying children, tasks that depend on multiple copied tasks are only copied once (deduplication by task ID). Default: `false`.
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

**Example Request (Copy before execution):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "copy_execution": true,
    "copy_children": false
  },
  "id": "execute-request-2"
}
```

**Example Request (Copy with children before execution):**
```json
{
  "jsonrpc": "2.0",
  "method": "tasks.execute",
  "params": {
    "task_id": "task-abc-123",
    "copy_execution": true,
    "copy_children": true
  },
  "id": "execute-request-3"
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

**Example Response (Copy before execution):**
```json
{
  "jsonrpc": "2.0",
  "id": "execute-request-2",
  "result": {
    "success": true,
    "protocol": "jsonrpc",
    "root_task_id": "task-copy-xyz-789",
    "task_id": "task-copy-xyz-789",
    "original_task_id": "task-abc-123",
    "status": "started",
    "message": "Task execution started"
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
- `root_task_id` (string): ID of the root task in the tree (copied task ID if `copy_execution=true`)
- `task_id` (string): ID of the task that was executed (copied task ID if `copy_execution=true`)
- `original_task_id` (string, optional): Present only when `copy_execution=true`. The ID of the original task that was copied before execution.
- `status` (string): Execution status ("started", "already_running", "failed")
- `message` (string): Status message
- `streaming` (boolean, optional): Present when `use_streaming=true` or `webhook_config` is provided. Indicates that streaming/webhook mode is enabled.
- `webhook_url` (string, optional): Present only when `webhook_config` is provided. The webhook URL where updates will be sent.

**Error Cases:**
- Task not found: Returns error with code -32602
- Permission denied: Returns error with code -32001
- Task already running: Returns success=false with status "already_running"

**Notes:**
- When `copy_execution=true`, the original task is copied before execution, preserving its execution history. The copied task is then executed, and the response includes both `task_id` (the copied task) and `original_task_id` (the original task).
- The `copy_execution` parameter only applies to `task_id` mode (executing existing tasks), not `tasks_array` mode (creating new tasks).
- When `copy_children=true` and `copy_execution=true`, each direct child task of the original task is also copied with its dependencies. Tasks that depend on multiple copied tasks are only copied once (deduplication by task ID).
- The copied task tree has new task IDs but preserves the original structure. All execution fields are reset (status="pending", progress=0.0, result=null).
- The original task's `has_copy` flag is set to `true` after copying.

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

## Authentication

### JWT Authentication

The API supports optional JWT authentication. To enable:

1. Set environment variable `AIPARTNERUPFLOW_JWT_SECRET_KEY`
2. Include JWT token in request headers or cookies

**Token Sources (Priority Order):**
1. **Authorization Header** (highest priority): `Authorization: Bearer <token>`
2. **Cookie** (fallback): `Authorization` cookie containing the token

**Token Format:**
```
# Header format
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Cookie format (alternative)
Cookie: Authorization=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Payload:**
```json
{
  "user_id": "user123",
  "sub": "user123",  // Standard JWT claim (used if user_id not present)
  "roles": ["admin"],
  "exp": 1234567890
}
```

**Token Generation:**
You can generate JWT tokens using the `generate_token()` function:

```python
from aipartnerupflow.api.a2a.server import generate_token

# Generate token with user_id
payload = {"user_id": "user123", "roles": ["admin"]}
secret_key = "your-secret-key"
token = generate_token(payload, secret_key, expires_in_days=30)

# Use token in requests
headers = {"Authorization": f"Bearer {token}"}
```

**Permission Checking:**
- If `roles` contains `"admin"`, user can access any task
- Otherwise, user can only access tasks with matching `user_id`
- If no `user_id` in token, the `sub` field is used as fallback
- If no `user_id` or `sub` in token, permission checking is skipped

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
        "schemas": {"method": "system_info_executor"},
        "inputs": {"resource": "cpu"}
      },
      {
        "id": "child",
        "name": "Child Task",
        "user_id": "user123",
        "parent_id": "root",
        "schemas": {"method": "command_executor"},
        "inputs": {"command": "echo 'Processing system info'"}
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
    enable_system_routes=True,  # Enable custom routes (default: True)
    auto_initialize_extensions=False,  # Optional: auto-initialize extensions (default: False)
    task_routes_class=None,  # Optional: custom TaskRoutes class
)
```

**New Parameters:**
- `auto_initialize_extensions`: If `True`, automatically calls `initialize_extensions()` before creating the server. Matches behavior of `create_app_by_protocol()`. Default: `False` (backward compatible).
- `task_routes_class`: Optional custom `TaskRoutes` class to use instead of default. Allows extending TaskRoutes functionality without monkey patching. Default: `None` (uses default `TaskRoutes`).

### JWT Authentication

The custom application supports optional JWT authentication via middleware:

```python
from aipartnerupflow.api.a2a.server import create_a2a_server, generate_token, verify_token

# Generate JWT token
payload = {"user_id": "user123", "roles": ["admin"]}
secret_key = "your-secret-key"
token = generate_token(payload, secret_key, expires_in_days=30)

# Verify JWT token (built-in function)
def verify_token_func(token: str) -> Optional[dict]:
    """JWT token verification using built-in function"""
    return verify_token(token, secret_key)

# Or use custom verification
def custom_verify_token(token: str) -> Optional[dict]:
    """Custom JWT token verification function"""
    # Your token verification logic
    return payload if valid else None

app = create_a2a_server(
    verify_token_func=verify_token_func,  # or custom_verify_token
    verify_token_secret_key=secret_key,  # Optional: for built-in verification
    enable_system_routes=True
)
```

**Token Sources:**
- JWT tokens can be provided via `Authorization: Bearer <token>` header (priority)
- Or via `Authorization` cookie (fallback)
- Both methods are supported for flexible authentication scenarios

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

### Copy Before Execution

The A2A protocol supports copying existing tasks before execution via `metadata.copy_execution` and `metadata.copy_children`. This feature allows you to preserve the original task's execution history while creating a new execution instance.

#### When to Use Copy Execution

- **Preserve Execution History**: When you want to re-execute a task without losing the original task's results and status
- **A/B Testing**: Compare different execution strategies on the same task definition
- **Retry Failed Tasks**: Create a fresh copy of a failed task for retry without modifying the original
- **Task Templates**: Use completed tasks as templates for new executions

#### Basic Copy Execution

To copy a task before execution, provide the task ID in `metadata.task_id` and set `metadata.copy_execution=true`:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {},
  "metadata": {
    "task_id": "existing-task-id",
    "copy_execution": true
  },
  "id": "request-123"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "id": "task-execution-id",
    "context_id": "copied-task-id",
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
              "root_task_id": "copied-task-id",
              "task_count": 1
            }
          }
        ]
      }
    },
    "metadata": {
      "protocol": "a2a",
      "root_task_id": "copied-task-id",
      "original_task_id": "existing-task-id",
      "user_id": "user123"
    }
  }
}
```

**Key Points:**
- The original task (`existing-task-id`) remains unchanged
- A new task (`copied-task-id`) is created and executed
- The response includes both `root_task_id` (the copied task) and `original_task_id` (the original task) in metadata
- All execution-specific fields (status, result, progress) are reset in the copy

#### Copy with Children

To also copy child tasks and their dependencies, set `metadata.copy_children=true`:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {},
  "metadata": {
    "task_id": "parent-task-id",
    "copy_execution": true,
    "copy_children": true
  },
  "id": "request-123"
}
```

**Behavior:**
- The parent task is copied
- Each direct child task of the parent is also copied
- All dependencies of the copied children are included
- Tasks that depend on multiple copied children are only copied once (automatic deduplication)

**Example Scenario:**
```
Original Task Tree:
- Parent Task (id: parent-1)
  - Child 1 (id: child-1, depends on: dep-1)
  - Child 2 (id: child-2, depends on: dep-1, dep-2)
  - Dependency 1 (id: dep-1)
  - Dependency 2 (id: dep-2)

After copy_execution=true, copy_children=true:
- Copied Parent Task (id: parent-1-copy)
  - Copied Child 1 (id: child-1-copy, depends on: dep-1-copy)
  - Copied Child 2 (id: child-2-copy, depends on: dep-1-copy, dep-2-copy)
  - Copied Dependency 1 (id: dep-1-copy) - copied only once, shared by both children
  - Copied Dependency 2 (id: dep-2-copy)
```

#### Copy Execution with Streaming

Copy execution works with streaming mode:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_task_tree",
  "params": {},
  "metadata": {
    "task_id": "existing-task-id",
    "copy_execution": true,
    "copy_children": true,
    "stream": true
  },
  "id": "request-123"
}
```

The streaming events will include `original_task_id` in the metadata:

```json
{
  "task_id": "task-execution-id",
  "context_id": "copied-task-id",
  "status": {
    "state": "working",
    "message": {
      "parts": [
        {
          "kind": "data",
          "data": {
            "protocol": "a2a",
            "status": "in_progress",
            "progress": 0.5,
            "root_task_id": "copied-task-id",
            "metadata": {
              "original_task_id": "existing-task-id"
            }
          }
        }
      ]
    }
  },
  "final": false
}
```

#### Important Notes

1. **Task ID Required**: When `copy_execution=true`, `metadata.task_id` must be provided. The task must exist in the database.

2. **Only for Existing Tasks**: Copy execution only works with existing tasks. It cannot be used with `params.tasks` array (creating new tasks).

3. **Dependency Handling**: When `copy_children=true`, all dependencies are automatically included. The system ensures no duplicate copies of shared dependencies.

4. **Execution State Reset**: Copied tasks have their execution state reset:
   - `status`: Set to `"pending"`
   - `result`: Set to `None`
   - `progress`: Set to `0.0`
   - `original_task_id`: Links to the original task

5. **Original Task Unchanged**: The original task and its execution history remain completely unchanged.

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

