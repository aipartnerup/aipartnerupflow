# API Quick Reference

Quick reference cheat sheet for aipartnerupflow APIs. Perfect for when you know what you need but need the exact syntax.

## Table of Contents

1. [Core APIs](#core-apis)
2. [Task Management](#task-management)
3. [Custom Executors](#custom-executors)
4. [Task Orchestration](#task-orchestration)
5. [Hooks](#hooks)
6. [Storage](#storage)
7. [Common Patterns](#common-patterns)

## Core APIs

### Import Core Components

```python
from aipartnerupflow import (
    TaskManager,
    TaskTreeNode,
    create_session,
    BaseTask,
    executor_register
)
```

### Create Database Session

```python
# DuckDB (default, no setup needed)
db = create_session()

# PostgreSQL
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:password@localhost/dbname"
db = create_session()
```

### Create TaskManager

```python
db = create_session()
task_manager = TaskManager(db)
```

## Task Management

### Create Task

```python
task = await task_manager.task_repository.create_task(
    name="executor_id",           # Required: Executor ID
    user_id="user123",            # Required: User identifier
    parent_id=None,               # Optional: Parent task ID
    priority=2,                   # Optional: Priority (0-3, default: 2)
    dependencies=[],              # Optional: List of dependencies
    inputs={},                    # Optional: Input parameters
    schemas={},                   # Optional: Task schemas
    status="pending"              # Optional: Initial status
)
```

### Get Task by ID

```python
task = await task_manager.task_repository.get_task_by_id(task_id)
```

### Update Task

```python
# Update status and related fields
await task_repository.update_task_status(
    task_id,
    status="completed",
    result={"data": "result"},
    progress=1.0
)

# Update inputs
await task_repository.update_task_inputs(task_id, {"key": "new_value"})

# Update name
await task_repository.update_task_name(task_id, "New Task Name")

# Update priority
await task_repository.update_task_priority(task_id, 2)

# Update params
await task_repository.update_task_params(task_id, {"executor_id": "new_executor"})

# Update schemas
await task_repository.update_task_schemas(task_id, {"input_schema": {...}})

# Update dependencies (only for pending tasks, with validation)
await task_repository.update_task_dependencies(
    task_id,
    [{"id": "dep-task-id", "required": True}]
)
```

**Critical Field Validation:**
- `parent_id` and `user_id`: Cannot be updated (always rejected)
- `dependencies`: Can only be updated for `pending` tasks, with validation:
  - All dependency references must exist in the same task tree
  - No circular dependencies allowed
  - No dependent tasks can be executing
- Other fields: Can be updated freely from any status

### Delete Task

```python
await task_manager.task_repository.delete_task(task_id)
```

### List Tasks

```python
tasks = await task_manager.task_repository.list_tasks(
    user_id="user123",
    status="completed",
    limit=100
)
```

## Custom Executors

### Basic Executor Template

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class MyExecutor(BaseTask):
    id = "my_executor"
    name = "My Executor"
    description = "Does something"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Your logic here
        return {"status": "completed", "result": "..."}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"}
            },
            "required": ["param"]
        }
```

### Use Custom Executor

```python
# Import to register
from my_module import MyExecutor

# Use it
task = await task_manager.task_repository.create_task(
    name="my_executor",  # Must match executor id
    user_id="user123",
    inputs={"param": "value"}
)
```

### LLM Executor (`llm_executor`)

```python
# Create task using LLM executor
task = await task_manager.task_repository.create_task(
    name="llm_executor",
    user_id="user123",
    inputs={
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Explain AI."}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
)
```

## Task Orchestration

### Build Task Tree

```python
# Single task
task_tree = TaskTreeNode(task)

# Multiple tasks
root = TaskTreeNode(root_task)
root.add_child(TaskTreeNode(child_task1))
root.add_child(TaskTreeNode(child_task2))
```

### Execute Task Tree

```python
# Without streaming
result = await task_manager.distribute_task_tree(task_tree)

# With streaming
await task_manager.distribute_task_tree_with_streaming(
    task_tree,
    use_callback=True
)
```

### Dependencies

```python
# Required dependency
task2 = await task_manager.task_repository.create_task(
    name="task2",
    dependencies=[{"id": task1.id, "required": True}],
    ...
)

# Optional dependency
task2 = await task_manager.task_repository.create_task(
    name="task2",
    dependencies=[{"id": task1.id, "required": False}],
    ...
)

# Multiple dependencies
task3 = await task_manager.task_repository.create_task(
    name="task3",
    dependencies=[
        {"id": task1.id, "required": True},
        {"id": task2.id, "required": True}
    ],
    ...
)
```

### Priorities

```python
# Priority levels
URGENT = 0   # Highest priority
HIGH = 1
NORMAL = 2   # Default
LOW = 3      # Lowest priority

task = await task_manager.task_repository.create_task(
    name="task",
    priority=URGENT,
    ...
)
```

### Cancel Task

```python
result = await task_manager.cancel_task(
    task_id="task_123",
    error_message="User requested cancellation"
)
```

## Hooks

### Pre-Execution Hook

```python
from aipartnerupflow import register_pre_hook

@register_pre_hook
async def validate_inputs(task):
    """Validate inputs before execution"""
    if task.inputs and "url" in task.inputs:
        url = task.inputs["url"]
        if not url.startswith(("http://", "https://")):
            task.inputs["url"] = f"https://{url}"
```

### Post-Execution Hook

```python
from aipartnerupflow import register_post_hook

@register_post_hook
async def log_results(task, inputs, result):
    """Log results after execution"""
    print(f"Task {task.id} completed: {result}")
```

### Use Hooks with TaskManager

```python
from aipartnerupflow import TaskPreHook, TaskPostHook

pre_hooks = [validate_inputs]
post_hooks = [log_results]

task_manager = TaskManager(
    db,
    pre_hooks=pre_hooks,
    post_hooks=post_hooks
)
```

## Storage

### Custom TaskModel

```python
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow import set_task_model_class
from sqlalchemy import Column, String

class CustomTaskModel(TaskModel):
    __tablename__ = "apflow_tasks"
    project_id = Column(String(255), nullable=True, index=True)

# Set before creating tasks
set_task_model_class(CustomTaskModel)
```

## Common Patterns

### Pattern 1: Simple Task

```python
# Create task
task = await task_manager.task_repository.create_task(
    name="executor_id",
    user_id="user123",
    inputs={"key": "value"}
)

# Build tree
task_tree = TaskTreeNode(task)

# Execute
await task_manager.distribute_task_tree(task_tree)

# Get result
result = await task_manager.task_repository.get_task_by_id(task.id)
print(f"Result: {result.result}")
```

### Pattern 2: Sequential Tasks

```python
# Task 1
task1 = await task_manager.task_repository.create_task(
    name="task1",
    user_id="user123",
    priority=1
)

# Task 2 depends on Task 1
task2 = await task_manager.task_repository.create_task(
    name="task2",
    user_id="user123",
    parent_id=task1.id,
    dependencies=[{"id": task1.id, "required": True}],
    priority=2
)

# Build tree
root = TaskTreeNode(task1)
root.add_child(TaskTreeNode(task2))

# Execute (Task 2 waits for Task 1)
await task_manager.distribute_task_tree(root)
```

### Pattern 3: Parallel Tasks

```python
# Root task
root_task = await task_manager.task_repository.create_task(
    name="root",
    user_id="user123",
    priority=1
)

# Task 1 (no dependencies)
task1 = await task_manager.task_repository.create_task(
    name="task1",
    user_id="user123",
    parent_id=root_task.id,
    priority=2
)

# Task 2 (no dependencies, runs in parallel with Task 1)
task2 = await task_manager.task_repository.create_task(
    name="task2",
    user_id="user123",
    parent_id=root_task.id,
    priority=2
)

# Build tree
root = TaskTreeNode(root_task)
root.add_child(TaskTreeNode(task1))
root.add_child(TaskTreeNode(task2))

# Execute (both run in parallel)
await task_manager.distribute_task_tree(root)
```

### Pattern 4: Fan-In (Multiple Dependencies)

```python
# Task 1
task1 = await task_manager.task_repository.create_task(...)

# Task 2
task2 = await task_manager.task_repository.create_task(...)

# Task 3 depends on both
task3 = await task_manager.task_repository.create_task(
    name="task3",
    dependencies=[
        {"id": task1.id, "required": True},
        {"id": task2.id, "required": True}
    ],
    ...
)
```

### Pattern 5: Error Handling

```python
# Execute
await task_manager.distribute_task_tree(task_tree)

# Check status
task = await task_manager.task_repository.get_task_by_id(task_id)

if task.status == "failed":
    print(f"Error: {task.error}")
    # Handle error
elif task.status == "completed":
    print(f"Result: {task.result}")
```

### Pattern 6: Using TaskExecutor

```python
from aipartnerupflow.core.execution.task_executor import TaskExecutor

# Get singleton instance
executor = TaskExecutor()

# Execute tasks from definitions
tasks = [
    {
        "id": "task1",
        "name": "executor_id",
        "user_id": "user123",
        "inputs": {"key": "value"}
    }
]

result = await executor.execute_tasks(
    tasks=tasks,
    root_task_id="root_123",
    use_streaming=False
)
```

### Pattern 7: Generate Task Tree from Natural Language

**Python API Usage:**

```python
from aipartnerupflow import TaskManager, TaskCreator, create_session
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.extensions.generate import GenerateExecutor

db = create_session()
task_manager = TaskManager(db)

# Step 1: Generate task tree using generate_executor
generate_task = await task_manager.task_repository.create_task(
    name="generate_executor",
    user_id="user123",
    inputs={
        "requirement": "Fetch data from API, process it, and save to database",
        "user_id": "user123",
        "llm_provider": "openai",  # Optional
        "model": "gpt-4o"  # Optional
    }
)

# Step 2: Execute generate_executor
generate_tree = TaskTreeNode(generate_task)
await task_manager.distribute_task_tree(generate_tree)

# Step 3: Get generated tasks array
result = await task_manager.task_repository.get_task_by_id(generate_task.id)
generated_tasks = result.result["tasks"]

# Step 4: Create and execute the generated task tree
creator = TaskCreator(db)
final_task_tree = await creator.create_task_tree_from_array(generated_tasks)
await task_manager.distribute_task_tree(final_task_tree)
```

**JSON-RPC API Usage:**

```python
import requests

# Generate task tree via API
response = requests.post(
    "http://localhost:8000/tasks",
    json={
        "jsonrpc": "2.0",
        "method": "tasks.generate",
        "params": {
            "requirement": "Fetch data from API, process it, and save to database",
            "user_id": "user123",
            "save": True  # Automatically save to database
        },
        "id": "generate-1"
    }
)

result = response.json()["result"]
generated_tasks = result["tasks"]
root_task_id = result.get("root_task_id")  # Present if save=true

# If save=true, tasks are already saved and ready for execution
# If save=false, use TaskCreator.create_task_tree_from_array(generated_tasks)
```

**CLI Usage Examples:**

```bash
# Get task statistics by status from database
apflow tasks count

# List tasks from database (defaults to root tasks)
apflow tasks list --user-id user123

# Generate and preview task tree
apflow generate task-tree "Fetch data from API and process it"
```

# Complex processing flow
apflow generate task-tree "Call REST API to get user data, process response with Python script, validate processed data, and save to file"

# Fan-out fan-in pattern
apflow generate task-tree "Fetch data from API, process it in two different ways in parallel (filter and aggregate), merge both results, and save to database"

# Complete business scenario
apflow generate task-tree "Monitor system resources (CPU, memory, disk) in parallel, analyze metrics, generate report, and send notification if threshold exceeded"

# Save output to file
apflow generate task-tree "Your requirement" --output tasks.json

# Save to database
apflow generate task-tree "Your requirement" --save --user-id user123
```

**Tips for Better Generation:**
- Use specific keywords: "parallel", "sequential", "merge", "aggregate" help guide the generation
- Describe data flow: Explain how data moves between steps
- Mention executors: Specify operations like "API", "database", "file", "command" for better executor selection
- Be detailed: More context leads to more accurate task trees

## Extension Registry

### Get Registry

```python
from aipartnerupflow.core.extensions import get_registry

registry = get_registry()
```

### List Executors

```python
from aipartnerupflow.core.extensions import ExtensionCategory

executors = registry.list_by_category(ExtensionCategory.EXECUTOR)
for executor in executors:
    print(f"ID: {executor.id}, Name: {executor.name}")
```

### Get Executor by ID

```python
executor = registry.get_by_id("executor_id")
```

### Create Executor Instance

```python
executor_instance = registry.create_executor_instance(
    extension_id="executor_id",
    inputs={"key": "value"}
)
```

## CrewAI Integration

### Create Crew

```python
from aipartnerupflow.extensions.crewai import CrewManager
from aipartnerupflow.core.extensions import get_registry

crew = CrewManager(
    id="my_crew",
    name="My Crew",
    description="Does AI analysis",
    agents=[
        {
            "role": "Analyst",
            "goal": "Analyze data",
            "backstory": "You are an expert analyst"
        }
    ],
    tasks=[
        {
            "description": "Analyze: {text}",
            "agent": "Analyst"
        }
    ]
)

# Register
get_registry().register(crew)
```

### Use Crew

```python
task = await task_manager.task_repository.create_task(
    name="my_crew",
    user_id="user123",
    inputs={"text": "Analyze this data"}
)
```

## CLI Commands

### Run Tasks

```bash
# Execute tasks from file
aipartnerupflow run flow --tasks-file tasks.json

# Execute single task
aipartnerupflow run task --task-id task_123
```

### Start Server

```bash
# Start API server
aipartnerupflow serve start --port 8000

# Start with specific host
aipartnerupflow serve start --host 0.0.0.0 --port 8000
```

### Task Management

```bash
# List tasks from database
aipartnerupflow tasks list --user-id user123

# Get task statistics
aipartnerupflow tasks count

# Get task status
aipartnerupflow tasks status task_123

# Watch task progress
aipartnerupflow tasks watch --task-id task_123
```

## Common Input Schema Patterns

### String with Validation

```python
{
    "type": "string",
    "description": "URL",
    "minLength": 1,
    "maxLength": 2048,
    "pattern": "^https?://"
}
```

### Number with Range

```python
{
    "type": "integer",
    "description": "Timeout in seconds",
    "minimum": 1,
    "maximum": 300,
    "default": 30
}
```

### Enum

```python
{
    "type": "string",
    "enum": ["option1", "option2", "option3"],
    "description": "Select option",
    "default": "option1"
}
```

### Array

```python
{
    "type": "array",
    "items": {"type": "string"},
    "description": "List of items",
    "minItems": 1
}
```

### Object

```python
{
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "string"}
    },
    "description": "Configuration object"
}
```

## Error Handling Patterns

### Return Error in Result

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = await self._process(inputs)
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

### Raise Exception

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    if not inputs.get("required_param"):
        raise ValueError("required_param is required")
    
    # Continue execution
    return {"status": "completed", "result": "..."}
```

## Quick Tips

- **Task name must match executor ID**: `name="executor_id"`
- **Dependencies control execution order**: Use `dependencies`, not `parent_id`
- **Lower priority numbers = higher priority**: 0 is highest, 3 is lowest
- **Import executors to register them**: `from my_module import MyExecutor`
- **Always use async for I/O**: Use `aiohttp`, `aiofiles`, etc.
- **Validate inputs early**: Check at the start of `execute()`
- **Return consistent results**: Always return `{"status": "...", ...}`

## See Also

- **[Python API Reference](python.md)** - Complete API documentation
- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Orchestration patterns
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create executors
- **[Examples](../examples/basic_task.md)** - Practical examples

---

**Need more details?** Check the [Full API Documentation](python.md)

