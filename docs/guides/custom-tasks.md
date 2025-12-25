# Custom Tasks Guide

Learn how to create your own custom executors (tasks) in aipartnerupflow. This guide will walk you through everything from simple tasks to advanced patterns.

## What You'll Learn

- ✅ How to create custom executors
- ✅ How to register and use them
- ✅ Input validation with JSON Schema
- ✅ Error handling best practices
- ✅ Common patterns and examples
- ✅ Testing your custom tasks

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding Executors](#understanding-executors)
3. [Creating Your First Executor](#creating-your-first-executor)
4. [Required Components](#required-components)
5. [Input Schema](#input-schema)
6. [Error Handling](#error-handling)
7. [Common Patterns](#common-patterns)
8. [Advanced Features](#advanced-features)
9. [Best Practices](#best-practices)
10. [Testing](#testing)

## Quick Start

The fastest way to create a custom executor:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class MyFirstExecutor(BaseTask):
    """A simple custom executor"""
    
    id = "my_first_executor"
    name = "My First Executor"
    description = "Does something useful"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        result = f"Processed: {inputs.get('data', 'no data')}"
        return {"status": "completed", "result": result}
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Input data"}
            },
            "required": ["data"]
        }
```

**That's it!** Just import it and use it:

```python
# Import to register
from my_module import MyFirstExecutor

# Use it
task = await task_manager.task_repository.create_task(
    name="my_first_executor",  # Must match id
    user_id="user123",
    inputs={"data": "Hello!"}
)
```

## Understanding Executors

### What is an Executor?

An **executor** is a piece of code that performs a specific task. Think of it as a function that:
- Takes inputs (parameters)
- Does some work
- Returns a result

**Example:**
- An executor that fetches data from an API
- An executor that processes files
- An executor that sends emails
- An executor that runs AI models

### Executor vs Task

**Executor**: The code that does the work (reusable)
**Task**: An instance of work to be done (specific execution)

**Analogy:**
- **Executor** = A recipe (reusable template)
- **Task** = A specific meal made from the recipe (one-time execution)

### BaseTask vs ExecutableTask

**BaseTask**: Recommended base class (simpler, includes registration)
```python
from aipartnerupflow import BaseTask, executor_register

@executor_register()
class MyTask(BaseTask):
    id = "my_task"
    # ...
```

**ExecutableTask**: Lower-level interface (more control)
```python
from aipartnerupflow import ExecutableTask

class MyTask(ExecutableTask):
    @property
    def id(self) -> str:
        return "my_task"
    # ...
```

**Recommendation**: Use `BaseTask` with `@executor_register()` - it's simpler!

## Creating Your First Executor

Let's create a complete, working example step by step.

### Step 1: Create the Executor Class

Create a file `greeting_executor.py`:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class GreetingExecutor(BaseTask):
    """Creates personalized greetings"""
    
    id = "greeting_executor"
    name = "Greeting Executor"
    description = "Creates personalized greeting messages"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute greeting creation"""
        name = inputs.get("name", "Guest")
        language = inputs.get("language", "en")
        
        greetings = {
            "en": f"Hello, {name}!",
            "es": f"¡Hola, {name}!",
            "fr": f"Bonjour, {name}!"
        }
        
        return {
            "greeting": greetings.get(language, greetings["en"]),
            "name": name,
            "language": language
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the person to greet"
                },
                "language": {
                    "type": "string",
                    "enum": ["en", "es", "fr", "zh"],
                    "description": "Language for the greeting",
                    "default": "en"
                }
            },
            "required": ["name"]
        }
```

### Step 2: Use Your Executor

Create a file `use_greeting.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
# Import to register the executor
from greeting_executor import GreetingExecutor

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create task using your executor
    task = await task_manager.task_repository.create_task(
        name="greeting_executor",  # Must match executor id
        user_id="user123",
        inputs={
            "name": "Alice",
            "language": "en"
        }
    )
    
    # Execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Greeting: {result.result['greeting']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Run It

```bash
python use_greeting.py
```

**Expected Output:**
```
Greeting: Hello, Alice!
```

**Congratulations!** You just created and used your first custom executor! 🎉

## Required Components

Every executor must have these components:

### 1. Unique ID

**Purpose**: Identifies the executor (used when creating tasks)

```python
id = "my_executor_id"  # Must be unique across all executors
```

**Best Practices:**
- Use lowercase with underscores
- Be descriptive: `fetch_user_data` not `task1`
- Keep it consistent: don't change after deployment

### 2. Display Name

**Purpose**: Human-readable name

```python
name = "My Executor"  # What users see
```

### 3. Description

**Purpose**: Explains what the executor does

```python
description = "Fetches user data from the API"
```

### 4. Execute Method

**Purpose**: The actual work happens here

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the task
    
    Args:
        inputs: Input parameters (from task.inputs)
        
    Returns:
        Execution result dictionary
    """
    # Your logic here
    return {"status": "completed", "result": "..."}
```

**Key Points:**
- Must be `async`
- Receives `inputs` dictionary
- Returns a dictionary
- Can raise exceptions (will be caught by TaskManager)

### 5. Input Schema

**Purpose**: Defines what inputs are expected (for validation)

```python
def get_input_schema(self) -> Dict[str, Any]:
    """
    Return JSON Schema for input parameters
    
    Returns:
        JSON Schema dictionary
    """
    return {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    }
```

## Input Schema

Input schemas use JSON Schema format to define and validate inputs.

### Basic Schema

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        },
        "required": ["name"]
    }
```

### Common Field Types

#### String

```python
"name": {
    "type": "string",
    "description": "Person's name",
    "minLength": 1,
    "maxLength": 100
}
```

#### Integer

```python
"age": {
    "type": "integer",
    "description": "Person's age",
    "minimum": 0,
    "maximum": 150
}
```

#### Boolean

```python
"enabled": {
    "type": "boolean",
    "description": "Whether feature is enabled",
    "default": false
}
```

#### Array

```python
"items": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of items",
    "minItems": 1
}
```

#### Object

```python
"config": {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "string"}
    },
    "description": "Configuration object"
}
```

#### Enum (Limited Choices)

```python
"status": {
    "type": "string",
    "enum": ["pending", "active", "completed"],
    "description": "Task status",
    "default": "pending"
}
```

### Default Values

Provide defaults for optional parameters:

```python
"timeout": {
    "type": "integer",
    "description": "Timeout in seconds",
    "default": 30  # Used if not provided
}
```

### Required Fields

Specify which fields are required:

```python
{
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"}
    },
    "required": ["name", "email"]  # Both required
}
```

### Complete Schema Example

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "API endpoint URL",
                "format": "uri"
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE"],
                "description": "HTTP method",
                "default": "GET"
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers",
                "additionalProperties": {"type": "string"}
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "minimum": 1,
                "maximum": 300,
                "default": 30
            },
            "retry": {
                "type": "boolean",
                "description": "Whether to retry on failure",
                "default": false
            }
        },
        "required": ["url"]
    }
```

## Error Handling

### Returning Errors (Recommended)

Return error information in the result:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = perform_operation(inputs)
        return {"status": "completed", "result": result}
    except ValueError as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "validation_error"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "execution_error"
        }
```

**Benefits:**
- More control over error format
- Can include additional context
- Task status will be "failed"

### Raising Exceptions

You can also raise exceptions (TaskManager will catch them):

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    if not inputs.get("required_param"):
        raise ValueError("required_param is required")
    
    # Continue with execution
    return {"status": "completed", "result": "..."}
```

**Note**: TaskManager will catch exceptions and mark the task as "failed".

### Best Practices

1. **Validate early**: Check inputs at the start
2. **Return meaningful errors**: Include error type and message
3. **Handle specific exceptions**: Catch specific errors, not just `Exception`
4. **Include context**: Add relevant information to error messages

**Example:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    url = inputs.get("url")
    if not url:
        return {
            "status": "failed",
            "error": "URL is required",
            "error_type": "validation_error",
            "field": "url"
        }
    
    if not isinstance(url, str):
        return {
            "status": "failed",
            "error": "URL must be a string",
            "error_type": "type_error",
            "field": "url",
            "received_type": type(url).__name__
        }
    
    # Continue with execution
    try:
        result = await fetch_url(url)
        return {"status": "completed", "result": result}
    except TimeoutError:
        return {
            "status": "failed",
            "error": f"Request to {url} timed out",
            "error_type": "timeout_error"
        }
```

## Common Patterns

### Pattern 1: HTTP API Call

```python
import aiohttp
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class APICallExecutor(BaseTask):
    """Calls an external HTTP API"""
    
    id = "api_call_executor"
    name = "API Call Executor"
    description = "Calls an external HTTP API"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        url = inputs.get("url")
        method = inputs.get("method", "GET")
        headers = inputs.get("headers", {})
        timeout = inputs.get("timeout", 30)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    data = await response.json() if response.content_type == "application/json" else await response.text()
                    
                    return {
                        "status": "completed",
                        "status_code": response.status,
                        "data": data
                    }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "API URL"},
                "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                "headers": {"type": "object"},
                "timeout": {"type": "integer", "default": 30}
            },
            "required": ["url"]
        }
```

### Pattern 2: Data Processing

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class DataProcessor(BaseTask):
    """Processes data"""
    
    id = "data_processor"
    name = "Data Processor"
    description = "Processes data with various operations"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data", [])
        operation = inputs.get("operation", "sum")
        
        if not isinstance(data, list):
            return {
                "status": "failed",
                "error": "Data must be a list",
                "error_type": "validation_error"
            }
        
        if operation == "sum":
            result = sum(data)
        elif operation == "average":
            result = sum(data) / len(data) if data else 0
        elif operation == "max":
            result = max(data) if data else None
        elif operation == "min":
            result = min(data) if data else None
        else:
            return {
                "status": "failed",
                "error": f"Unknown operation: {operation}",
                "error_type": "validation_error"
            }
        
        return {
            "status": "completed",
            "operation": operation,
            "result": result,
            "input_count": len(data)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of numbers"
                },
                "operation": {
                    "type": "string",
                    "enum": ["sum", "average", "max", "min"],
                    "default": "sum"
                }
            },
            "required": ["data"]
        }
```

### Pattern 3: File Operations

```python
import aiofiles
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class FileReader(BaseTask):
    """Reads files"""
    
    id = "file_reader"
    name = "File Reader"
    description = "Reads content from files"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        file_path = inputs.get("file_path")
        
        if not file_path:
            return {
                "status": "failed",
                "error": "file_path is required",
                "error_type": "validation_error"
            }
        
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            return {
                "status": "completed",
                "file_path": file_path,
                "content": content,
                "size": len(content)
            }
        except FileNotFoundError:
            return {
                "status": "failed",
                "error": f"File not found: {file_path}",
                "error_type": "file_not_found"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to file"
                }
            },
            "required": ["file_path"]
        }
```

### Pattern 4: Database Query

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class DatabaseQuery(BaseTask):
    """Executes database queries"""
    
    id = "db_query"
    name = "Database Query"
    description = "Executes database queries"
    
    def __init__(self):
        super().__init__()
        # Initialize database connection
        # self.db = create_db_connection()
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query")
        params = inputs.get("params", {})
        
        if not query:
            return {
                "status": "failed",
                "error": "query is required",
                "error_type": "validation_error"
            }
        
        try:
            # Execute query
            # result = await self.db.fetch(query, params)
            result = []  # Placeholder
            
            return {
                "status": "completed",
                "rows": result,
                "count": len(result)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": "database_error"
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query"},
                "params": {"type": "object", "description": "Query parameters"}
            },
            "required": ["query"]
        }
```

## Advanced Features

### Cancellation Support

Implement cancellation for long-running tasks:

```python
class CancellableTask(BaseTask):
    cancelable: bool = True  # Mark as cancellable
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self._cancelled = False
        
        for i in range(100):
            # Check for cancellation
            if self._cancelled:
                return {
                    "status": "cancelled",
                    "message": "Task was cancelled",
                    "progress": i
                }
            
            # Do work
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "result": "done"}
    
    async def cancel(self) -> Dict[str, Any]:
        """Cancel task execution"""
        self._cancelled = True
        return {
            "status": "cancelled",
            "message": "Cancellation requested"
        }
```

**Note**: Not all executors need cancellation. Only implement if your task can be safely cancelled.

### Accessing Task Context

Access task information through the executor:

```python
class ContextAwareTask(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Task context is available through TaskManager
        # You can access it via hooks or by storing task reference
        
        # Example: Access task ID (if available)
        # task_id = getattr(self, '_task_id', None)
        
        return {"status": "completed"}
```

## Best Practices

### 1. Keep Tasks Focused

**Good:**
```python
class FetchUserData(BaseTask):
    # Only fetches user data
```

**Bad:**
```python
class DoEverything(BaseTask):
    # Fetches, processes, saves, sends notifications, etc.
```

### 2. Validate Inputs Early

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Validate at the start
    url = inputs.get("url")
    if not url:
        return {"status": "failed", "error": "URL is required"}
    
    if not isinstance(url, str):
        return {"status": "failed", "error": "URL must be a string"}
    
    # Continue with execution
```

### 3. Use Async Properly

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    return {"status": "completed", "data": data}
```

**Bad:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    import requests
    response = requests.get(url)  # Blocking!
    return {"status": "completed", "data": response.json()}
```

### 4. Document Your Tasks

```python
class MyCustomTask(BaseTask):
    """
    Custom task that performs specific operations.
    
    This task processes input data and returns processed results.
    It supports various processing modes and configurations.
    
    Example:
        task = create_task(
            name="my_custom_task",
            inputs={"data": [1, 2, 3], "mode": "sum"}
        )
    """
```

### 5. Return Consistent Results

```python
# Good: Consistent format
return {
    "status": "completed",
    "result": result,
    "metadata": {...}
}

# Bad: Inconsistent format
return result  # Sometimes just the result
return {"data": result}  # Sometimes wrapped
```

## Testing

### Unit Testing

Test your executor in isolation:

```python
import pytest
from my_executors import GreetingExecutor

@pytest.mark.asyncio
async def test_greeting_executor():
    executor = GreetingExecutor()
    
    # Test with valid inputs
    result = await executor.execute({
        "name": "Alice",
        "language": "en"
    })
    
    assert result["status"] == "completed"
    assert "Hello, Alice!" in result["greeting"]
    
    # Test with default language
    result = await executor.execute({"name": "Bob"})
    assert result["language"] == "en"
    
    # Test with invalid language
    result = await executor.execute({
        "name": "Charlie",
        "language": "invalid"
    })
    # Should handle gracefully
```

### Integration Testing

Test with TaskManager:

```python
import pytest
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
from my_executors import GreetingExecutor

@pytest.mark.asyncio
async def test_executor_integration():
    # Import to register
    from my_executors import GreetingExecutor
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create and execute task
    task = await task_manager.task_repository.create_task(
        name="greeting_executor",
        user_id="test_user",
        inputs={"name": "Test User", "language": "en"}
    )
    
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Verify result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    assert result.status == "completed"
    assert "Test User" in result.result["greeting"]
```

## Built-in Executors

aipartnerupflow provides several built-in executors for common use cases. These executors are automatically registered and can be used directly in your tasks.

### HTTP/REST API Executor

Execute HTTP requests to external APIs, webhooks, and HTTP-based services.

**Installation:**
```bash
# httpx is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "rest_executor"
    },
    "inputs": {
        "url": "https://api.example.com/users",
        "method": "GET",
        "headers": {"Authorization": "Bearer token"},
        "timeout": 30.0
    }
}
```

**Features:**
- Supports GET, POST, PUT, DELETE, PATCH methods
- Authentication: Bearer token, Basic auth, API key
- Custom headers and query parameters
- JSON and form data support
- SSL verification control

### SSH Remote Executor

Execute commands on remote servers via SSH.

**Installation:**
```bash
pip install aipartnerupflow[ssh]
```

**Usage:**
```python
{
    "schemas": {
        "method": "ssh_executor"
    },
    "inputs": {
        "host": "example.com",
        "username": "user",
        "key_file": "/path/to/key",
        "command": "ls -la",
        "timeout": 30
    }
}
```

**Features:**
- Password and key-based authentication
- Environment variable support
- Automatic key file permission validation
- Command timeout handling

### Docker Container Executor

Execute commands in isolated Docker containers.

**Installation:**
```bash
pip install aipartnerupflow[docker]
```

**Usage:**
```python
{
    "schemas": {
        "method": "docker_executor"
    },
    "inputs": {
        "image": "python:3.11",
        "command": "python -c 'print(\"Hello\")'",
        "env": {"KEY": "value"},
        "volumes": {"/host/path": "/container/path"},
        "resources": {"cpu": "1.0", "memory": "512m"}
    }
}
```

**Features:**
- Custom Docker images
- Environment variables
- Volume mounts
- Resource limits (CPU, memory)
- Automatic container cleanup

### gRPC Executor

Call gRPC services and microservices.

**Installation:**
```bash
pip install aipartnerupflow[grpc]
```

**Usage:**
```python
{
    "schemas": {
        "method": "grpc_executor"
    },
    "inputs": {
        "server": "localhost:50051",
        "service": "Greeter",
        "method": "SayHello",
        "request": {"name": "World"},
        "timeout": 30.0
    }
}
```

**Features:**
- Dynamic proto loading support
- Custom metadata
- Timeout handling
- Error handling

### WebSocket Executor

Bidirectional WebSocket communication.

**Installation:**
```bash
# websockets is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "websocket_executor"
    },
    "inputs": {
        "url": "ws://example.com/ws",
        "message": "Hello",
        "wait_response": true,
        "timeout": 30.0
    }
}
```

**Features:**
- Send and receive messages
- JSON message support
- Configurable response waiting
- Connection timeout handling

### aipartnerupflow API Executor

Call other aipartnerupflow API instances for distributed execution.

**Installation:**
```bash
# httpx is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "apflow_api_executor"
    },
    "inputs": {
        "base_url": "http://remote-instance:8000",
        "method": "tasks.execute",
        "params": {"task_id": "task-123"},
        "auth_token": "eyJ...",
        "wait_for_completion": true
    }
}
```

**Features:**
- All task management methods (tasks.execute, tasks.create, tasks.get, etc.)
- JWT authentication support
- Task completion polling
- Streaming support
- Distributed execution scenarios

**Use Cases:**
- Distributed task execution across multiple instances
- Service orchestration
- Load balancing
- Cross-environment task execution

### MCP (Model Context Protocol) Executor

Interact with MCP servers to access external tools and data sources through the standardized MCP protocol.

**Installation:**
```bash
# MCP executor uses standard library for stdio mode
# For HTTP mode, httpx is included in a2a extra
pip install aipartnerupflow[a2a]  # For HTTP transport
# Or just use stdio mode (no additional dependencies)
```

**Transport Modes:**

1. **stdio** - Local process communication (no dependencies)
2. **http** - Remote server communication (requires httpx from [a2a] extra)

**Operations:**
- `list_tools`: List available MCP tools
- `call_tool`: Call a tool with arguments
- `list_resources`: List available resources
- `read_resource`: Read a resource by URI

**Usage Examples:**

**stdio Transport - List Tools:**
```python
{
    "schemas": {
        "method": "mcp_executor"
    },
    "inputs": {
        "transport": "stdio",
        "command": ["python", "-m", "mcp_server"],
        "operation": "list_tools"
    }
}
```

**stdio Transport - Call Tool:**
```python
{
    "schemas": {
        "method": "mcp_executor"
    },
    "inputs": {
        "transport": "stdio",
        "command": ["python", "-m", "mcp_server"],
        "operation": "call_tool",
        "tool_name": "search_web",
        "arguments": {
            "query": "Python async programming"
        }
    }
}
```

**stdio Transport - Read Resource:**
```python
{
    "schemas": {
        "method": "mcp_executor"
    },
    "inputs": {
        "transport": "stdio",
        "command": ["python", "-m", "mcp_server"],
        "operation": "read_resource",
        "resource_uri": "file:///path/to/file.txt"
    }
}
```

**HTTP Transport - List Tools:**
```python
{
    "schemas": {
        "method": "mcp_executor"
    },
    "inputs": {
        "transport": "http",
        "url": "http://localhost:8000/mcp",
        "operation": "list_tools",
        "headers": {
            "Authorization": "Bearer token"
        }
    }
}
```

**HTTP Transport - Call Tool:**
```python
{
    "schemas": {
        "method": "mcp_executor"
    },
    "inputs": {
        "transport": "http",
        "url": "http://localhost:8000/mcp",
        "operation": "call_tool",
        "tool_name": "search_web",
        "arguments": {
            "query": "Python async"
        },
        "timeout": 30.0
    }
}
```

**Configuration Options:**
- `transport`: "stdio" or "http" (required)
- `operation`: "list_tools", "call_tool", "list_resources", "read_resource" (required)
- For stdio:
  - `command`: List of strings for MCP server command (required)
  - `env`: Optional environment variables dict
  - `cwd`: Optional working directory
- For http:
  - `url`: MCP server URL (required)
  - `headers`: Optional HTTP headers dict
- For call_tool:
  - `tool_name`: Tool name (required)
  - `arguments`: Tool arguments dict (required)
- For read_resource:
  - `resource_uri`: Resource URI (required)
- `timeout`: Operation timeout in seconds (default: 30.0)

**Features:**
- Support for stdio and HTTP transport modes
- JSON-RPC 2.0 protocol compliance
- Tool and resource access
- Environment variable injection (stdio)
- Custom headers (HTTP)
- Timeout and cancellation support
- Comprehensive error handling

**Use Cases:**
- Access external tools via MCP servers
- Read data from MCP resources
- Integrate with MCP-compatible services
- Local and remote MCP server communication

### LLM Executor (`llm_executor`)

Direct LLM interaction via LiteLLM, supporting over 100+ providers including OpenAI, Anthropic, Google Gemini, and many others.

**Installation:**
```bash
pip install aipartnerupflow[llm]
```

**Features:**
- **Unified Model Access**: Use a single interface to interact with any LLM provider.
- **Streaming Support**: Built-in support for real-time streaming results (SSE).
- **Auto-Config**: Automatically handles API keys from environment variables or project-level configuration.
- **LiteLLM Power**: Leverages LiteLLM for robust, production-ready LLM interactions.

**Usage:**
```python
# Create task using LLM executor
task = await task_manager.task_repository.create_task(
    name="llm_executor",
    user_id="user123",
    inputs={
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Explain quantum entanglement in one sentence."}
        ]
    }
)
```

**Input Schema:**
- `model`: (required) Model name (provider-prefixed if needed, e.g., `gpt-4o`, `claude-3-5-sonnet-20240620`)
- `messages`: (required) Array of message objects (role and content)
- `stream`: (optional) Enable streaming (default: false)
- `temperature`: (optional) Controls randomness (default: 1.0)
- `max_tokens`: (optional) Maximum generation length
- `api_base`: (optional) Custom API base URL
- `api_key`: (optional) Override API key (can be passed via `X-LLM-API-KEY` header in API)

### Task Tree Generator Executor

Generate valid task tree JSON arrays from natural language requirements using LLM.

**Installation:**
```bash
# Install LLM provider package (choose one)
pip install openai
# or
pip install anthropic
```

**Usage:**
```python
{
    "schemas": {
        "method": "generate_executor"
    },
    "inputs": {
        "requirement": "Fetch data from API, process it, and save to database",
        "user_id": "user123",
        "llm_provider": "openai",  # Optional: "openai" or "anthropic"
        "model": "gpt-4",  # Optional: model name
        "temperature": 0.7,  # Optional: LLM temperature
        "max_tokens": 4000  # Optional: maximum tokens
    }
}
```

**Features:**
- Automatically collects available executors and their schemas
- Loads framework documentation as LLM context
- Generates valid task trees compatible with `TaskCreator.create_task_tree_from_array()`
- Comprehensive validation ensures generated tasks meet all requirements
- Supports OpenAI and Anthropic LLM providers
- Configurable via environment variables or input parameters

**Configuration:**
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: LLM API key (environment variable)
- `AIPARTNERUPFLOW_LLM_PROVIDER`: Provider selection (default: "openai")
- `AIPARTNERUPFLOW_LLM_MODEL`: Model name (optional)

**Output:**
Returns a JSON array of task objects that can be used with `TaskCreator.create_task_tree_from_array()`:
```python
{
    "status": "completed",
    "tasks": [
        {
            "name": "rest_executor",
            "inputs": {"url": "https://api.example.com/data", "method": "GET"},
            "priority": 1
        },
        {
            "name": "command_executor",
            "parent_id": "task_1",
            "dependencies": [{"id": "task_1", "required": True}],
            "inputs": {"command": "python process_data.py"},
            "priority": 2
        }
    ],
    "count": 2
}
```

**Use Cases:**
- Automatically generate task trees from natural language requirements
- Rapid prototyping of workflows
- Converting business requirements into executable task structures
- Learning tool for understanding task tree patterns

**CLI Usage Examples:**

The following examples demonstrate the intelligent task tree generation capabilities:

```bash
# 1. Parallel Workflow - Fetch from multiple APIs in parallel
apflow generate task-tree "Fetch data from two different APIs in parallel, then merge the results and save to database"

# 2. ETL Pipeline - Extract, Transform, Load workflow
apflow generate task-tree "Extract data from REST API, transform it by filtering and aggregating, then load it into database"

# 3. Multi-Source Data Collection - Parallel system monitoring
apflow generate task-tree "Collect system information about CPU and memory in parallel, analyze the data, and aggregate results"

# 4. Complex Processing Flow - Multi-step data processing
apflow generate task-tree "Call REST API to get user data, process response with Python script, validate processed data, and save to file"

# 5. Fan-Out Fan-In Pattern - Parallel processing with convergence
apflow generate task-tree "Fetch data from API, process it in two different ways in parallel (filter and aggregate), merge both results, and save to database"

# 6. Complete Business Scenario - Real-world monitoring workflow
apflow generate task-tree "Monitor system resources (CPU, memory, disk) in parallel, analyze metrics, generate report, and send notification if threshold exceeded"

# 7. Data Pipeline - Multi-source processing
apflow generate task-tree "Download data from multiple sources simultaneously, transform each dataset independently, then combine all results into single output file"

# 8. Hierarchical Processing - Category-based organization
apflow generate task-tree "Fetch data from API, organize into categories, process each category in parallel, then aggregate all category results"

# 9. Complex Workflow - Complete business process
apflow generate task-tree "Fetch customer data from API, validate information, process orders in parallel for each customer, aggregate results, calculate totals, and generate final report"

# 10. With custom LLM parameters
apflow generate task-tree "Create a workflow" --temperature 0.9 --max-tokens 6000 --provider openai --model gpt-4o

# 11. Save to database
apflow generate task-tree "My requirement" --save --user-id user123
```

**Tips for Better Results:**
- **Be specific**: More detailed requirements lead to better task trees
- **Mention patterns**: Use words like "parallel", "sequential", "merge", "aggregate" to guide generation
- **Specify executors**: Mention specific operations (API, database, file, command) for better executor selection
- **Describe flow**: Explain the data flow and execution order in your requirement
- **Save to file**: Use `--output tasks.json` to save generated tasks for later use

### Summary

All built-in executors follow the same pattern:
1. Inherit from `BaseTask`
2. Registered with `@executor_register()`
3. Support cancellation (where applicable)
4. Provide input schema validation
5. Return consistent result format

You can use these executors directly in your task schemas or extend them for custom behavior.

## Next Steps

- **[Task Orchestration Guide](task-orchestration.md)** - Learn how to orchestrate multiple tasks
- **[Basic Examples](../examples/basic_task.md)** - More practical examples
- **[Best Practices Guide](best-practices.md)** - Advanced techniques
- **[API Reference](../api/python.md)** - Complete API documentation

---

**Need help?** Check the [FAQ](faq.md) or [Quick Start Guide](../getting-started/quick-start.md)
