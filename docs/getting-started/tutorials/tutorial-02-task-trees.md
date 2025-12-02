# Tutorial 2: Building Task Trees

Learn how to build complex task trees with multiple tasks, dependencies, and priorities.

## What You'll Learn

By the end of this tutorial, you'll be able to:
- ✅ Build task trees with multiple tasks
- ✅ Understand parent-child relationships
- ✅ Create hierarchical task structures
- ✅ Organize complex workflows

**Time required:** 20-30 minutes

**Prerequisites**: 
- Completed [Tutorial 1: First Steps](tutorial-01-first-steps.md)
- Understand basic task execution

## Part 1: Understanding Task Trees

### What is a Task Tree?

A **task tree** is a hierarchical structure that organizes tasks. Think of it like a family tree:
- **Root task**: The top-level task (like a family ancestor)
- **Child tasks**: Tasks that belong to a parent (like children)
- **Grandchild tasks**: Tasks that belong to a child (like grandchildren)

### Visual Representation

```
Root Task
│
├── Child Task 1
│   │
│   └── Grandchild Task 1.1
│
├── Child Task 2
│
└── Child Task 3
    │
    ├── Grandchild Task 3.1
    └── Grandchild Task 3.2
```

### Key Concept: Parent-Child is Organizational

**Important**: Parent-child relationships (`parent_id`) are for **organization only**. They don't control execution order!

- **Parent-Child**: Like folders - helps organize tasks
- **Dependencies**: Control when tasks run (we'll cover this in Tutorial 3)

## Part 2: Building Your First Task Tree

### Example: Simple Two-Level Tree

Let's create a simple tree with a root and one child:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Create root task
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="tutorial_user",
        priority=1
    )
    
    # Step 2: Create child task
    child_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,  # This makes it a child
        priority=2,
        inputs={"resource": "cpu"}
    )
    
    # Step 3: Build task tree
    root = TaskTreeNode(root_task)
    root.add_child(TaskTreeNode(child_task))
    
    # Step 4: Execute
    await task_manager.distribute_task_tree(root)
    
    # Step 5: Check results
    child_result = await task_manager.task_repository.get_task_by_id(child_task.id)
    print(f"Child task status: {child_result.status}")
    print(f"Child task result: {child_result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding the Code

1. **Root task**: The top-level task (organizational parent)
2. **Child task**: Has `parent_id=root_task.id` (organizational child)
3. **TaskTreeNode**: Wraps tasks in tree structure
4. **add_child()**: Adds a child node to the tree

**Visual Structure:**
```
Root Task
│
└── Child Task (gets CPU info)
```

## Part 3: Multiple Children

### Example: Root with Multiple Children

Create a root task with multiple children:

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create root
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="tutorial_user",
        priority=1
    )
    
    # Create multiple children
    child1 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,  # Child of root
        priority=2,
        inputs={"resource": "cpu"}
    )
    
    child2 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,  # Also child of root
        priority=2,
        inputs={"resource": "memory"}
    )
    
    child3 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,  # Also child of root
        priority=2,
        inputs={"resource": "disk"}
    )
    
    # Build tree
    root = TaskTreeNode(root_task)
    root.add_child(TaskTreeNode(child1))
    root.add_child(TaskTreeNode(child2))
    root.add_child(TaskTreeNode(child3))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check all results
    for child in [child1, child2, child3]:
        result = await task_manager.task_repository.get_task_by_id(child.id)
        print(f"{child.id}: {result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Visual Structure:**
```
Root Task
│
├── Child 1 (CPU)
├── Child 2 (Memory)
└── Child 3 (Disk)
```

**Note**: All three children can run in parallel (no dependencies between them)!

## Part 4: Multi-Level Trees

### Example: Three-Level Tree

Create a tree with root, children, and grandchildren:

```python
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Level 1: Root
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="tutorial_user",
        priority=1
    )
    
    # Level 2: Children
    child1 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,
        priority=2,
        inputs={"resource": "cpu"}
    )
    
    child2 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=root_task.id,
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Level 3: Grandchildren
    grandchild1 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=child1.id,  # Child of child1
        priority=3,
        inputs={"resource": "all"}
    )
    
    grandchild2 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="tutorial_user",
        parent_id=child2.id,  # Child of child2
        priority=3,
        inputs={"resource": "all"}
    )
    
    # Build tree
    root = TaskTreeNode(root_task)
    child1_node = TaskTreeNode(child1)
    child2_node = TaskTreeNode(child2)
    
    child1_node.add_child(TaskTreeNode(grandchild1))
    child2_node.add_child(TaskTreeNode(grandchild2))
    
    root.add_child(child1_node)
    root.add_child(child2_node)
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check results
    print("Tree execution completed!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Visual Structure:**
```
Root Task
│
├── Child 1 (CPU)
│   │
│   └── Grandchild 1 (All resources)
│
└── Child 2 (Memory)
    │
    └── Grandchild 2 (All resources)
```

## Part 5: Building Trees Programmatically

### Helper Function

Create a helper function to build trees more easily:

```python
def build_tree_from_tasks(task_manager, tasks_config):
    """
    Build a task tree from configuration
    
    tasks_config: List of dicts with task info
    """
    # Create all tasks first
    created_tasks = {}
    for config in tasks_config:
        task = await task_manager.task_repository.create_task(
            name=config["name"],
            user_id=config["user_id"],
            parent_id=config.get("parent_id"),
            priority=config.get("priority", 2),
            inputs=config.get("inputs", {})
        )
        created_tasks[config["id"]] = task
    
    # Build tree
    root_id = None
    nodes = {}
    
    # Find root (task with no parent)
    for task_id, task in created_tasks.items():
        if task.parent_id is None:
            root_id = task_id
            break
    
    # Create nodes
    for task_id, task in created_tasks.items():
        nodes[task_id] = TaskTreeNode(task)
    
    # Add children
    for task_id, task in created_tasks.items():
        if task.parent_id:
            parent_node = nodes[task.parent_id]
            parent_node.add_child(nodes[task_id])
    
    return nodes[root_id]

# Use it
async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    tasks_config = [
        {
            "id": "root",
            "name": "root_task",
            "user_id": "tutorial_user",
            "priority": 1
        },
        {
            "id": "child1",
            "name": "system_info_executor",
            "user_id": "tutorial_user",
            "parent_id": "root",
            "priority": 2,
            "inputs": {"resource": "cpu"}
        },
        {
            "id": "child2",
            "name": "system_info_executor",
            "user_id": "tutorial_user",
            "parent_id": "root",
            "priority": 2,
            "inputs": {"resource": "memory"}
        }
    ]
    
    # Build tree
    root = await build_tree_from_tasks(task_manager, tasks_config)
    
    # Execute
    await task_manager.distribute_task_tree(root)

if __name__ == "__main__":
    asyncio.run(main())
```

## Part 6: Common Tree Patterns

### Pattern 1: Flat Tree (All Children of Root)

```python
# All tasks are direct children of root
root = TaskTreeNode(root_task)
root.add_child(TaskTreeNode(child1))
root.add_child(TaskTreeNode(child2))
root.add_child(TaskTreeNode(child3))
```

**Use Case**: Parallel processing of independent tasks

### Pattern 2: Deep Tree (Many Levels)

```python
# Tree with many levels
root = TaskTreeNode(root_task)
level1 = TaskTreeNode(child1)
level2 = TaskTreeNode(grandchild1)
level3 = TaskTreeNode(great_grandchild1)

level2.add_child(level3)
level1.add_child(level2)
root.add_child(level1)
```

**Use Case**: Hierarchical data processing

### Pattern 3: Balanced Tree

```python
# Tree where each node has similar number of children
root = TaskTreeNode(root_task)
for i in range(3):
    child = TaskTreeNode(children[i])
    for j in range(2):
        grandchild = TaskTreeNode(grandchildren[i*2 + j])
        child.add_child(grandchild)
    root.add_child(child)
```

**Use Case**: Balanced workload distribution

## Part 7: Tree Operations

### Calculate Progress

Get overall progress of the tree:

```python
# After execution
progress = root.calculate_progress()
print(f"Overall progress: {progress * 100}%")
```

### Calculate Status

Get overall status of the tree:

```python
status = root.calculate_status()
print(f"Overall status: {status}")
# Returns: "completed", "failed", "in_progress", or "pending"
```

### Traverse Tree

Visit all nodes in the tree:

```python
def traverse_tree(node, level=0):
    """Traverse tree and print structure"""
    indent = "  " * level
    print(f"{indent}- {node.task.name} (status: {node.task.status})")
    
    for child in node.children:
        traverse_tree(child, level + 1)

# Use it
traverse_tree(root)
```

**Output:**
```
- root_task (status: completed)
  - child1 (status: completed)
    - grandchild1 (status: completed)
  - child2 (status: completed)
```

## Part 8: Best Practices

### 1. Keep Trees Manageable

**Good**: 3-5 levels deep, 10-20 tasks
**Bad**: 10+ levels deep, 100+ tasks

### 2. Use Meaningful Names

```python
# Good
name="fetch_user_data"
name="process_payment"
name="send_notification"

# Bad
name="task1"
name="task2"
name="x"
```

### 3. Organize by Function

Group related tasks under the same parent:

```python
# Data collection group
data_collection_root = create_task(name="data_collection_root")
fetch_api = create_task(parent_id=data_collection_root.id, ...)
fetch_db = create_task(parent_id=data_collection_root.id, ...)

# Processing group
processing_root = create_task(name="processing_root")
process_data = create_task(parent_id=processing_root.id, ...)
```

### 4. Document Complex Trees

For complex trees, add comments:

```python
# Tree structure:
# Root
# ├── Data Collection
# │   ├── Fetch from API
# │   └── Fetch from DB
# └── Processing
#     ├── Process Data
#     └── Save Results
```

## Part 9: Common Mistakes

### Mistake 1: Forgetting to Add Children

```python
# Wrong: Created tasks but didn't add to tree
root = TaskTreeNode(root_task)
child = TaskTreeNode(child_task)
# Forgot: root.add_child(child)
await task_manager.distribute_task_tree(root)  # Child won't execute!
```

**Fix**: Always add children to the tree

### Mistake 2: Confusing Parent-Child with Dependencies

```python
# Wrong: Thinking parent-child controls execution order
child = create_task(parent_id=parent.id)  # This doesn't make child wait for parent!

# Right: Use dependencies for execution order
child = create_task(
    parent_id=parent.id,  # Organizational
    dependencies=[{"id": parent.id, "required": True}]  # Execution order
)
```

### Mistake 3: Creating Orphan Tasks

```python
# Wrong: Task with parent_id that doesn't exist
child = create_task(parent_id="nonexistent_id")  # Will cause errors!

# Right: Create parent first
parent = create_task(...)
child = create_task(parent_id=parent.id)
```

## Part 10: Next Steps

You've learned how to build task trees! Next:

1. **[Tutorial 3: Dependencies](tutorial-03-dependencies.md)** - Learn how dependencies control execution order
2. **[Task Orchestration Guide](../guides/task-orchestration.md)** - Deep dive into orchestration
3. **[Best Practices](../guides/best-practices.md)** - Learn from experts

## Summary

In this tutorial, you learned:
- ✅ What task trees are and why they're useful
- ✅ How to build simple and complex trees
- ✅ How parent-child relationships work (organizational)
- ✅ Common tree patterns and best practices
- ✅ How to traverse and inspect trees

**Key Takeaway**: Parent-child relationships organize tasks, but dependencies control execution order!

**Next**: [Tutorial 3: Dependencies →](tutorial-03-dependencies.md)

