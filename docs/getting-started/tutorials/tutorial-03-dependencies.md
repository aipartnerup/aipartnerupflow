# Tutorial 3: Working with Dependencies

Master dependencies - the mechanism that controls when tasks execute. This is one of the most important concepts in aipartnerupflow!

## What You'll Learn

By the end of this tutorial, you'll be able to:
- ✅ Understand how dependencies control execution order
- ✅ Create sequential task pipelines
- ✅ Handle multiple dependencies
- ✅ Use optional dependencies for fallbacks
- ✅ Build complex dependency graphs

**Time required:** 25-35 minutes

**Prerequisites**: 
- Completed [Tutorial 1: First Steps](tutorial-01-first-steps.md)
- Completed [Tutorial 2: Task Trees](tutorial-02-task-trees.md)
- Understand task trees and parent-child relationships

## Part 1: Understanding Dependencies

### What are Dependencies?

**Dependencies** control **when tasks execute**. A task with dependencies will wait for its dependencies to complete before executing.

**Key Point**: Dependencies are different from parent-child relationships!
- **Parent-Child** (`parent_id`): Organizational (like folders)
- **Dependencies** (`dependencies`): Execution control (when tasks run)

### Visual Example

```
Task A (no dependencies) → runs first
    ↓
Task B (depends on A) → waits for A, then runs
    ↓
Task C (depends on B) → waits for B, then runs
```

**Execution Order**: A → B → C (automatic!)

## Part 2: Your First Dependency

### Example: Sequential Tasks

Create two tasks where the second depends on the first:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Task 1: Get CPU info (no dependencies)
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    # Task 2: Get memory info (depends on CPU task)
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=cpu_task.id,  # Organizational
        dependencies=[{"id": cpu_task.id, "required": True}],  # Execution: waits for CPU
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Build tree
    root = TaskTreeNode(cpu_task)
    root.add_child(TaskTreeNode(memory_task))
    
    # Execute
    # TaskManager will:
    # 1. Execute cpu_task first (no dependencies)
    # 2. Wait for cpu_task to complete
    # 3. Then execute memory_task (dependency satisfied)
    await task_manager.distribute_task_tree(root)
    
    # Check results
    cpu_result = await task_manager.task_repository.get_task_by_id(cpu_task.id)
    memory_result = await task_manager.task_repository.get_task_by_id(memory_task.id)
    
    print(f"CPU task: {cpu_result.status}")
    print(f"Memory task: {memory_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding the Code

**Key Components:**
1. **`dependencies`**: List of dependency dictionaries
2. **`{"id": cpu_task.id, "required": True}`**: Dependency specification
   - `id`: The task ID to wait for
   - `required`: Whether the dependency must succeed (True) or can fail (False)

**Execution Flow:**
```
CPU Task (runs first, no dependencies)
    ↓ (waits for completion)
Memory Task (runs after CPU completes)
```

## Part 3: Sequential Pipeline

### Example: Three-Step Pipeline

Create a pipeline: Fetch → Process → Save

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Fetch data
    fetch_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    # Step 2: Process data (depends on fetch)
    process_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=fetch_task.id,
        dependencies=[{"id": fetch_task.id, "required": True}],
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Step 3: Save results (depends on process)
    save_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=fetch_task.id,
        dependencies=[{"id": process_task.id, "required": True}],
        priority=3,
        inputs={"resource": "disk"}
    )
    
    # Build pipeline
    root = TaskTreeNode(fetch_task)
    root.add_child(TaskTreeNode(process_task))
    root.add_child(TaskTreeNode(save_task))
    
    # Execute
    # Order: Fetch → Process → Save (automatic!)
    await task_manager.distribute_task_tree(root)
    
    print("Pipeline completed!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Execution Flow:**
```
Fetch → Process → Save
```

**Key Point**: Each task waits for the previous one to complete!

## Part 4: Multiple Dependencies

### Example: Task Depends on Multiple Tasks

Create a task that depends on multiple other tasks:

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Task 1: Get CPU info
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    # Task 2: Get memory info
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "memory"}
    )
    
    # Task 3: Get disk info
    disk_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "disk"}
    )
    
    # Task 4: Aggregate all (depends on ALL three)
    aggregate_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=cpu_task.id,
        dependencies=[
            {"id": cpu_task.id, "required": True},
            {"id": memory_task.id, "required": True},
            {"id": disk_task.id, "required": True}
        ],
        priority=2,
        inputs={"resource": "all"}
    )
    
    # Build tree
    root = TaskTreeNode(cpu_task)
    root.add_child(TaskTreeNode(memory_task))
    root.add_child(TaskTreeNode(disk_task))
    root.add_child(TaskTreeNode(aggregate_task))
    
    # Execute
    # Tasks 1, 2, 3 run in parallel (no dependencies)
    # Task 4 waits for ALL of them to complete
    await task_manager.distribute_task_tree(root)
    
    print("All tasks completed!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Execution Flow:**
```
CPU Task ──┐
           │
Memory Task├──→ Aggregate Task (waits for all three)
           │
Disk Task ──┘
```

**Key Point**: Task 4 only executes after **all three** dependencies complete!

## Part 5: Optional Dependencies

### Example: Fallback Pattern

Use optional dependencies for fallback scenarios:

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Primary task
    primary_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    # Fallback task (runs even if primary fails)
    fallback_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=primary_task.id,
        dependencies=[{"id": primary_task.id, "required": False}],  # Optional!
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Final task (works with either primary or fallback)
    final_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=primary_task.id,
        dependencies=[
            {"id": primary_task.id, "required": False},  # Optional
            {"id": fallback_task.id, "required": False}  # Optional
        ],
        priority=3,
        inputs={"resource": "disk"}
    )
    
    # Build tree
    root = TaskTreeNode(primary_task)
    root.add_child(TaskTreeNode(fallback_task))
    root.add_child(TaskTreeNode(final_task))
    
    # Execute
    # Even if primary_task fails, fallback_task and final_task will still run
    await task_manager.distribute_task_tree(root)

if __name__ == "__main__":
    asyncio.run(main())
```

**Key Point**: `"required": False` means the task can execute even if the dependency fails!

## Part 6: Complex Dependency Graphs

### Example: Complex Workflow

Create a complex workflow with multiple dependency paths:

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create all tasks
    tasks = {}
    
    # Level 1: Independent tasks
    tasks["fetch1"] = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    tasks["fetch2"] = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        priority=1,
        inputs={"resource": "memory"}
    )
    
    # Level 2: Tasks that depend on Level 1
    tasks["process1"] = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=tasks["fetch1"].id,
        dependencies=[{"id": tasks["fetch1"].id, "required": True}],
        priority=2,
        inputs={"resource": "disk"}
    )
    
    tasks["process2"] = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=tasks["fetch2"].id,
        dependencies=[{"id": tasks["fetch2"].id, "required": True}],
        priority=2,
        inputs={"resource": "all"}
    )
    
    # Level 3: Final task depends on both Level 2 tasks
    tasks["final"] = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=tasks["fetch1"].id,
        dependencies=[
            {"id": tasks["process1"].id, "required": True},
            {"id": tasks["process2"].id, "required": True}
        ],
        priority=3,
        inputs={"resource": "cpu"}
    )
    
    # Build tree
    root = TaskTreeNode(tasks["fetch1"])
    root.add_child(TaskTreeNode(tasks["fetch2"]))
    root.add_child(TaskTreeNode(tasks["process1"]))
    root.add_child(TaskTreeNode(tasks["process2"]))
    root.add_child(TaskTreeNode(tasks["final"]))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    print("Complex workflow completed!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Execution Flow:**
```
Fetch1 ──→ Process1 ──┐
                       ├──→ Final
Fetch2 ──→ Process2 ──┘
```

**Execution Order:**
1. Fetch1 and Fetch2 run in parallel
2. Process1 waits for Fetch1, Process2 waits for Fetch2
3. Final waits for both Process1 and Process2

## Part 7: Dependencies vs Priorities

### Important: Dependencies Override Priorities

**Key Rule**: Dependencies take precedence over priorities!

```python
# Task 1: Priority 2, no dependencies
task1 = create_task(name="task1", priority=2, ...)

# Task 2: Priority 0 (higher), but depends on Task 1
task2 = create_task(
    name="task2",
    priority=0,  # Higher priority
    dependencies=[{"id": task1.id, "required": True}],  # But depends on Task 1!
    ...
)
```

**Execution Order**: Task 1 runs first (even though Task 2 has higher priority), then Task 2

**Why**: Dependencies control execution order, priorities only matter when tasks are ready to run!

## Part 8: Common Patterns

### Pattern 1: Sequential Pipeline

```python
# Tasks execute one after another
task1 → task2 → task3
```

**Implementation:**
```python
task2 = create_task(dependencies=[{"id": task1.id, "required": True}])
task3 = create_task(dependencies=[{"id": task2.id, "required": True}])
```

### Pattern 2: Fan-In (Converge)

```python
# Multiple tasks converge to one
task1 ──┐
task2 ──├──→ final_task
task3 ──┘
```

**Implementation:**
```python
final = create_task(
    dependencies=[
        {"id": task1.id, "required": True},
        {"id": task2.id, "required": True},
        {"id": task3.id, "required": True}
    ]
)
```

### Pattern 3: Fan-Out (Diverge)

```python
# One task spawns multiple dependent tasks
root_task ──→ task1
           └──→ task2
           └──→ task3
```

**Implementation:**
```python
task1 = create_task(dependencies=[{"id": root_task.id, "required": True}])
task2 = create_task(dependencies=[{"id": root_task.id, "required": True}])
task3 = create_task(dependencies=[{"id": root_task.id, "required": True}])
```

### Pattern 4: Conditional Execution

```python
# Fallback pattern
primary ──┐
          ├──→ final (works with either)
fallback ─┘
```

**Implementation:**
```python
final = create_task(
    dependencies=[
        {"id": primary.id, "required": False},  # Optional
        {"id": fallback.id, "required": False}   # Optional
    ]
)
```

## Part 9: Best Practices

### 1. Always Specify Dependencies Explicitly

**Good:**
```python
task2 = create_task(
    dependencies=[{"id": task1.id, "required": True}]  # Explicit
)
```

**Bad:**
```python
# Relying on implicit order - don't do this!
task2 = create_task(...)  # No dependency, but hoping task1 runs first
```

### 2. Use Required Dependencies by Default

**Good:**
```python
dependencies=[{"id": task1.id, "required": True}]  # Default
```

**Only use optional when needed:**
```python
dependencies=[{"id": task1.id, "required": False}]  # Only for fallbacks
```

### 3. Keep Dependency Chains Manageable

**Good**: 3-5 levels deep
**Bad**: 10+ levels deep (hard to debug)

### 4. Document Complex Dependencies

```python
# Dependency structure:
# Task1 (no dependencies)
#   ↓
# Task2 (depends on Task1)
#   ↓
# Task3 (depends on Task2)
```

## Part 10: Common Mistakes

### Mistake 1: Circular Dependencies

```python
# Wrong: Circular dependency
task1 = create_task(dependencies=[{"id": task2.id}])
task2 = create_task(dependencies=[{"id": task1.id}])  # Circular!

# This will cause infinite waiting!
```

**Fix**: Avoid circular dependencies. Use a directed acyclic graph (DAG).

### Mistake 2: Missing Dependency

```python
# Wrong: Task depends on task that doesn't exist
task2 = create_task(dependencies=[{"id": "nonexistent_task", "required": True}])

# This will cause errors!
```

**Fix**: Always ensure dependency tasks exist and are in the same tree.

### Mistake 3: Confusing Parent-Child with Dependencies

```python
# Wrong: Thinking parent-child controls execution
child = create_task(parent_id=parent.id)  # This doesn't make child wait!

# Right: Use dependencies
child = create_task(
    parent_id=parent.id,  # Organizational
    dependencies=[{"id": parent.id, "required": True}]  # Execution order
)
```

## Part 11: Debugging Dependencies

### Check Dependency Status

```python
# After execution, check if dependencies were satisfied
task = await task_manager.task_repository.get_task_by_id(task_id)

print(f"Task status: {task.status}")
print(f"Dependencies: {task.dependencies}")

# Check each dependency
for dep in task.dependencies:
    dep_task = await task_manager.task_repository.get_task_by_id(dep["id"])
    print(f"Dependency {dep['id']}: {dep_task.status}")
    if dep_task.status == "failed":
        print(f"  Error: {dep_task.error}")
```

### Why is My Task Stuck in "pending"?

**Common causes:**
1. Dependencies not completed
2. Dependency task failed (if required=True)
3. Dependency task not in tree
4. Circular dependency

**Debug:**
```python
# Check task status
task = await task_manager.task_repository.get_task_by_id(task_id)
print(f"Status: {task.status}")

# Check dependencies
for dep in task.dependencies:
    dep_task = await task_manager.task_repository.get_task_by_id(dep["id"])
    print(f"Dependency {dep['id']}: {dep_task.status}")
```

## Part 12: Next Steps

You've mastered dependencies! Next:

1. **[Task Orchestration Guide](../guides/task-orchestration.md)** - Deep dive into orchestration
2. **[Best Practices](../guides/best-practices.md)** - Learn from experts
3. **[Basic Examples](../examples/basic_task.md)** - See more patterns

## Summary

In this tutorial, you learned:
- ✅ How dependencies control execution order
- ✅ How to create sequential pipelines
- ✅ How to handle multiple dependencies
- ✅ How to use optional dependencies for fallbacks
- ✅ Common patterns and best practices
- ✅ How to debug dependency issues

**Key Takeaways:**
- Dependencies control **when** tasks run
- Parent-child is for **organization** only
- Dependencies override priorities
- Always specify dependencies explicitly

**Next**: [Task Orchestration Guide →](../guides/task-orchestration.md)

