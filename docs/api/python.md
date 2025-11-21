# Core API Reference

This document provides a complete reference for aipartnerupflow's core APIs.

## Overview

The core API consists of:
- **TaskManager**: Task orchestration and execution
- **ExecutableTask**: Interface for all task executors
- **TaskTreeNode**: Task tree structure
- **TaskRepository**: Database operations
- **TaskCreator**: Task tree creation from arrays

## TaskManager

The main class for orchestrating and executing task trees.

### Initialization

```python
from aipartnerupflow import TaskManager, create_session

db = create_session()
task_manager = TaskManager(
    db,
    root_task_id=None,              # Optional: Root task ID for streaming
    pre_hooks=None,                 # Optional: List of pre-execution hooks
    post_hooks=None,                # Optional: List of post-execution hooks
    executor_instances=None         # Optional: Shared executor instances dict
)
```

**Parameters**:
- `db` (Session | AsyncSession): Database session
- `root_task_id` (str, optional): Root task ID for streaming callbacks
- `pre_hooks` (List[TaskPreHook], optional): Pre-execution hook functions
- `post_hooks` (List[TaskPostHook], optional): Post-execution hook functions
- `executor_instances` (Dict[str, Any], optional): Shared executor instances for cancellation

### Methods

#### `distribute_task_tree(task_tree, use_callback=True)`

Execute a task tree with proper dependency management and priority scheduling.

```python
result = await task_manager.distribute_task_tree(
    task_tree: TaskTreeNode,
    use_callback: bool = True
) -> TaskTreeNode
```

**Parameters**:
- `task_tree` (TaskTreeNode): Root task tree node
- `use_callback` (bool): Whether to use callbacks (default: True)

**Returns**: TaskTreeNode with execution results

**Example**:
```python
task_tree = TaskTreeNode(root_task)
task_tree.add_child(TaskTreeNode(child_task))
result = await task_manager.distribute_task_tree(task_tree)
```

#### `distribute_task_tree_with_streaming(task_tree, use_callback=True)`

Execute a task tree with real-time streaming for progress updates.

```python
await task_manager.distribute_task_tree_with_streaming(
    task_tree: TaskTreeNode,
    use_callback: bool = True
) -> None
```

**Parameters**:
- `task_tree` (TaskTreeNode): Root task tree node
- `use_callback` (bool): Whether to use callbacks (default: True)

**Note**: Requires streaming callbacks to be configured.

#### `cancel_task(task_id, error_message=None)`

Cancel a running task execution.

```python
result = await task_manager.cancel_task(
    task_id: str,
    error_message: str | None = None
) -> Dict[str, Any]
```

**Parameters**:
- `task_id` (str): Task ID to cancel
- `error_message` (str, optional): Optional error message

**Returns**: Dictionary with cancellation result

**Example**:
```python
result = await task_manager.cancel_task("task_123", "User requested cancellation")
```

### Properties

- `task_repository` (TaskRepository): Access to task repository for database operations
- `streaming_callbacks` (StreamingCallbacks): Streaming callbacks instance

## ExecutableTask

Abstract base class for all task executors.

### Interface

```python
from aipartnerupflow import ExecutableTask
from typing import Dict, Any

class MyTask(ExecutableTask):
    @property
    def id(self) -> str:
        """Unique identifier"""
        return "my_task"
    
    @property
    def name(self) -> str:
        """Display name"""
        return "My Task"
    
    @property
    def description(self) -> str:
        """Description"""
        return "Task description"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task logic"""
        return {"status": "completed", "result": "..."}
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for inputs"""
        return {
            "type": "object",
            "properties": {...}
        }
    
    async def cancel(self) -> Dict[str, Any]:
        """Optional: Cancel execution"""
        return {"status": "cancelled"}
```

### Required Methods

#### `id` (property)

Unique identifier for the task. Used for registration and references.

#### `name` (property)

Human-readable name for the task.

#### `description` (property)

Description of what the task does.

#### `execute(inputs)`

Main execution logic. Must be async.

**Parameters**:
- `inputs` (Dict[str, Any]): Input parameters

**Returns**: Dict[str, Any] with execution result

#### `get_input_schema()`

Return JSON Schema defining input parameters.

**Returns**: Dict[str, Any] with JSON Schema

### Optional Methods

#### `cancel()`

Cancel task execution (optional). Implement if task supports cancellation.

**Returns**: Dict[str, Any] with cancellation result

## TaskTreeNode

Represents a node in a task tree structure.

### Initialization

```python
from aipartnerupflow.core.types import TaskTreeNode

node = TaskTreeNode(task: TaskModel)
```

**Parameters**:
- `task` (TaskModel): The task model instance

### Methods

#### `add_child(child)`

Add a child node to this node.

```python
node.add_child(child: TaskTreeNode) -> None
```

**Parameters**:
- `child` (TaskTreeNode): Child node to add

**Example**:
```python
root = TaskTreeNode(root_task)
child = TaskTreeNode(child_task)
root.add_child(child)
```

#### `calculate_progress()`

Calculate progress of the task tree.

```python
progress = node.calculate_progress() -> float
```

**Returns**: Average progress (0.0 to 1.0)

#### `calculate_status()`

Calculate overall status of the task tree.

```python
status = node.calculate_status() -> str
```

**Returns**: Status string ("completed", "failed", "in_progress", or "pending")

### Properties

- `task` (TaskModel): The task model instance
- `children` (List[TaskTreeNode]): List of child nodes

## TaskRepository

Database operations for tasks.

### Initialization

```python
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository

repository = TaskRepository(
    db: Session | AsyncSession,
    task_model_class: Type[TaskModel] = TaskModel
)
```

### Methods

#### `create_task(...)`

Create a new task in the database.

```python
task = await repository.create_task(
    name: str,
    user_id: str,
    parent_id: str | None = None,
    priority: int = 2,
    dependencies: List[Dict[str, Any]] | None = None,
    inputs: Dict[str, Any] | None = None,
    schemas: Dict[str, Any] | None = None,
    status: str = "pending",
    **kwargs
) -> TaskModel
```

**Parameters**:
- `name` (str): Task name (executor identifier)
- `user_id` (str): User ID
- `parent_id` (str, optional): Parent task ID
- `priority` (int): Priority level (default: 2)
- `dependencies` (List[Dict], optional): Task dependencies
- `inputs` (Dict, optional): Input parameters
- `schemas` (Dict, optional): Task schemas
- `status` (str): Initial status (default: "pending")

**Returns**: Created TaskModel instance

#### `get_task_by_id(task_id)`

Get a task by its ID.

```python
task = await repository.get_task_by_id(task_id: str) -> TaskModel | None
```

#### `get_root_task(task)`

Get the root task for a given task.

```python
root = await repository.get_root_task(task: TaskModel) -> TaskModel
```

#### `build_task_tree(task)`

Build a task tree starting from a task.

```python
tree = await repository.build_task_tree(task: TaskModel) -> TaskTreeNode
```

## TaskCreator

Create task trees from task arrays.

### Initialization

```python
from aipartnerupflow.core.execution.task_creator import TaskCreator

creator = TaskCreator(db: Session | AsyncSession)
```

### Methods

#### `create_task_tree_from_array(tasks)`

Create a task tree from an array of task dictionaries.

```python
tree = await creator.create_task_tree_from_array(
    tasks: List[Dict[str, Any]]
) -> TaskTreeNode
```

**Parameters**:
- `tasks` (List[Dict]): Array of task dictionaries

**Task Dictionary Format**:
```python
{
    "id": "task_1",                    # Optional: Task ID
    "name": "Task 1",                  # Required: Task name
    "user_id": "user_123",             # Required: User ID
    "parent_id": "parent_task_id",     # Optional: Parent task ID
    "priority": 1,                     # Optional: Priority (default: 2)
    "dependencies": [                 # Optional: Dependencies
        {"id": "task_0", "required": True}
    ],
    "inputs": {"key": "value"},        # Optional: Input parameters
    "schemas": {...}                   # Optional: Task schemas
}
```

**Returns**: TaskTreeNode root node

**Example**:
```python
tasks = [
    {
        "id": "task_1",
        "name": "task1",
        "user_id": "user123",
        "priority": 1
    },
    {
        "id": "task_2",
        "name": "task2",
        "user_id": "user123",
        "parent_id": "task_1",
        "dependencies": [{"id": "task_1", "required": True}]
    }
]
tree = await creator.create_task_tree_from_array(tasks)
```

**Validation**:
- Detects circular dependencies using DFS algorithm
- Ensures all tasks form a single task tree (exactly one root task)
- Verifies all tasks are reachable from root task via parent_id chain
- Validates that all dependent tasks are included in the input array

#### `create_task_copy(original_task)`

Create a copy of an existing task tree for re-execution.

This method creates a new executable copy of a task tree, including:
- The original task and all its children
- All tasks that depend on the original task (including transitive dependencies)
- Automatically handles failed leaf nodes (filters out pending dependents)

**Parameters**:
- `original_task` (TaskModel): The task to copy (can be root or any task in tree)

**Returns**: `TaskTreeNode` - New task tree with copied tasks

**Example**:
```python
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel

# Get original task
original_task = await task_repository.get_task_by_id("task-123")

# Create copy
task_creator = TaskCreator(db_session)
new_tree = await task_creator.create_task_copy(original_task)

# Execute the copied task tree
result = await task_manager.distribute_task_tree(new_tree)
```

**What gets copied**:
- Task structure (parent-child relationships)
- Task definitions (name, code, inputs, schemas, params, dependencies)
- All dependent tasks (direct and transitive)
- Minimal subtree containing only required tasks

**What gets reset**:
- Task IDs (new IDs generated)
- Status (reset to "pending")
- Progress (reset to 0.0)
- Result (reset to None)
- Error (reset to None)
- Execution timestamps (started_at, completed_at)
- Token usage counters (token_success, token_failed)

**What gets preserved**:
- Task definitions (name, code, inputs, schemas, params)
- User and product associations (user_id, product_id)
- Priority settings
- Dependencies structure

**Metadata**:
- `original_task_id`: Links copied task to original task's root ID
- `has_copy`: Set to `true` on all original tasks that were copied

## TaskModel

Database model for tasks.

### Fields

- `id` (str): Task ID (primary key)
- `parent_id` (str, optional): Parent task ID
- `user_id` (str, optional): User ID
- `name` (str): Task name
- `status` (str): Task status
- `priority` (int): Priority level
- `dependencies` (JSON): Task dependencies
- `inputs` (JSON): Input parameters
- `params` (JSON): Executor parameters
- `result` (JSON): Execution result
- `error` (str, optional): Error message
- `schemas` (JSON): Task schemas
- `progress` (Decimal): Progress (0.0 to 1.0)
- `has_children` (bool): Whether task has children
- `created_at` (DateTime): Creation timestamp
- `started_at` (DateTime, optional): Start timestamp
- `updated_at` (DateTime): Update timestamp
- `completed_at` (DateTime, optional): Completion timestamp
- `original_task_id` (str, optional): ID of original task (for copied tasks)
- `has_copy` (bool): Whether this task has been copied (default: False)

### Methods

#### `to_dict()`

Convert model to dictionary.

```python
data = task.to_dict() -> Dict[str, Any]
```

## TaskStatus

Task status constants.

### Constants

- `TaskStatus.PENDING = "pending"`
- `TaskStatus.IN_PROGRESS = "in_progress"`
- `TaskStatus.COMPLETED = "completed"`
- `TaskStatus.FAILED = "failed"`
- `TaskStatus.CANCELLED = "cancelled"`

### Methods

#### `is_terminal(status)`

Check if status is terminal.

```python
is_terminal = TaskStatus.is_terminal(status: str) -> bool
```

#### `is_active(status)`

Check if status is active.

```python
is_active = TaskStatus.is_active(status: str) -> bool
```

## Utility Functions

### Session Management

#### `create_session()`

Create a new database session.

```python
from aipartnerupflow import create_session

db = create_session() -> Session
```

#### `get_default_session()`

Get the default database session.

```python
from aipartnerupflow import get_default_session

db = get_default_session() -> Session
```

### Extension Registry

#### Registering Executors

Register an executor with the extension registry.

**Using decorator (recommended):**
```python
from aipartnerupflow import executor_register, BaseTask

@executor_register()
class MyExecutor(BaseTask):
    id = "my_executor"
    # ...
```

The decorator automatically registers the executor when the class is defined. Simply import the class to make it available.

**Note:** For executors that need runtime configuration, you can register instances directly using `get_registry().register(instance)`, but using the decorator is the recommended approach.

#### `register_pre_hook(hook)`

Register a pre-execution hook.

```python
from aipartnerupflow import register_pre_hook

@register_pre_hook
async def my_pre_hook(task: TaskModel):
    # Modify task.inputs if needed
    pass
```

#### `register_post_hook(hook)`

Register a post-execution hook.

```python
from aipartnerupflow import register_post_hook

@register_post_hook
async def my_post_hook(task: TaskModel, inputs: Dict[str, Any], result: Any):
    # Process result
    pass
```

## Type Definitions

### TaskPreHook

Type alias for pre-execution hook functions.

```python
TaskPreHook = Callable[[TaskModel], Union[None, Awaitable[None]]]
```

### TaskPostHook

Type alias for post-execution hook functions.

```python
TaskPostHook = Callable[[TaskModel, Dict[str, Any], Any], Union[None, Awaitable[None]]]
```

## Error Handling

### Common Exceptions

- `ValueError`: Invalid input parameters
- `RuntimeError`: Execution errors
- `KeyError`: Missing required fields

### Error Response Format

Tasks that fail return:

```python
{
    "status": "failed",
    "error": "Error message",
    "error_type": "ExceptionType"
}
```

## Examples

### Basic Usage

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

db = create_session()
task_manager = TaskManager(db)

# Create task
task = await task_manager.task_repository.create_task(
    name="my_task",
    user_id="user123",
    inputs={"key": "value"}
)

# Build tree
tree = TaskTreeNode(task)

# Execute
result = await task_manager.distribute_task_tree(tree)
```

### With Dependencies

```python
# Create tasks
task1 = await task_manager.task_repository.create_task(
    name="task1",
    user_id="user123"
)

task2 = await task_manager.task_repository.create_task(
    name="task2",
    user_id="user123",
    parent_id=task1.id,
    dependencies=[{"id": task1.id, "required": True}]
)

# Build tree
tree = TaskTreeNode(task1)
tree.add_child(TaskTreeNode(task2))

# Execute
await task_manager.distribute_task_tree(tree)
```

## A2A Protocol Integration

aipartnerupflow implements the A2A (Agent-to-Agent) Protocol standard, allowing seamless integration with other A2A-compatible agents and services.

### Using A2A Client SDK

The A2A protocol provides an official client SDK for easy integration. Here's how to use it with aipartnerupflow:

#### Installation

```bash
pip install a2a
```

#### Basic Example

```python
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard
import httpx
import uuid
import asyncio

async def execute_task_via_a2a():
    # Create HTTP client
    httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")
    
    # Create A2A client config
    config = ClientConfig(
        streaming=True,
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
    
    # Send message and process responses
    async for response in client.send_message(message):
        if isinstance(response, Message):
            for part in response.parts:
                if part.kind == "data" and isinstance(part.data, dict):
                    result = part.data
                    print(f"Status: {result.get('status')}")
                    print(f"Progress: {result.get('progress')}")
    
    await httpx_client.aclose()

# Run
asyncio.run(execute_task_via_a2a())
```

### Push Notification Configuration

You can use push notifications to receive task execution updates via callback URL:

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
async for response in client.send_message(message):
    # Initial response only
    print(f"Initial response: {response}")
    break
```

The server will send task status updates to your callback URL as the task executes.

### Streaming Mode

Enable streaming mode to receive real-time progress updates:

```python
# Create message with streaming enabled via metadata
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part],
    metadata={"stream": True}
)

# Send message - will receive multiple updates
async for response in client.send_message(message):
    if isinstance(response, Message):
        # Process streaming updates
        for part in response.parts:
            if part.kind == "data":
                update = part.data
                print(f"Update: {update}")
```

### Task Tree Execution

Execute complex task trees with dependencies:

```python
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

### A2A Protocol Documentation

For detailed information about the A2A Protocol, please refer to the official documentation:

- **A2A Protocol Official Documentation**: [https://www.a2aprotocol.org/en/docs](https://www.a2aprotocol.org/en/docs)
- **A2A Protocol Homepage**: [https://www.a2aprotocol.org](https://www.a2aprotocol.org)

## See Also

- [Task Orchestration Guide](../guides/task-orchestration.md)
- [Custom Tasks Guide](../guides/custom-tasks.md)
- [Architecture Documentation](../architecture/overview.md)
- [HTTP API Reference](./http.md)

