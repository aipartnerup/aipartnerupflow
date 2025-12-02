# Quick Start Guide

Get started with aipartnerupflow in 10 minutes. This guide will walk you through creating and executing your first task.

## Prerequisites

- Python 3.10 or higher (3.12+ recommended)
- Basic understanding of Python async/await (we'll explain as we go)

## Step 0: Installation

### Minimal Installation (Core Only)

```bash
pip install aipartnerupflow
```

This installs the core orchestration framework with no optional dependencies.

**What you get:**
- Task orchestration engine (TaskManager)
- Built-in executors (system_info_executor, command_executor)
- Storage (DuckDB - no setup needed!)

### Full Installation (All Features)

```bash
pip install aipartnerupflow[all]
```

This includes everything:
- Core orchestration framework
- CrewAI support for LLM tasks
- A2A Protocol Server
- CLI tools
- PostgreSQL storage support

**For this tutorial:** The minimal installation is enough!

## Step 1: Your First Task (Using Built-in Executor)

Let's start with the simplest possible example - using a built-in executor. No custom code needed!

### What We'll Do

We'll create a task that gets system information (CPU, memory, disk) using the built-in `system_info_executor`.

### Complete Example

Create a file `first_task.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    # Step 1: Create a database session
    # DuckDB is used by default - no configuration needed!
    db = create_session()
    
    # Step 2: Create a TaskManager
    # This is the orchestrator that manages task execution
    task_manager = TaskManager(db)
    
    # Step 3: Create a task
    # We're using the built-in "system_info_executor"
    # It's already registered and ready to use!
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",  # This matches the executor ID
        user_id="user123",            # Your user identifier
        priority=2,                   # Normal priority
        inputs={"resource": "cpu"}    # Get CPU information
    )
    
    # Step 4: Build a task tree
    # Even for a single task, we need a tree structure
    task_tree = TaskTreeNode(task)
    
    # Step 5: Execute the task
    # TaskManager handles everything automatically:
    # - Finds the executor
    # - Executes the task
    # - Tracks status
    # - Handles errors
    await task_manager.distribute_task_tree(task_tree)
    
    # Step 6: Get the result
    # Reload the task to see the updated status and result
    completed_task = await task_manager.task_repository.get_task_by_id(task.id)
    
    print(f"✅ Task Status: {completed_task.status}")
    print(f"📊 Task Result: {completed_task.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
python first_task.py
```

**Expected Output:**
```
✅ Task Status: completed
📊 Task Result: {'system': 'Darwin', 'cores': 8, 'cpu_count': 8, ...}
```

### What Just Happened?

1. **Created a task**: We defined what we want to do (get CPU info)
2. **TaskManager found the executor**: It automatically found `system_info_executor`
3. **Task executed**: The executor ran and got the CPU information
4. **Result stored**: The result was saved in the database

**That's it!** You just executed your first task with aipartnerupflow! 🎉

## Step 2: Understanding Task Execution

Let's break down what happened in more detail:

### The Components

```
┌─────────────────────────────────────────────────┐
│              Your Application                    │
│  (first_task.py)                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│            TaskManager                           │
│  - Creates tasks                                 │
│  - Manages execution                            │
│  - Tracks status                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│         Task (in database)                      │
│  - name: "system_info_executor"                 │
│  - inputs: {"resource": "cpu"}                   │
│  - status: pending → in_progress → completed    │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│      Executor (system_info_executor)            │
│  - Runs the actual code                         │
│  - Returns the result                           │
└─────────────────────────────────────────────────┘
```

### Key Concepts

- **Task**: A unit of work (what you want to do)
- **Executor**: The code that does the work (how it's done)
- **TaskManager**: Coordinates everything (the conductor)
- **Task Tree**: Organizes tasks (even single tasks need a tree)

### Try It Yourself

Modify the example to get different information:

```python
# Get memory information instead
inputs={"resource": "memory"}

# Get disk information
inputs={"resource": "disk"}

# Get all system resources
inputs={"resource": "all"}
```

## Step 3: Task Dependencies

Now let's create multiple tasks where one depends on another. This is where aipartnerupflow really shines!

### Example: Sequential Tasks

Create a file `dependent_tasks.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Task 1: Get CPU info
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        priority=1,  # Higher priority (lower number = higher priority)
        inputs={"resource": "cpu"}
    )
    
    # Task 2: Get memory info (depends on CPU task)
    # This task will wait for cpu_task to complete!
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        parent_id=cpu_task.id,  # Organizational: child of cpu_task
        dependencies=[{"id": cpu_task.id, "required": True}],  # Execution: wait for cpu_task
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Build task tree
    root = TaskTreeNode(cpu_task)
    root.add_child(TaskTreeNode(memory_task))
    
    # Execute
    # TaskManager will:
    # 1. Execute cpu_task first
    # 2. Wait for it to complete
    # 3. Then execute memory_task
    await task_manager.distribute_task_tree(root)
    
    # Check results
    cpu_result = await task_manager.task_repository.get_task_by_id(cpu_task.id)
    memory_result = await task_manager.task_repository.get_task_by_id(memory_task.id)
    
    print(f"✅ CPU Task: {cpu_result.status}")
    print(f"✅ Memory Task: {memory_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Dependencies

**Key Point**: `dependencies` control execution order, not `parent_id`!

- **parent_id**: Organizational (like folders) - doesn't affect when tasks run
- **dependencies**: Execution control - determines when tasks run

In the example above:
- `memory_task` is a **child** of `cpu_task` (organization)
- `memory_task` **depends on** `cpu_task` (execution order)

### Try It Yourself

Create three tasks in sequence:

```python
# Task 1: CPU
cpu_task = await task_manager.task_repository.create_task(...)

# Task 2: Memory (depends on CPU)
memory_task = await task_manager.task_repository.create_task(
    dependencies=[{"id": cpu_task.id}],
    ...
)

# Task 3: Disk (depends on Memory)
disk_task = await task_manager.task_repository.create_task(
    dependencies=[{"id": memory_task.id}],
    ...
)
```

**Execution Order**: CPU → Memory → Disk (automatic!)

## Step 4: Creating Your Own Executor

Now let's create a custom executor. This is where you add your own business logic!

### Example: Simple Data Processing

Create a file `my_executor.py`:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class GreetingTask(BaseTask):
    """A simple task that creates personalized greetings"""
    
    id = "greeting_task"
    name = "Greeting Task"
    description = "Creates a personalized greeting message"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
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

### Use Your Custom Executor

Create a file `use_custom_executor.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
# Import your executor (automatically registered via @executor_register())
from my_executor import GreetingTask

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create a task using your custom executor
    task = await task_manager.task_repository.create_task(
        name="greeting_task",  # Must match executor ID
        user_id="user123",
        inputs={
            "name": "Alice",
            "language": "en"
        }
    )
    
    # Build and execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"✅ Greeting: {result.result['greeting']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Custom Executors

**What you need to implement:**

1. **id**: Unique identifier (used in `name` field when creating tasks)
2. **name**: Display name
3. **description**: What the task does
4. **execute()**: The actual work (async function)
5. **get_input_schema()**: Input parameter definition (JSON Schema)

**The `@executor_register()` decorator** automatically registers your executor - just import it!

## Step 5: Next Steps

Congratulations! You've learned the basics. Here's what to explore next:

### Immediate Next Steps

1. **[Core Concepts](concepts.md)** - Deep dive into the concepts you just used
2. **[First Steps Tutorial](tutorials/tutorial-01-first-steps.md)** - More detailed beginner tutorial
3. **[Basic Examples](../examples/basic_task.md)** - Copy-paste ready examples

### Learn More

- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Master task trees and dependencies
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create more complex executors
- **[Best Practices](../guides/best-practices.md)** - Learn from the experts

### Advanced Topics

- **[Task Trees Tutorial](tutorials/tutorial-02-task-trees.md)** - Build complex workflows
- **[Dependencies Tutorial](tutorials/tutorial-03-dependencies.md)** - Master dependency management

## Common Patterns

### Pattern 1: Simple Task (No Dependencies)

```python
task = await task_manager.task_repository.create_task(
    name="executor_id",
    user_id="user123",
    inputs={"key": "value"}
)
task_tree = TaskTreeNode(task)
await task_manager.distribute_task_tree(task_tree)
```

### Pattern 2: Sequential Tasks (With Dependencies)

```python
# Task 1
task1 = await task_manager.task_repository.create_task(...)

# Task 2 depends on Task 1
task2 = await task_manager.task_repository.create_task(
    dependencies=[{"id": task1.id, "required": True}],
    ...
)

# Build tree
root = TaskTreeNode(task1)
root.add_child(TaskTreeNode(task2))

# Execute (Task2 waits for Task1 automatically)
await task_manager.distribute_task_tree(root)
```

### Pattern 3: Parallel Tasks (No Dependencies)

```python
# Both tasks can run at the same time
task1 = await task_manager.task_repository.create_task(...)
task2 = await task_manager.task_repository.create_task(...)  # No dependency on task1

# Build tree
root = TaskTreeNode(parent_task)
root.add_child(TaskTreeNode(task1))
root.add_child(TaskTreeNode(task2))

# Execute (both run in parallel)
await task_manager.distribute_task_tree(root)
```

## Troubleshooting

### Problem: Task Executor Not Found

**Error:** `Task executor not found: executor_id`

**Solutions:**
1. **For built-in executors**: Make sure you've imported the extension:
   ```python
   # This automatically registers built-in executors
   import aipartnerupflow.extensions.stdio
   ```

2. **For custom executors**: Make sure you:
   - Used `@executor_register()` decorator
   - Imported the executor class in your main script
   - The `name` field matches the executor `id`

### Problem: Task Stays in "pending" Status

**Possible causes:**
- Dependencies not satisfied (check if dependency tasks are completed)
- Executor not found (see above)
- Task not executed (make sure you called `distribute_task_tree()`)

**Solution:**
```python
# Check task status
task = await task_manager.task_repository.get_task_by_id(task_id)
print(f"Status: {task.status}")
print(f"Error: {task.error}")  # Check for errors
```

### Problem: Database Error

**Error:** Database connection issues

**Solution:**
- **DuckDB (default)**: No setup needed! It just works.
- **PostgreSQL**: Set environment variable:
  ```bash
  export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
  ```

### Problem: Import Error

**Error:** `ModuleNotFoundError: No module named 'aipartnerupflow'`

**Solution:**
```bash
pip install aipartnerupflow
```

## Try It Yourself

### Exercise 1: Multiple System Checks

Create tasks to check CPU, memory, and disk, then aggregate the results.

### Exercise 2: Custom Greeting in Multiple Languages

Use the `GreetingTask` example to create greetings in different languages, then combine them.

### Exercise 3: Sequential Processing

Create a pipeline: fetch data → process data → save results (each step depends on the previous).

## Getting Help

- **Stuck?** Check the [FAQ](../guides/faq.md)
- **Need examples?** See [Basic Examples](../examples/basic_task.md)
- **Want to understand concepts?** Read [Core Concepts](concepts.md)
- **Found a bug?** [Report it on GitHub](https://github.com/aipartnerup/aipartnerupflow/issues)
- **Have questions?** [Ask on Discussions](https://github.com/aipartnerup/aipartnerupflow/discussions)

---

**Ready for more?** → [Learn Core Concepts →](concepts.md) or [Try the First Steps Tutorial →](tutorials/tutorial-01-first-steps.md)
