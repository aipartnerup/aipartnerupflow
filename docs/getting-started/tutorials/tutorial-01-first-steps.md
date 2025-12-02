# Tutorial 1: First Steps

This is a complete beginner-friendly tutorial. If you're new to aipartnerupflow, start here!

## What You'll Learn

By the end of this tutorial, you'll be able to:
- ✅ Install and set up aipartnerupflow
- ✅ Create and execute your first task
- ✅ Understand the basic workflow
- ✅ Use built-in executors
- ✅ Check task status and results

**Time required:** 15-20 minutes

## Prerequisites

- Python 3.10+ installed
- Basic Python knowledge (variables, functions, async/await basics)
- A text editor or IDE

## Part 1: Installation and Setup

### Step 1: Install aipartnerupflow

```bash
pip install aipartnerupflow
```

That's it! No database setup needed - DuckDB works out of the box.

### Step 2: Verify Installation

```python
import aipartnerupflow
print(aipartnerupflow.__version__)
```

If you see a version number, you're good to go!

## Part 2: Your Very First Task

Let's create the simplest possible task to see aipartnerupflow in action.

### The Goal

Get CPU information from your system using the built-in `system_info_executor`.

### Complete Code

Create a file `tutorial_01.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    print("🚀 Starting aipartnerupflow tutorial...")
    
    # Step 1: Create database session
    # DuckDB is used by default - no configuration needed!
    print("📦 Creating database session...")
    db = create_session()
    
    # Step 2: Create TaskManager
    # This is the orchestrator that manages everything
    print("🎯 Creating TaskManager...")
    task_manager = TaskManager(db)
    
    # Step 3: Create a task
    # We're using the built-in system_info_executor
    # It's already available - no custom code needed!
    print("📝 Creating task...")
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",  # Built-in executor ID
        user_id="tutorial_user",      # Your identifier
        priority=2,                   # Normal priority
        inputs={"resource": "cpu"}   # Get CPU information
    )
    
    print(f"✅ Task created with ID: {task.id}")
    print(f"📊 Task status: {task.status}")
    
    # Step 4: Build task tree
    # Even a single task needs to be in a tree structure
    print("🌳 Building task tree...")
    task_tree = TaskTreeNode(task)
    
    # Step 5: Execute the task
    # TaskManager handles everything:
    # - Finds the executor
    # - Executes the task
    # - Updates status
    # - Saves results
    print("⚡ Executing task...")
    await task_manager.distribute_task_tree(task_tree)
    
    # Step 6: Get the result
    # Reload the task to see updated status and result
    print("📥 Fetching results...")
    completed_task = await task_manager.task_repository.get_task_by_id(task.id)
    
    print(f"\n✅ Task completed!")
    print(f"📊 Final status: {completed_task.status}")
    print(f"💾 Result: {completed_task.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
python tutorial_01.py
```

### Expected Output

```
🚀 Starting aipartnerupflow tutorial...
📦 Creating database session...
🎯 Creating TaskManager...
📝 Creating task...
✅ Task created with ID: <some-uuid>
📊 Task status: pending
🌳 Building task tree...
⚡ Executing task...
📥 Fetching results...

✅ Task completed!
📊 Final status: completed
💾 Result: {'system': 'Darwin', 'cores': 8, 'cpu_count': 8, ...}
```

### What Happened?

1. **Created a task**: We told aipartnerupflow "get CPU info"
2. **TaskManager found the executor**: It automatically found `system_info_executor`
3. **Task executed**: The executor ran and collected CPU information
4. **Result saved**: The result was stored in the database

**Congratulations!** You just executed your first task! 🎉

## Part 3: Understanding the Workflow

Let's break down what happened step by step:

### The Workflow

```
┌─────────────────────────────────────────┐
│  1. Create Task                         │
│     - Define what you want to do        │
│     - Specify inputs                    │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  2. Build Task Tree                     │
│     - Organize tasks in a tree          │
│     - Even single tasks need a tree     │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  3. Execute with TaskManager            │
│     - TaskManager finds the executor    │
│     - Executor runs the task            │
│     - Status updates automatically      │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  4. Get Results                         │
│     - Reload task from database          │
│     - Check status and result           │
└─────────────────────────────────────────┘
```

### Key Components Explained

**TaskManager**: The orchestrator
- Manages task execution
- Finds executors
- Tracks status
- Handles errors

**Task**: What you want to do
- Has a `name` (executor ID)
- Has `inputs` (parameters)
- Has a `status` (pending → in_progress → completed)

**Executor**: The code that does the work
- `system_info_executor` is built-in
- You can create custom executors too!

**Task Tree**: Organization structure
- Even single tasks need a tree
- Multiple tasks form a hierarchy

## Part 4: Experimenting

Let's try different things to understand better:

### Experiment 1: Get Different Information

Modify the `inputs` to get different system information:

```python
# Get memory information
inputs={"resource": "memory"}

# Get disk information
inputs={"resource": "disk"}

# Get all system resources
inputs={"resource": "all"}
```

### Experiment 2: Check Task Status

Add status checking during execution:

```python
# After creating task
print(f"Initial status: {task.status}")  # Should be "pending"

# After execution
completed_task = await task_manager.task_repository.get_task_by_id(task.id)
print(f"Final status: {completed_task.status}")  # Should be "completed"
```

### Experiment 3: Handle Errors

Try with invalid input:

```python
# This might fail
inputs={"resource": "invalid_resource"}
```

Check the error:

```python
failed_task = await task_manager.task_repository.get_task_by_id(task.id)
if failed_task.status == "failed":
    print(f"Error: {failed_task.error}")
```

## Part 5: Multiple Tasks

Now let's create multiple tasks to see how they work together:

### Example: Get All System Resources

Create a file `tutorial_01_multiple.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create multiple tasks
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "memory"}
    )
    
    disk_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "disk"}
    )
    
    # Build task tree (all tasks are children of a root)
    # For now, we'll use cpu_task as root
    root = TaskTreeNode(cpu_task)
    root.add_child(TaskTreeNode(memory_task))
    root.add_child(TaskTreeNode(disk_task))
    
    # Execute all tasks
    # Since they have no dependencies, they can run in parallel!
    await task_manager.distribute_task_tree(root)
    
    # Get all results
    cpu_result = await task_manager.task_repository.get_task_by_id(cpu_task.id)
    memory_result = await task_manager.task_repository.get_task_by_id(memory_task.id)
    disk_result = await task_manager.task_repository.get_task_by_id(disk_task.id)
    
    print(f"✅ CPU: {cpu_result.status}")
    print(f"✅ Memory: {memory_result.status}")
    print(f"✅ Disk: {disk_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Parallel Execution

In this example:
- All three tasks have **no dependencies**
- They can run **in parallel** (at the same time)
- TaskManager handles this automatically!

## Part 6: What's Next?

You've learned the basics! Here's what to explore:

### Immediate Next Steps

1. **[Core Concepts](../concepts.md)** - Understand the concepts deeply
2. **[Quick Start Guide](../quick-start.md)** - More examples and patterns
3. **[Basic Examples](../examples/basic_task.md)** - Copy-paste ready examples

### Learn More

- **[Task Trees Tutorial](tutorial-02-task-trees.md)** - Build complex task hierarchies
- **[Dependencies Tutorial](tutorial-03-dependencies.md)** - Control execution order
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create your own executors

## Common Questions

**Q: Why do I need a task tree for a single task?**  
A: The framework is designed for complex workflows. Even single tasks use the tree structure for consistency.

**Q: Can I skip creating a task tree?**  
A: No, but you can use `TaskCreator` to build trees from arrays automatically (we'll cover this in later tutorials).

**Q: What if my task fails?**  
A: Check `task.status` - it will be "failed". Check `task.error` for the error message.

**Q: How do I know which executors are available?**  
A: Built-in executors are automatically registered. Check the [API Reference](../api/python.md) or use the registry:
```python
from aipartnerupflow.core.extensions import get_registry
registry = get_registry()
executors = registry.list_by_category(ExtensionCategory.EXECUTOR)
print(executors)
```

## Summary

In this tutorial, you learned:
- ✅ How to install aipartnerupflow
- ✅ How to create and execute tasks
- ✅ How to use built-in executors
- ✅ How to check task status and results
- ✅ How to create multiple tasks

**Next:** [Tutorial 2: Task Trees →](tutorial-02-task-trees.md) or [Core Concepts →](../concepts.md)

