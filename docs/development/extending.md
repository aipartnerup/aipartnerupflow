# Extending aipartnerupflow

This guide explains how to extend aipartnerupflow by creating custom executors, extensions, tools, and hooks.

## Overview

aipartnerupflow is designed to be extensible. You can create:

1. **Custom Executors**: Task execution implementations
2. **Custom Extensions**: Storage, hooks, and other extension types
3. **Custom Tools**: Reusable tools for executors
4. **Custom Hooks**: Pre/post execution hooks
5. **CLI Extensions**: Additional subcommands for the `apflow` CLI

## Creating a Custom Executor

### Method 1: Implement ExecutableTask Directly

For maximum flexibility:

```python
from aipartnerupflow import ExecutableTask
from typing import Dict, Any

class MyCustomExecutor(ExecutableTask):
    """Custom executor implementation"""
    
    id = "my_custom_executor"
    name = "My Custom Executor"
    description = "Executes custom business logic"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        # Your execution logic here
        result = {
            "status": "completed",
            "data": inputs.get("data")
        }
        return result
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Input data"
                }
            },
            "required": ["data"]
        }
    
    async def cancel(self) -> Dict[str, Any]:
        """Optional: Implement cancellation support"""
        return {
            "status": "cancelled",
            "message": "Task cancelled"
        }
```

### Method 2: Inherit from BaseTask

For common functionality:

```python
from aipartnerupflow import BaseTask
from typing import Dict, Any
from pydantic import BaseModel

# Define input schema using Pydantic
class MyTaskInputs(BaseModel):
    data: str
    count: int = 10

class MyCustomExecutor(BaseTask):
    """Custom executor using BaseTask"""
    
    id = "my_custom_executor"
    name = "My Custom Executor"
    description = "Executes custom business logic"
    
    # Use Pydantic model for input validation
    inputs_schema = MyTaskInputs
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        # Inputs are automatically validated against inputs_schema
        data = inputs["data"]
        count = inputs["count"]
        
        # Your execution logic
        result = {
            "status": "completed",
            "processed_items": count,
            "data": data
        }
        
        # Check for cancellation (if supported)
        if self.cancellation_checker and self.cancellation_checker():
            return {
                "status": "cancelled",
                "message": "Task was cancelled"
            }
        
        return result
```

### Registering Your Executor

```python
from aipartnerupflow import executor_register

# Register the executor
executor_register(MyCustomExecutor())

# Or register with custom ID
executor_register(MyCustomExecutor(), executor_id="custom_id")
```

## Creating Custom Extensions

### Extension Categories

Extensions are categorized by `ExtensionCategory`:

- `EXECUTOR`: Task executors (implement `ExecutableTask`)
- `STORAGE`: Storage backends
- `HOOK`: Pre/post execution hooks
- `TOOL`: Reusable tools

### Example: Custom Storage Extension

```python
from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.extensions.storage import StorageExtension

class MyCustomStorage(StorageExtension):
    """Custom storage implementation"""
    
    id = "my_custom_storage"
    name = "My Custom Storage"
    category = ExtensionCategory.STORAGE
    
    async def save_task(self, task):
        """Save task to storage"""
        # Your storage logic
        pass
    
    async def get_task(self, task_id):
        """Retrieve task from storage"""
        # Your retrieval logic
        pass
```

### Registering Extensions

```python
from aipartnerupflow import storage_register

storage_register(MyCustomStorage())
```

## Creating Custom Tools

Tools are reusable utilities that can be used by executors:

```python
from aipartnerupflow.core.tools.base import Tool
from typing import Dict, Any

class MyCustomTool(Tool):
    """Custom tool implementation"""
    
    id = "my_custom_tool"
    name = "My Custom Tool"
    description = "Performs a specific operation"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool"""
        # Tool logic
        return {"result": "tool_output"}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
```

**Registering:**
```python
from aipartnerupflow import tool_register

tool_register(MyCustomTool())
```

## Creating Custom Hooks

Hooks allow you to modify task behavior before and after execution.

### Pre-Execution Hooks

Modify task inputs before execution:

```python
from aipartnerupflow import register_pre_hook

@register_pre_hook
async def validate_and_transform(task):
    """Validate and transform task inputs"""
    if task.inputs and "url" in task.inputs:
        url = task.inputs["url"]
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            task.inputs["url"] = f"https://{url}"
    
    # Add timestamp
    task.inputs["_processed_at"] = datetime.now().isoformat()
```

### Post-Execution Hooks

Process results after execution:

```python
from aipartnerupflow import register_post_hook

@register_post_hook
async def log_and_notify(task, inputs, result):
    """Log execution and send notification"""
    logger.info(f"Task {task.id} completed")
    logger.info(f"Inputs: {inputs}")
    logger.info(f"Result: {result}")
    
    # Send notification (example)
    if result.get("status") == "failed":
        send_alert(f"Task {task.id} failed: {result.get('error')}")
```

## Using Custom TaskModel

Extend TaskModel to add custom fields:

```python
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from sqlalchemy import Column, String, Integer
from aipartnerupflow import set_task_model_class

class ProjectTaskModel(TaskModel):
    """Custom TaskModel with project and department fields"""
    __tablename__ = "apflow_tasks"
    
    project_id = Column(String(255), nullable=True, index=True)
    department = Column(String(100), nullable=True)
    priority_level = Column(Integer, default=2)

# Set custom model (must be called before creating tasks)
set_task_model_class(ProjectTaskModel)

# Now you can use custom fields
task = await task_manager.task_repository.create_task(
    name="my_task",
    user_id="user123",
    project_id="proj-123",  # Custom field
    department="engineering",  # Custom field
    priority_level=1,  # Custom field
    inputs={...}
)
```

## Advanced: Cancellation Support

Implement cancellation for long-running tasks:

```python
class CancellableExecutor(ExecutableTask):
    """Executor with cancellation support"""
    
    id = "cancellable_executor"
    name = "Cancellable Executor"
    description = "Supports cancellation during execution"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with cancellation checks"""
        # TaskManager sets cancellation_checker if executor supports it
        cancellation_checker = getattr(self, 'cancellation_checker', None)
        
        for i in range(100):
            # Check for cancellation
            if cancellation_checker and cancellation_checker():
                return {
                    "status": "cancelled",
                    "message": "Task was cancelled",
                    "progress": i / 100
                }
            
            # Do work
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "progress": 1.0}
    
    async def cancel(self) -> Dict[str, Any]:
        """Handle cancellation request"""
        # Cleanup logic here
        return {
            "status": "cancelled",
            "message": "Cancellation requested"
        }

## Creating CLI Extensions

CLI extensions allow you to register new subcommand groups to the `apflow` CLI using Python's `entry_points` mechanism.

### 1. Create your Command Group

Inherit from `CLIExtension` to ensure consistent UI defaults (like showing help when no arguments are provided).

```python
from aipartnerupflow.cli import CLIExtension

# Create the command group
users_app = CLIExtension(help="Manage and analyze users")

@users_app.command()
def stat():
    """Display user statistics"""
    print("User Statistics: ...")

@users_app.command()
def list():
    """List all users"""
    print("User list...")
```

### 2. Register in `pyproject.toml`

Register your command group under the `aipartnerupflow.cli_plugins` group in your project's `pyproject.toml`.

```toml
[project.entry-points."aipartnerupflow.cli_plugins"]
users = "your_package.cli:users_app"
```

- The entry point **key** (`users`) will be the name of the subcommand cluster.
- The **value** points to the `CLIExtension` (or `typer.Typer`) instance.

### 3. Usage

After installing your package in the same environment as `aipartnerupflow`, the command will be available automatically:

```bash
apflow users stat
```

### Supported Plugin Types

Discovery supports two types of plugin objects:
1. **`typer.Typer` (or `CLIExtension`)**: Registered as a **subcommand group** (e.g., `apflow users <cmd>`).
2. **`Callable` (function)**: Registered as a **single command** (e.g., `apflow run-once`).
```

## Advanced: Streaming Support

Send real-time progress updates:

```python
class StreamingExecutor(ExecutableTask):
    """Executor with streaming support"""
    
    id = "streaming_executor"
    name = "Streaming Executor"
    description = "Sends real-time progress updates"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with streaming"""
        # Access event queue (set by TaskManager)
        event_queue = getattr(self, 'event_queue', None)
        
        total_steps = 10
        for step in range(total_steps):
            # Send progress update
            if event_queue:
                await event_queue.put({
                    "type": "progress",
                    "task_id": getattr(self, 'task_id', None),
                    "data": {
                        "step": step + 1,
                        "total": total_steps,
                        "progress": (step + 1) / total_steps
                    }
                })
            
            # Do work
            await asyncio.sleep(0.5)
        
        return {"status": "completed", "steps": total_steps}
```

## Best Practices

### 1. Input Validation

Always validate inputs:

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "required_field": {
                "type": "string",
                "description": "Required field"
            },
            "optional_field": {
                "type": "integer",
                "description": "Optional field",
                "default": 0
            }
        },
        "required": ["required_field"]
    }
```

### 2. Error Handling

Return structured error responses:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Your logic
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

### 3. Resource Cleanup

Clean up resources properly:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    resource = None
    try:
        resource = acquire_resource()
        # Use resource
        return {"status": "completed"}
    finally:
        if resource:
            resource.cleanup()
```

### 4. Async Best Practices

Use async/await properly:

```python
# Good: Use async I/O
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    return {"data": data}

# Avoid: Blocking operations
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Bad: Blocking I/O
    response = requests.get(url)  # Don't do this
    return {"data": response.json()}
```

## Testing Your Extensions

### Unit Testing

```python
import pytest
from aipartnerupflow import executor_register, TaskManager, create_session

@pytest.fixture
def executor():
    return MyCustomExecutor()

@pytest.fixture
def task_manager():
    executor_register(MyCustomExecutor())
    db = create_session()
    return TaskManager(db)

@pytest.mark.asyncio
async def test_executor_execution(executor, task_manager):
    """Test executor execution"""
    task = await task_manager.task_repository.create_task(
        name="my_custom_executor",
        user_id="test_user",
        inputs={"data": "test"}
    )
    
    from aipartnerupflow.core.types import TaskTreeNode
    task_tree = TaskTreeNode(task)
    result = await task_manager.distribute_task_tree(task_tree)
    
    assert result["status"] == "completed"
```

## See Also

- [Architecture Documentation](../architecture/architecture.md)
- [Extension Registry Design](../architecture/extension-registry-design.md)
- [Examples](../examples/basic_task.md)
- [Development Guide](development.md)

