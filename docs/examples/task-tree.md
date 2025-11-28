# Task Tree Examples

This document provides examples of creating and managing task trees with dependencies and priorities.

## Important Concepts

**Parent-Child Relationship vs Dependencies:**

- **Parent-Child (`parent_id`)**: Used only for **organizing** the task tree structure. It helps visualize the hierarchy but does NOT affect execution order.

- **Dependencies (`dependencies`)**: These **determine execution order**. A task executes only when all its required dependencies are satisfied. Dependencies control when tasks run, not parent-child relationships.

**Key Point**: If you want to control execution order, always use `dependencies`. The `parent_id` field is purely for organizational purposes.

## Example 1: Simple Sequential Pipeline

Execute tasks one after another:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Fetch data
    fetch_task = await task_manager.task_repository.create_task(
        name="fetch_data",
        user_id="user123",
        priority=1,
        inputs={"url": "https://api.example.com/data"}
    )
    
    # Step 2: Process data (depends on Step 1)
    process_task = await task_manager.task_repository.create_task(
        name="process_data",
        user_id="user123",
        parent_id=fetch_task.id,
        dependencies=[{"id": fetch_task.id, "required": True}],
        priority=2,
        inputs={"operation": "analyze"}
    )
    
    # Step 3: Save results (depends on Step 2)
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
    
    # Execute (tasks execute in order: fetch -> process -> save)
    result = await task_manager.distribute_task_tree(task_tree)
    print(f"Execution completed: {result.calculate_status()}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 2: Parallel Execution

Execute multiple tasks in parallel, then merge results:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Root task
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="user123",
        priority=1
    )
    
    # Task 1: Fetch from API A (parallel)
    task1 = await task_manager.task_repository.create_task(
        name="fetch_api_a",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,
        inputs={"url": "https://api-a.example.com/data"}
    )
    
    # Task 2: Fetch from API B (parallel with Task 1)
    task2 = await task_manager.task_repository.create_task(
        name="fetch_api_b",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,
        inputs={"url": "https://api-b.example.com/data"}
    )
    
    # Task 3: Merge results (depends on both Task 1 and Task 2)
    merge_task = await task_manager.task_repository.create_task(
        name="merge_results",
        user_id="user123",
        parent_id=root_task.id,
        dependencies=[
            {"id": task1.id, "required": True},
            {"id": task2.id, "required": True}
        ],
        priority=3,
        inputs={"operation": "merge"}
    )
    
    # Build tree
    task_tree = TaskTreeNode(root_task)
    task_tree.add_child(TaskTreeNode(task1))
    task_tree.add_child(TaskTreeNode(task2))
    task_tree.add_child(TaskTreeNode(merge_task))
    
    # Execute (Task 1 and Task 2 run in parallel, then Task 3)
    result = await task_manager.distribute_task_tree(task_tree)
    print(f"Final status: {result.calculate_status()}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 3: Priority-Based Execution

Use priorities to control execution order:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Root task
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="user123",
        priority=1
    )
    
    # Urgent task (priority 0 - executes first)
    urgent_task = await task_manager.task_repository.create_task(
        name="urgent_task",
        user_id="user123",
        parent_id=root_task.id,
        priority=0,  # Highest priority
        inputs={"action": "urgent_operation"}
    )
    
    # Normal task (priority 2 - executes after urgent)
    normal_task = await task_manager.task_repository.create_task(
        name="normal_task",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,  # Normal priority
        inputs={"action": "normal_operation"}
    )
    
    # Low priority task (priority 3 - executes last)
    low_task = await task_manager.task_repository.create_task(
        name="low_task",
        user_id="user123",
        parent_id=root_task.id,
        priority=3,  # Lowest priority
        inputs={"action": "low_priority_operation"}
    )
    
    # Build tree
    task_tree = TaskTreeNode(root_task)
    task_tree.add_child(TaskTreeNode(urgent_task))
    task_tree.add_child(TaskTreeNode(normal_task))
    task_tree.add_child(TaskTreeNode(low_task))
    
    # Execute (order: urgent -> normal -> low)
    result = await task_manager.distribute_task_tree(task_tree)

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 4: Complex Workflow

Combination of sequential and parallel execution:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Root: Data Collection Phase
    root_task = await task_manager.task_repository.create_task(
        name="data_collection",
        user_id="user123",
        priority=1
    )
    
    # Phase 1: Collect data from multiple sources (parallel)
    source1 = await task_manager.task_repository.create_task(
        name="collect_source1",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,
        inputs={"source": "source1"}
    )
    
    source2 = await task_manager.task_repository.create_task(
        name="collect_source2",
        user_id="user123",
        parent_id=root_task.id,
        priority=2,
        inputs={"source": "source2"}
    )
    
    # Phase 2: Process collected data (depends on both sources)
    process_task = await task_manager.task_repository.create_task(
        name="process_data",
        user_id="user123",
        parent_id=root_task.id,
        dependencies=[
            {"id": source1.id, "required": True},
            {"id": source2.id, "required": True}
        ],
        priority=3,
        inputs={"operation": "process"}
    )
    
    # Phase 3: Validate and save (depends on processing)
    validate_task = await task_manager.task_repository.create_task(
        name="validate_data",
        user_id="user123",
        parent_id=root_task.id,
        dependencies=[{"id": process_task.id, "required": True}],
        priority=4,
        inputs={"validation": "strict"}
    )
    
    save_task = await task_manager.task_repository.create_task(
        name="save_data",
        user_id="user123",
        parent_id=root_task.id,
        dependencies=[{"id": process_task.id, "required": True}],
        priority=4,
        inputs={"destination": "database"}
    )
    
    # Phase 4: Notify (depends on save, optional dependency on validate)
    notify_task = await task_manager.task_repository.create_task(
        name="notify",
        user_id="user123",
        parent_id=root_task.id,
        dependencies=[
            {"id": save_task.id, "required": True},
            {"id": validate_task.id, "required": False}  # Optional
        ],
        priority=5,
        inputs={"channel": "email"}
    )
    
    # Build tree
    task_tree = TaskTreeNode(root_task)
    task_tree.add_child(TaskTreeNode(source1))
    task_tree.add_child(TaskTreeNode(source2))
    task_tree.add_child(TaskTreeNode(process_task))
    task_tree.add_child(TaskTreeNode(validate_task))
    task_tree.add_child(TaskTreeNode(save_task))
    task_tree.add_child(TaskTreeNode(notify_task))
    
    # Execute
    result = await task_manager.distribute_task_tree(task_tree)
    print(f"Workflow completed: {result.calculate_status()}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 5: Error Handling with Fallback

Use optional dependencies for fallback scenarios:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Primary task
    primary_task = await task_manager.task_repository.create_task(
        name="primary_service",
        user_id="user123",
        priority=1,
        inputs={"service": "primary"}
    )
    
    # Fallback task (optional dependency - executes even if primary fails)
    fallback_task = await task_manager.task_repository.create_task(
        name="fallback_service",
        user_id="user123",
        parent_id=primary_task.id,
        dependencies=[{"id": primary_task.id, "required": False}],  # Optional
        priority=2,
        inputs={"service": "fallback"}
    )
    
    # Final task (depends on either primary or fallback)
    final_task = await task_manager.task_repository.create_task(
        name="finalize",
        user_id="user123",
        parent_id=primary_task.id,
        dependencies=[
            {"id": primary_task.id, "required": False},
            {"id": fallback_task.id, "required": False}
        ],
        priority=3,
        inputs={"action": "finalize"}
    )
    
    # Build tree
    task_tree = TaskTreeNode(primary_task)
    task_tree.add_child(TaskTreeNode(fallback_task))
    task_tree.add_child(TaskTreeNode(final_task))
    
    # Execute
    result = await task_manager.distribute_task_tree(task_tree)
    
    # Check results
    if primary_task.status == "failed":
        print("Primary task failed, using fallback")
    if final_task.status == "completed":
        print("Final task completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 6: Using TaskCreator

Create task tree from array format:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskCreator, create_session

async def main():
    db = create_session()
    task_creator = TaskCreator(db)
    task_manager = TaskManager(db)
    
    # Define tasks as array
    tasks = [
        {
            "id": "task_1",
            "name": "fetch_data",
            "user_id": "user123",
            "priority": 1,
            "inputs": {"url": "https://api.example.com/data"}
        },
        {
            "id": "task_2",
            "name": "process_data",
            "user_id": "user123",
            "parent_id": "task_1",
            "dependencies": [{"id": "task_1", "required": True}],
            "priority": 2,
            "inputs": {"operation": "analyze"}
        },
        {
            "id": "task_3",
            "name": "save_results",
            "user_id": "user123",
            "parent_id": "task_2",
            "dependencies": [{"id": "task_2", "required": True}],
            "priority": 3,
            "inputs": {"destination": "database"}
        }
    ]
    
    # Create task tree from array
    task_tree = await task_creator.create_task_tree_from_array(tasks)
    
    # Execute
    result = await task_manager.distribute_task_tree(task_tree)
    print(f"Execution completed: {result.calculate_status()}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

1. **Use meaningful task names**: Make task names descriptive
2. **Set appropriate priorities**: Use consistent priority levels
3. **Explicit dependencies**: Always specify dependencies explicitly
4. **Handle errors**: Check task status and handle failures
5. **Use parent-child relationships**: Create clear hierarchy

## Next Steps

- Learn more about [Task Orchestration](../guides/task-orchestration.md)
- See [Custom Tasks](../guides/custom-tasks.md) for creating custom executors
- Check [Python API Reference](../api/python.md) for detailed API documentation

