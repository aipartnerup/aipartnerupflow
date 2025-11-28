# Task Orchestration Guide

This guide explains how to use aipartnerupflow's task orchestration features to create and manage complex task trees with dependencies and priorities.

## Overview

Task orchestration in aipartnerupflow allows you to:
- Create hierarchical task trees
- Manage task dependencies
- Control execution order with priorities
- Track task lifecycle and status
- Handle task failures and retries

## Core Concepts

### Task Tree Structure

A task tree is a hierarchical structure where:
- **Root Task**: The top-level task (no parent)
- **Child Tasks**: Tasks that have a parent task
- **Dependencies**: Tasks that must complete before another task can execute
- **Priority**: Controls execution order (lower numbers execute first)

**Important: Parent-Child vs Dependencies**

- **Parent-Child Relationship (`parent_id`)**: Used only for **organizing** the task tree structure. It does NOT affect execution order. Parent-child relationships are purely organizational and help visualize the task hierarchy.

- **Dependencies (`dependencies`)**: These **determine execution order**. A task will only execute when all its required dependencies are satisfied (completed). Dependencies are the mechanism that controls when tasks run, not parent-child relationships.

**Example:**
```python
# Task B is a child of Task A (organizational)
# But Task B depends on Task C (execution order)
task_a = create_task(name="task_a")
task_b = create_task(name="task_b", parent_id=task_a.id)  # Child of A
task_c = create_task(name="task_c")
task_b = create_task(
    name="task_b",
    parent_id=task_a.id,  # Organizational: B is child of A
    dependencies=[{"id": task_c.id, "required": True}]  # Execution: B waits for C
)
# Execution order: C executes first, then B (regardless of parent-child relationship)
```

### Task Lifecycle

Tasks go through the following states:
1. **pending**: Task is created but not yet executed
2. **in_progress**: Task is currently executing
3. **completed**: Task finished successfully
4. **failed**: Task execution failed
5. **cancelled**: Task was cancelled

## Creating Task Trees

### Basic Task Tree

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create root task
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="user123",
        priority=1
    )
    
    # Create child task
    child_task = await task_manager.task_repository.create_task(
        name="child_task",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,
        inputs={"data": "example"}
    )
    
    # Build task tree
    task_tree = TaskTreeNode(root_task)
    task_tree.add_child(TaskTreeNode(child_task))
    
    # Execute
    result = await task_manager.distribute_task_tree(task_tree)
    print(f"Result: {result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Task Dependencies

Dependencies ensure tasks execute in the correct order:

```python
# Task 1: Fetch data
fetch_task = await task_manager.task_repository.create_task(
    name="fetch_data",
    user_id="user123",
    priority=1,
    inputs={"url": "https://api.example.com/data"}
)

# Task 2: Process data (depends on Task 1)
process_task = await task_manager.task_repository.create_task(
    name="process_data",
    user_id="user123",
    parent_id=fetch_task.id,
    dependencies=[{"id": fetch_task.id, "required": True}],
    priority=2,
    inputs={"operation": "analyze"}
)

# Task 3: Save results (depends on Task 2)
save_task = await task_manager.task_repository.create_task(
    name="save_results",
    user_id="user123",
    parent_id=process_task.id,
    dependencies=[{"id": process_task.id, "required": True}],
    priority=3,
    inputs={"destination": "database"}
)

# Build tree
task_tree = TaskTreeNode(fetch_task)
task_tree.add_child(TaskTreeNode(process_task))
task_tree.children[0].add_child(TaskTreeNode(save_task))

# Execute (tasks will execute in order: fetch -> process -> save)
result = await task_manager.distribute_task_tree(task_tree)
```

### Dependency Types

#### Required Dependencies

Required dependencies must complete successfully before the dependent task can execute:

```python
dependencies=[
    {"id": "task_1", "required": True}  # Task must complete successfully
]
```

If a required dependency fails, the dependent task will not execute.

#### Optional Dependencies

Optional dependencies allow execution even if the dependency fails:

```python
dependencies=[
    {"id": "task_1", "required": False}  # Task can execute even if dependency fails
]
```

### Priority Scheduling

Priority controls execution order. Lower numbers execute first:

```python
# Priority levels:
# 0 = urgent (highest priority)
# 1 = high
# 2 = normal (default)
# 3 = low (lowest priority)

task1 = await task_manager.task_repository.create_task(
    name="urgent_task",
    user_id="user123",
    priority=0  # Executes first
)

task2 = await task_manager.task_repository.create_task(
    name="normal_task",
    user_id="user123",
    priority=2  # Executes after urgent tasks
)
```

Tasks with the same priority execute in the order they are added to the tree.

## Task Manager API

### Creating Tasks

```python
task = await task_manager.task_repository.create_task(
    name="task_name",           # Required: Task name (executor identifier)
    user_id="user123",          # Required: User ID
    parent_id=None,             # Optional: Parent task ID
    priority=2,                 # Optional: Priority (default: 2)
    dependencies=[],            # Optional: List of dependencies
    inputs={},                  # Optional: Input parameters
    schemas={},                 # Optional: Task schemas
    status="pending"            # Optional: Initial status (default: "pending")
)
```

### Building Task Trees

```python
# Create TaskTreeNode from TaskModel
root_node = TaskTreeNode(root_task)

# Add child nodes
root_node.add_child(TaskTreeNode(child_task))

# Access children
for child in root_node.children:
    print(f"Child: {child.task.name}")
```

### Executing Task Trees

```python
# Execute without streaming
result = await task_manager.distribute_task_tree(task_tree)

# Execute with streaming (for real-time updates)
await task_manager.distribute_task_tree_with_streaming(task_tree)
```

### Task Status and Results

```python
# Get task by ID
task = await task_manager.task_repository.get_task_by_id(task_id)

# Check status
print(f"Status: {task.status}")
print(f"Progress: {task.progress}")
print(f"Result: {task.result}")
print(f"Error: {task.error}")
```

## Advanced Patterns

### Parallel Execution

Tasks without dependencies can execute in parallel:

```python
# Task 1 and Task 2 can execute in parallel
task1 = await task_manager.task_repository.create_task(
    name="task1",
    user_id="user123",
    priority=1
)

task2 = await task_manager.task_repository.create_task(
    name="task2",
    user_id="user123",
    priority=1
)

# Task 3 depends on both
task3 = await task_manager.task_repository.create_task(
    name="task3",
    user_id="user123",
    parent_id=root_task.id,
    dependencies=[
        {"id": task1.id, "required": True},
        {"id": task2.id, "required": True}
    ],
    priority=2
)
```

### Conditional Execution

Use optional dependencies for conditional execution:

```python
# Task 2 can execute even if Task 1 fails
task2 = await task_manager.task_repository.create_task(
    name="fallback_task",
    user_id="user123",
    dependencies=[{"id": task1.id, "required": False}],
    priority=2
)
```

### Task Cancellation

Cancel a running task:

```python
result = await task_manager.cancel_task(
    task_id="task_123",
    error_message="User requested cancellation"
)
```

## Best Practices

### 1. Use Meaningful Task Names

Task names should clearly indicate what the task does:

```python
# Good
name="fetch_user_data"
name="process_payment"
name="send_notification"

# Bad
name="task1"
name="do_stuff"
name="x"
```

### 2. Set Appropriate Priorities

Use priority levels consistently:
- `0`: Critical tasks that must execute first
- `1`: High priority tasks
- `2`: Normal tasks (default)
- `3`: Low priority tasks

### 3. Handle Dependencies Explicitly

Always specify dependencies explicitly:

```python
# Good: Explicit dependency
dependencies=[{"id": task1.id, "required": True}]

# Bad: Implicit dependency (relying on execution order)
# No dependency specified
```

### 4. Use Parent-Child Relationships for Organization, Dependencies for Execution

**Parent-child relationships (`parent_id`)** are for organizing the task tree structure:
- Use them to group related tasks visually
- They help understand the task hierarchy
- They do NOT affect execution order

**Dependencies (`dependencies`)** control execution order:
- Use them to specify which tasks must complete before another task runs
- They determine the actual execution sequence
- A task executes when its dependencies are satisfied, regardless of parent-child relationships

```python
# Good: Clear organization with explicit dependencies
root_task = create_task(name="root")
child_task = create_task(
    name="child",
    parent_id=root_task.id,  # Organizational: child of root
    dependencies=[{"id": "other_task", "required": True}]  # Execution: waits for other_task
)

# Bad: Relying on parent-child for execution order
# Parent-child does NOT guarantee execution order
```

### 5. Handle Errors Gracefully

Check task status and handle failures:

```python
result = await task_manager.distribute_task_tree(task_tree)

# Check if any tasks failed
if task.status == "failed":
    print(f"Task {task.id} failed: {task.error}")
    # Handle failure appropriately
```

## Common Patterns

### Pattern 1: Sequential Pipeline

```python
# Tasks execute one after another
task1 -> task2 -> task3
```

### Pattern 2: Fan-Out

```python
# One task spawns multiple parallel tasks
root_task -> [task1, task2, task3]
```

### Pattern 3: Fan-In

```python
# Multiple tasks converge to one task
[task1, task2, task3] -> final_task
```

### Pattern 4: Complex Workflow

```python
# Combination of patterns
root -> [task1, task2] -> task3 -> [task4, task5] -> final
```

## Troubleshooting

### Task Not Executing

**Problem**: Task remains in "pending" status

**Solutions**:
- Check if dependencies are completed
- Verify task name matches registered executor
- Check for errors in parent tasks

### Dependency Not Satisfied

**Problem**: Task waiting for dependency that never completes

**Solutions**:
- Verify dependency task ID is correct
- Check if dependency task failed
- Ensure dependency task is in the same tree

### Priority Not Working

**Problem**: Tasks not executing in expected order

**Solutions**:
- Verify priority values (lower = higher priority)
- Check if dependencies override priority
- Ensure tasks are at the same level in the tree

## Next Steps

- Learn about [Custom Tasks](custom-tasks.md)
- See [API Reference](api-reference.md) for detailed API documentation
- Check [Examples](../examples/basic_task.md) for more patterns

